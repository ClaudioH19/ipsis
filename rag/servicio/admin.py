"""``/admin``: configuración de la personalidad y del widget por HTTP.

Solo existe si ``RAG_ADMIN_TOKEN`` está definido (≥ 32 caracteres). Reglas:

- ``Authorization: Bearer <token>``, comparado en tiempo constante;
- en producción, HTTPS obligatorio salvo desde la propia máquina; el esquema y
  la IP los fija uvicorn a partir de ``X-Forwarded-*`` solo si vienen del proxy
  declarado (``RAG_PROXY_CONFIABLE``);
- lista opcional de IPs (``RAG_ADMIN_IPS``);
- tras 5 tokens incorrectos, la IP queda bloqueada 15 minutos;
- cuerpo ≤ 256 KiB, limitador de peticiones y sin CORS (lo excluye ``api``);
- cada cambio queda en ``.rag/registros/admin.jsonl`` (sin el token ni los valores).
"""
from __future__ import annotations

import hmac
import ipaddress
import threading
import time
from collections.abc import Callable

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from rag.aplicacion.modo import ModoServicio

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


def crear_router_admin(modo: ModoServicio, limitador, al_cambiar: Callable[[], None] | None = None,
                       reloj: Callable[[], float] = time.monotonic) -> APIRouter:
    """Router de ``/admin``. ``al_cambiar`` se llama tras cada escritura (recarga en caliente)."""
    from rag.aplicacion.avatar import AvatarInvalido
    from rag.aplicacion.personalidad import (
        PersonalidadInvalida,
        actualizar_personalidad,
        importar_avatar_desde,
        probar_tono,
        resumen_admin,
    )
    from rag.aplicacion.registro import registrar_admin
    from rag.aplicacion.widget import actualizar_estilos, cargar_estilos

    bloqueos = _Bloqueos()

    async def verificar(request: Request) -> str:
        ip = request.client.host if request.client else "desconocida"
        if modo.admin_ips and ip not in modo.admin_ips:
            raise HTTPException(status_code=403, detail="IP no permitida para /admin")
        if not modo.desarrollo and request.url.scheme != "https" and not _es_loopback(ip):
            raise HTTPException(status_code=403, detail="/admin exige HTTPS en producción "
                                                        "(o un proxy declarado en RAG_PROXY_CONFIABLE)")
        ahora = reloj()
        if bloqueos.bloqueada(ip, ahora):
            raise HTTPException(status_code=429, detail="demasiados intentos; espera 15 minutos",
                                headers={"Retry-After": str(BLOQUEO_S)})
        esquema, _, token = (request.headers.get("authorization") or "").partition(" ")
        if esquema.lower() != "bearer" or not hmac.compare_digest(token.strip().encode(),
                                                                   (modo.token_admin or "").encode()):
            bloqueos.fallo(ip, ahora)
            raise HTTPException(status_code=401, detail="token de administración inválido",
                                headers={"WWW-Authenticate": "Bearer"})
        bloqueos.exito(ip)
        if not limitador.permitir(f"admin:{ip}"):
            raise HTTPException(status_code=429, detail="límite de peticiones excedido",
                                headers={"Retry-After": "3"})
        if int(request.headers.get("content-length") or 0) > LIMITE_CUERPO:
            raise HTTPException(status_code=413, detail="cuerpo mayor a 256 KiB")
        if len(await request.body()) > LIMITE_CUERPO:
            raise HTTPException(status_code=413, detail="cuerpo mayor a 256 KiB")
        return ip

    router = APIRouter(prefix="/admin", dependencies=[Depends(verificar)])

    def _invalido(e: Exception) -> HTTPException:
        errores = getattr(e, "errores", None) or [str(e)]
        return HTTPException(status_code=422, detail={"errores": errores})

    def _cambio(request: Request, accion: str, claves: list[str]) -> None:
        registrar_admin(request.client.host if request.client else None, accion, claves)
        if al_cambiar is not None:
            al_cambiar()

    @router.get("/personalidad")
    def leer_personalidad():
        return resumen_admin()

    @router.put("/personalidad")
    def cambiar_personalidad(request: Request, cambios: dict = Body(...)):
        try:
            config = actualizar_personalidad(cambios)
        except PersonalidadInvalida as e:
            raise _invalido(e) from e
        _cambio(request, "personalidad", list(cambios))
        return config.model_dump(mode="json")

    @router.post("/personalidad/vista-previa")
    def vista_previa(cuerpo: dict = Body(default={})):
        try:
            return probar_tono(cuerpo.get("tono"), cuerpo.get("situacion"))
        except PersonalidadInvalida as e:
            raise _invalido(e) from e

    @router.get("/avatares")
    def avatares():
        return resumen_admin()["avatares"]

    @router.post("/avatares")
    def subir_avatar(request: Request, cuerpo: dict = Body(...)):
        import json

        nombre, definicion = cuerpo.get("nombre"), cuerpo.get("definicion")
        if not isinstance(nombre, str) or not isinstance(definicion, (dict, str)):
            raise HTTPException(status_code=422, detail={"errores": ["se esperaba {nombre, definicion}"]})
        contenido = (definicion if isinstance(definicion, str) else json.dumps(definicion)).encode("utf-8")
        try:
            avatar = importar_avatar_desde(contenido, nombre)
        except AvatarInvalido as e:
            raise _invalido(e) from e
        _cambio(request, "avatar", [nombre])
        return {"nombre": avatar.nombre, "animaciones": list(avatar.animaciones),
                "expresiones": list(avatar.expresiones)}

    @router.get("/estilos")
    def leer_estilos():
        return cargar_estilos()

    @router.put("/estilos")
    def cambiar_estilos(request: Request, cambios: dict = Body(...)):
        try:
            tema = actualizar_estilos(cambios)
        except ValueError as e:
            raise _invalido(e) from e
        _cambio(request, "estilos", list(cambios))
        return tema

    return router


__all__ = ["BLOQUEO_S", "INTENTOS_MAXIMOS", "LIMITE_CUERPO", "crear_router_admin"]
