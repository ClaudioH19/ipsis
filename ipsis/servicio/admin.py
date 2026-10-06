"""``/admin``: configuración de la personalidad y del widget por HTTP.

Solo existe si ``IPSIS_ADMIN_TOKEN`` está definido (≥ 32 caracteres). Reglas:

- ``Authorization: Bearer <token>``, comparado en tiempo constante;
- en producción, HTTPS obligatorio salvo desde la propia máquina; el esquema y
  la IP los fija uvicorn a partir de ``X-Forwarded-*`` solo si vienen del proxy
  declarado (``IPSIS_TRUSTED_PROXY``);
- lista opcional de IPs (``IPSIS_ADMIN_IPS``);
- tras 5 tokens incorrectos, la IP queda bloqueada 15 minutos;
- cuerpo ≤ 256 KiB, limitador de peticiones y sin CORS (lo excluye ``api``);
- cada cambio queda en ``.ipsis/logs/admin.jsonl`` (sin el token ni los valores).

Las rutas y los cuerpos usan los nombres de los archivos (``personality.yaml``,
``styles.yaml``), en inglés; el glosario los traduce a los internos.
"""
from __future__ import annotations

import hmac
import ipaddress
import threading
import time
from collections.abc import Callable

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from ipsis.aplicacion.modo import ModoServicio

LIMITE_CUERPO = 256 * 1024
INTENTOS_MAXIMOS = 5
BLOQUEO_S = 15 * 60


def _es_loopback(ip: str | None) -> bool:
    try:
        return ip is not None and ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


class _Bloqueos:
    """Fallos de token por IP; bloquea tras ``INTENTOS_MAXIMOS``."""

    def __init__(self) -> None:
        self._fallos: dict[str, tuple[int, float]] = {}
        self._candado = threading.Lock()

    def bloqueada(self, ip: str, ahora: float) -> bool:
        with self._candado:
            fallos, hasta = self._fallos.get(ip, (0, 0.0))
            return fallos >= INTENTOS_MAXIMOS and ahora < hasta

    def fallo(self, ip: str, ahora: float) -> None:
        with self._candado:
            fallos, hasta = self._fallos.get(ip, (0, 0.0))
            if fallos >= INTENTOS_MAXIMOS and ahora >= hasta:
                fallos = 0  # el bloqueo anterior venció
            fallos += 1
            self._fallos[ip] = (fallos, ahora + BLOQUEO_S if fallos >= INTENTOS_MAXIMOS else hasta)

    def exito(self, ip: str) -> None:
        with self._candado:
            self._fallos.pop(ip, None)


def transporte_permitido(modo: ModoServicio, request: Request) -> str | None:
    """Motivo de rechazo por IP o transporte (``None`` si se permite). Lo comparten la API y el panel."""
    ip = request.client.host if request.client else "unknown"
    if modo.admin_ips and ip not in modo.admin_ips:
        return "IP not allowed for /admin"
    if not modo.desarrollo and request.url.scheme != "https" and not _es_loopback(ip):
        return "/admin requires HTTPS in production (or a proxy declared in IPSIS_TRUSTED_PROXY)"
    return None


def crear_router_admin(modo: ModoServicio, limitador, al_cambiar: Callable[[], None] | None = None,
                       reloj: Callable[[], float] = time.monotonic) -> APIRouter:
    """Router de ``/admin``. ``al_cambiar`` se llama tras cada escritura (recarga en caliente)."""
    from ipsis.aplicacion.avatar import AvatarInvalido
    from ipsis.aplicacion.personalidad import (
        PersonalidadInvalida,
        actualizar_personalidad,
        importar_avatar_desde,
        probar_tono,
        resumen_admin,
    )
    from ipsis.aplicacion.registro import registrar_admin
    from ipsis.aplicacion.widget import (
        actualizar_estilos,
        aplicar_preset,
        cambiar_estilo,
        cargar_estilos,
        estilo_plano,
        listar_presets,
    )

    bloqueos = _Bloqueos()

    async def verificar(request: Request) -> str:
        ip = request.client.host if request.client else "unknown"
        if motivo := transporte_permitido(modo, request):
            raise HTTPException(status_code=403, detail=motivo)
        ahora = reloj()
        if bloqueos.bloqueada(ip, ahora):
            raise HTTPException(status_code=429, detail="too many attempts; wait 15 minutes",
                                headers={"Retry-After": str(BLOQUEO_S)})
        esquema, _, token = (request.headers.get("authorization") or "").partition(" ")
        if esquema.lower() != "bearer" or not hmac.compare_digest(token.strip().encode(),
                                                                   (modo.token_admin or "").encode()):
            bloqueos.fallo(ip, ahora)
            raise HTTPException(status_code=401, detail="invalid admin token",
                                headers={"WWW-Authenticate": "Bearer"})
        bloqueos.exito(ip)
        if not limitador.permitir(f"admin:{ip}"):
            raise HTTPException(status_code=429, detail="rate limit exceeded",
                                headers={"Retry-After": "3"})
        if int(request.headers.get("content-length") or 0) > LIMITE_CUERPO:
            raise HTTPException(status_code=413, detail="body larger than 256 KiB")
        if len(await request.body()) > LIMITE_CUERPO:
            raise HTTPException(status_code=413, detail="body larger than 256 KiB")
        return ip

    router = APIRouter(prefix="/admin", dependencies=[Depends(verificar)])

    from ipsis.aplicacion.publico import a_publico as a_externo, desde_publico as a_interno

    def _invalido(e: Exception) -> HTTPException:
        errores = getattr(e, "errores", None) or [str(e)]
        return HTTPException(status_code=422, detail={"errors": errores})

    def _personalidad_publica(config) -> dict:
        return a_externo(config.model_dump(mode="json"), "personalidad")

    def _resumen_publico() -> dict:
        r = resumen_admin()
        return {
            "config": a_externo(r["config"], "personalidad"),
            "tones": [{"tone": t["tono"], "description": t["descripcion"], "example": t["ejemplo"],
                       "active": t["activo"]} for t in r["tonos"]],
            "situations": {s: {"origin": "engine" if d["origen"] == "motor" else "widget",
                               "variables": d["variables"]} for s, d in r["situaciones"].items()},
            "events": {e: {"suggested": d["sugerida"], "fallback": d["respaldo"]} for e, d in r["eventos"].items()},
            "avatars": [{"name": a["nombre"], "origin": a["origen"], "error": a["error"]} if "error" in a else
                        {"name": a["nombre"], "origin": a["origen"], "animations": a["animaciones"],
                         "expressions": a["expresiones"]} for a in r["avatares"]],
            "tone_warnings": r["avisos_tono"],
            "avatar": {"name": r["avatar"]["nombre"], "state": r["avatar"]["estado"],
                       "message": r["avatar"]["mensaje"], "keys": r["avatar"]["claves"],
                       "fallbacks": r["avatar"]["respaldos"]},
        }

    def _cambio(request: Request, accion: str, claves: list[str]) -> None:
        registrar_admin(request.client.host if request.client else None, accion, claves)
        if al_cambiar is not None:
            al_cambiar()

    @router.get("/personality")
    def leer_personalidad():
        return _resumen_publico()

    @router.put("/personality")
    def cambiar_personalidad(request: Request, cambios: dict = Body(...)):
        try:
            config = actualizar_personalidad(a_interno(cambios, "personalidad"))
        except PersonalidadInvalida as e:
            raise _invalido(e) from e
        _cambio(request, "personality", list(cambios))
        return _personalidad_publica(config)

    @router.post("/personality/preview")
    def vista_previa(cuerpo: dict = Body(default={})):
        try:
            return probar_tono(cuerpo.get("tone"), cuerpo.get("situation"))
        except PersonalidadInvalida as e:
            raise _invalido(e) from e

    @router.get("/avatars")
    def avatares():
        return _resumen_publico()["avatars"]

    @router.post("/avatars")
    def subir_avatar(request: Request, cuerpo: dict = Body(...)):
        import json

        nombre, definicion = cuerpo.get("name"), cuerpo.get("definition")
        if not isinstance(nombre, str) or not isinstance(definicion, (dict, str)):
            raise HTTPException(status_code=422, detail={"errors": ["expected {name, definition}"]})
        contenido = (definicion if isinstance(definicion, str) else json.dumps(definicion)).encode("utf-8")
        try:
            avatar = importar_avatar_desde(contenido, nombre)
        except AvatarInvalido as e:
            raise _invalido(e) from e
        _cambio(request, "avatar", [nombre])
        return {"name": avatar.nombre, "animations": list(avatar.animaciones),
                "expressions": list(avatar.expresiones)}

    @router.get("/styles")
    def leer_estilos():
        return a_externo(cargar_estilos(), "estilos")

    @router.put("/styles")
    def cambiar_estilos(request: Request, cambios: dict = Body(...)):
        try:
            tema = actualizar_estilos(a_interno(cambios, "estilos"))
        except ValueError as e:
            raise _invalido(e) from e
        _cambio(request, "styles", list(cambios))
        return a_externo(tema, "estilos")

    @router.get("/styles/flat")
    def estilos_plano():
        """Cada valor editable como ``section.key`` (lo del proyecto sobre la plantilla)."""
        return [{"key": clave, "value": valor} for clave, valor in estilo_plano()]

    @router.post("/styles/set")
    def cambiar_estilos_planos(request: Request, cuerpo: dict = Body(...)):
        asignaciones = cuerpo.get("assignments")
        if not isinstance(asignaciones, list) or not all(isinstance(a, str) for a in asignaciones):
            raise HTTPException(status_code=422, detail={"errors": ["expected {assignments: ['section.key=value', …]}"]})
        try:
            tema = cambiar_estilo(asignaciones)
        except ValueError as e:
            raise _invalido(e) from e
        _cambio(request, "styles", [a.partition("=")[0] for a in asignaciones])
        return a_externo(tema, "estilos")

    @router.get("/styles/presets")
    def presets():
        return listar_presets()

    @router.post("/styles/preset")
    def cambiar_preset(request: Request, cuerpo: dict = Body(...)):
        try:
            tema = aplicar_preset(str(cuerpo.get("name", "")))
        except ValueError as e:
            raise _invalido(e) from e
        _cambio(request, "preset", [str(cuerpo.get("name", ""))])
        return a_externo(tema, "estilos")

    return router


# --- panel gráfico (/admin/panel): archivos estáticos; los datos van por la API con token ---------
DIR_PANEL = "admin"
ARCHIVOS_PANEL = {"panel.html": "text/html; charset=utf-8", "panel.js": "application/javascript; charset=utf-8",
                  "panel.css": "text/css; charset=utf-8", "vista-previa.html": "text/html; charset=utf-8"}
CSP_PANEL = ("default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; "
             "frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'")
# La vista previa carga el widget real: su <style> en el Shadow DOM es inline y el
# motor del avatar valida con ajv (``unsafe-eval``). Solo se enmarca desde el panel.
CSP_VISTA_PREVIA = ("default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
                    "connect-src 'self'; img-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; "
                    "form-action 'none'")


def _panel_en_el_idioma(ruta) -> str:
    """``panel.html`` con cada ``{{clave}}`` reemplazada por ``panel.clave`` del catálogo (escapada)."""
    import html
    import re

    from ipsis.recursos.mensajes import t

    plantilla = ruta.read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: html.escape(t(f"panel.{m.group(1)}"), quote=True), plantilla)


def crear_router_panel(modo: ModoServicio, carpeta) -> APIRouter:
    """``/admin/panel`` y sus archivos. Sin token (no traen datos), con las mismas reglas de transporte."""
    from fastapi.responses import FileResponse

    router = APIRouter()

    def _archivo(nombre: str, request: Request):
        if motivo := transporte_permitido(modo, request):
            raise HTTPException(status_code=403, detail=motivo)
        if nombre not in ARCHIVOS_PANEL:
            raise HTTPException(status_code=404, detail="not found")
        if nombre == "panel.html":
            respuesta = Response(content=_panel_en_el_idioma(carpeta / DIR_PANEL / nombre),
                                 media_type=ARCHIVOS_PANEL[nombre])
        else:
            respuesta = FileResponse(carpeta / DIR_PANEL / nombre, media_type=ARCHIVOS_PANEL[nombre])
        respuesta.headers["Content-Security-Policy"] = (CSP_VISTA_PREVIA if nombre == "vista-previa.html"
                                                        else CSP_PANEL)
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        return respuesta

    @router.get("/admin/panel")
    def panel(request: Request):
        return _archivo("panel.html", request)

    @router.get("/admin/panel/{nombre}")
    def archivo_panel(nombre: str, request: Request):
        return _archivo(nombre, request)

    return router


__all__ = ["BLOQUEO_S", "CSP_PANEL", "CSP_VISTA_PREVIA", "INTENTOS_MAXIMOS", "LIMITE_CUERPO", "crear_router_admin", "crear_router_panel",
           "transporte_permitido"]
