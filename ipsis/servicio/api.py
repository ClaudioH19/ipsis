"""Transporte HTTP del asistente documental.

La aplicación adapta ``Motor.consultar()`` al contrato HTTP. El contrato
público usa nombres en inglés (``POST /ask`` con ``question`` y
``session_id``; respuesta con ``status``, ``answer``, ``fragments``…); el
motor conserva su contrato interno y aquí se traduce. El pipeline, sus
componentes y sus recursos pertenecen al motor; FastAPI conserva solo el
estado propio de cada instancia de aplicación.
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ipsis import __version__
from ipsis.recursos.mensajes import t
from ipsis.aplicacion.consulta import (
    Motor,
    MotorNoListo,
    MotorSaturado,
    ContinuacionInvalida,
    construir_motor_del_proyecto,
    recargar_presentacion,
)
from ipsis.nucleo.contratos import QueryEngine
from ipsis.aplicacion.modo import ModoServicio, modo_servicio
from ipsis.aplicacion.proyecto import (
    configuracion_asistente,
    interfaz_del_idioma,
    limite_de_peticiones,
    microcopia_del_widget,
)
from ipsis.aplicacion.registro import RegistroConsultas, registro_del_proyecto
from ipsis.nucleo.traza import capturar_traza
from ipsis.servicio.seguridad import (
    NOMBRE_CABECERA_CLAVE_WIDGET,
    LimitadorPeticiones,
    identificador_limitador,
    verificar_clave_widget,
)

_DIR_ESTATICOS = Path(__file__).resolve().parent / "estaticos"
_log = logging.getLogger(__name__)
ConstructorMotor = Callable[[], QueryEngine]


class Filtros(BaseModel):
    version: Optional[str] = None
    document: Optional[str] = None


class PeticionConsulta(BaseModel):
    question: str
    session_id: str
    filters: Filtros = Field(default_factory=Filtros)
    deadline_ms: Optional[int] = Field(default=None, ge=1, le=30000)
    continuation: Optional[str] = Field(default=None, min_length=1, max_length=128)


class CeldaVisual(BaseModel):
    column: int = Field(ge=0)
    column_span: int = Field(default=1, ge=1)
    row_span: int = Field(default=1, ge=1)
    text: str
    offset_start: int = Field(ge=0)
    offset_end: int = Field(ge=0)
    locator: Optional[str] = None


class FilaVisual(BaseModel):
    header: bool = False
    cells: list[CeldaVisual]


class BloqueFuente(BaseModel):
    kind: Literal["heading", "paragraph", "table"]
    text: str
    offset_start: int = Field(ge=0)
    offset_end: int = Field(ge=0)
    columns: Optional[int] = Field(default=None, ge=1)
    rows: list[FilaVisual] = Field(default_factory=list)


class Fragmento(BaseModel):
    chunk_id: str
    doc_title: str
    section: str
    version: str
    page: Optional[int] = None
    offset_start: int
    offset_end: int
    text: str
    score: float
    score_kind: Optional[Literal["reranker_logit", "retrieval_score"]] = None
    doc_id: Optional[str] = None
    source_name: Optional[str] = None
    rank: Optional[int] = None
    match_start: Optional[int] = None
    match_end: Optional[int] = None
    truncated: Optional[bool] = None
    source_blocks: list[BloqueFuente] = Field(default_factory=list)


class Confianza(BaseModel):
    top1: float
    margin: float
    bm25_agreement: Optional[bool] = None


class RespuestaExacta(BaseModel):
    """Tramo literal que responde la pregunta (lo marca el lector QA)."""

    chunk_id: str
    text: str
    offset_start: int
    offset_end: int


class ReferenciaDestacado(BaseModel):
    element_id: str
    cell_id: Optional[str] = None
    offset_start: int
    offset_end: int
    text: str
    locator: str
    role: str


class DestacadoRespuesta(BaseModel):
    """Propuesta del lector, sin certificación de pertinencia o completitud."""

    type: Literal["possible_fragment"] = "possible_fragment"
    references: list[ReferenciaDestacado]


class BloqueRespuesta(BaseModel):
    """Un párrafo de ``answer``. ``passage`` es texto literal del documento;
    ``lead`` y ``message`` son frases fijas del tono."""

    type: Literal["lead", "passage", "message"]
    text: str
    connector: Optional[str] = None
    citation: Optional[str] = None
    chunk_id: Optional[str] = None
    highlights: list[DestacadoRespuesta] = Field(default_factory=list)


class RespuestaConsulta(BaseModel):
    status: Literal["ok", "related", "conversational", "no_answer", "degraded", "saturated"]
    service_level: Literal["normal", "medium", "high"]
    answer: Optional[str]
    response_mode: Optional[Literal["ranked_sources"]] = None
    continuation: Optional[str] = None
    has_more: Optional[bool] = None
    # ``answer`` por párrafos, para pintarlo con estructura: unirlos con una
    # línea en blanco (conector + texto + cita) reproduce ``answer``.
    answer_blocks: list[BloqueRespuesta] = Field(default_factory=list)
    plan: Optional[Literal[
        "definition", "procedure", "requirement", "specific_fact",
        "comparison", "exception", "extractive", "gray_zone",
        "no_answer", "conversational", "clarification",
    ]]
    fragments: list[Fragmento]
    confidence: Confianza
    latency_ms: int
    exact_answer: Optional[RespuestaExacta] = None
    # Solo en ``no_answer`` con la postura proactiva (ADR 0008): lo más parecido
    # que sí está, literal y citado. No responde la pregunta.
    alternatives: list[Fragmento] = Field(default_factory=list)
    # Qué tan segura es: high (directa con lector), medium (directa sin lector),
    # low (relacionado). Ausente si no hay respuesta (abstención, aclaración, saludo).
    confidence_level: Optional[Literal["high", "medium", "low"]] = None
    # Solo en respuestas conversacionales (para el avatar del widget).
    conversational_category: Optional[Literal["greeting", "thanks", "farewell", "capability"]] = None


# Contrato interno del motor → público.
_ESTADOS = {"ok": "ok", "relacionado": "related", "conversacional": "conversational", "sin_respuesta": "no_answer",
            "degradado": "degraded", "saturado": "saturated"}
_NIVELES = {"normal": "normal", "media": "medium", "alta": "high"}
_PLANES = {"definicion": "definition", "procedimiento": "procedure", "requisito": "requirement",
           "dato_puntual": "specific_fact", "comparacion": "comparison", "excepcion": "exception",
           "extractivo": "extractive", "zona_gris": "gray_zone", "sin_respuesta": "no_answer",
           "conversacional": "conversational", "aclaracion": "clarification"}


_BLOQUES = {"encabezado": "lead", "pasaje": "passage", "mensaje": "message"}


def respuesta_publica(contrato: dict) -> dict:
    """``diagnostico["contrato_http"]`` del motor con los nombres del contrato público."""
    def fragmento(f: dict) -> dict:
        salida = {"chunk_id": f["chunk_id"], "doc_title": f["doc_titulo"], "section": f["seccion"],
                "version": f["version"], "page": f.get("pagina"), "offset_start": f["offset_inicio"],
                "offset_end": f["offset_fin"], "text": f["texto"], "score": f["score"]}
        for interno, externo in (("doc_id", "doc_id"), ("rango", "rank"),
                ("archivo_fuente", "source_name"),
                ("offset_coincidencia_inicio", "match_start"), ("offset_coincidencia_fin", "match_end"),
                ("truncado", "truncated"), ("bloques_fuente", "source_blocks")):
            if interno in f:
                salida[externo] = f[interno]
        if "tipo_puntaje" in f:
            salida["score_kind"] = {"logit_reranker": "reranker_logit",
                                    "recuperacion": "retrieval_score"}[f["tipo_puntaje"]]
        return salida

    def bloque(b: dict) -> dict:
        salida = {"type": _BLOQUES[b["tipo"]], "text": b["texto"], "connector": b.get("conector"),
                  "citation": b.get("cita"), "chunk_id": b.get("chunk_id")}
        if b.get("destacados"):
            salida["highlights"] = [{"type": "possible_fragment", "references": [
                {"element_id": r["element_id"], "cell_id": r.get("cell_id"),
                 "offset_start": r["offset_inicio"], "offset_end": r["offset_fin"],
                 "text": r["texto"], "locator": r["localizador"], "role": r["rol"]}
                for r in d["referencias"]]} for d in b["destacados"]]
        return salida

    confianza = contrato.get("confianza") or {}
    bloques = contrato.get("bloques")
    if bloques is None and contrato.get("respuesta"):
        bloques = [{"tipo": "mensaje", "texto": contrato["respuesta"]}]
    publica = {
        "status": _ESTADOS[contrato["estado"]],
        "service_level": _NIVELES[contrato["nivel_servicio"]],
        "answer": contrato.get("respuesta"),
        "answer_blocks": [bloque(b) for b in bloques or []],
        "plan": _PLANES.get(contrato.get("plan"), contrato.get("plan")),
        "fragments": [fragmento(f) for f in contrato.get("fragmentos") or []],
        "confidence": {"top1": confianza.get("top1"), "margin": confianza.get("margen"),
                       "bm25_agreement": confianza.get("acuerdo_bm25")},
        "latency_ms": contrato["latencia_ms"],
    }
    if contrato.get("nivel_confianza"):
        publica["confidence_level"] = {"alta": "high", "media": "medium", "baja": "low"}[contrato["nivel_confianza"]]
    exacta = contrato.get("respuesta_exacta")
    if exacta:
        publica["exact_answer"] = {"chunk_id": exacta["chunk_id"], "text": exacta["texto"],
                                   "offset_start": exacta["offset_inicio"], "offset_end": exacta["offset_fin"]}
    if contrato.get("alternativas"):
        publica["alternatives"] = [fragmento(f) for f in contrato["alternativas"]]
    if contrato.get("categoria_conversacional"):
        publica["conversational_category"] = contrato["categoria_conversacional"]
    if contrato.get("modo_respuesta") == "fuentes_ordenadas":
        publica["response_mode"] = "ranked_sources"
        if "continuation" in contrato:
            publica["continuation"] = contrato["continuation"]
            publica["has_more"] = contrato["has_more"]
    return publica


class ConfigWidget(BaseModel):
    assistant_name: str
    domain_description: str
    greeting: str
    response_mode: Optional[Literal["ranked_sources"]] = None
    preset: str = "classic"
    density: Literal["comfortable", "compact"] = "comfortable"
    citations: Literal["accordion", "list"] = "accordion"  # las citas nunca se ocultan
    show_status_label: bool = True
    # Pasajes del documento justificados (con guiones según ``language``) o alineados al inicio.
    text_align: Literal["start", "justify"] = "justify"
    language: str = "es"  # idioma del asistente: el atributo lang del widget
    interface: dict[str, str] = {}
    # Variantes del tono para welcome, waiting, citations_hint y errores.
    microcopy: dict[str, list[str]] = {}
    # styles.yaml::placement: position, offset_x, offset_y, z_index, size y launcher.
    placement: dict[str, str | int] = {}
    # personality.yaml::avatar efectivo; enabled=false si falta (el widget usa el ícono).
    avatar: dict = {}


@dataclass
class EstadoAplicacion:
    motor: QueryEngine
    constructor_motor: ConstructorMotor | None
    claves_widget: list[str]
    limitador: LimitadorPeticiones
    listo: bool = False
    error_arranque: str | None = None
    abstencion_calibrada: bool = False
    registro: RegistroConsultas | None = None  # None: registro apagado, no se escribe nada
    diagnostico: tuple[float, dict | None] | None = None  # (momento, resumen) que publica /ready
    refrescando_diagnostico: bool = False
    candado_diagnostico: threading.Lock = field(default_factory=threading.Lock, repr=False)
    # Recarga del motor pedida desde /admin (umbrales o reindexado): estado visible en el panel.
    tarea: dict = field(default_factory=lambda: {"state": "idle"})
    candado_recarga: threading.Lock = field(default_factory=threading.Lock, repr=False)


def _construir_motor_produccion() -> QueryEngine:
    return construir_motor_del_proyecto()


def recargar_motor(servicio: EstadoAplicacion, *, reindexar: bool = False) -> None:
    """Cierra el motor, reindexa si se pide y abre uno nuevo (lo corre un hilo).

    El índice local de Qdrant admite un solo cliente: mientras dura, el motor queda
    reemplazado por uno vacío y ``/ask`` responde 503 («no listo»), sin errores.
    El resultado queda en ``servicio.tarea`` para el panel."""
    with servicio.candado_recarga:
        servicio.tarea = {"state": "running", "reindex": reindexar}
        servicio.listo = False
        anterior, servicio.motor = servicio.motor, Motor()
        try:
            anterior.cerrar()
            if reindexar:
                from ipsis.aplicacion.corpus import indexar_proyecto

                indexar_proyecto("documents")
            motor = (servicio.constructor_motor or _construir_motor_produccion)()
            motor.calentar()
            servicio.motor = motor
            servicio.abstencion_calibrada = getattr(motor, "abstencion_calibrada",
                                                    bool(getattr(motor, "politica_abstencion", None)))
            servicio.diagnostico = (time.monotonic(), _calcular_diagnostico())
            servicio.listo, servicio.error_arranque = True, None
            servicio.tarea = {"state": "done", "reindex": reindexar}
        except Exception as exc:  # noqa: BLE001 -- se muestra en el panel y en /ready
            servicio.error_arranque = f"{type(exc).__name__}: {exc}"
            servicio.tarea = {"state": "error", "reindex": reindexar, "message": servicio.error_arranque}


def _estado(request: Request) -> EstadoAplicacion:
    return request.app.state.servicio


def _verificar_seguridad(
    peticion: Request,
    x_rag_widget_key: Optional[str] = Header(default=None, alias=NOMBRE_CABECERA_CLAVE_WIDGET),
) -> None:
    estado = _estado(peticion)
    verificar_clave_widget(x_rag_widget_key, estado.claves_widget)
    ip_cliente = peticion.client.host if peticion.client else None
    identificador = identificador_limitador(x_rag_widget_key, ip_cliente)
    if not estado.limitador.permitir(identificador):
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded, retry in a few seconds",
            headers={"Retry-After": "3"},
        )


class _CORSSinAdmin(CORSMiddleware):
    """CORS para el widget, nunca para ``/admin``: el panel es del mismo origen."""

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/admin"):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


_ESTATICOS = ("/widget.js", "/styles.css", "/avatar.js")


_TTL_DIAGNOSTICO_S = 30.0


def _calcular_diagnostico() -> dict | None:
    from ipsis.aplicacion.diagnostico import ProyectoNoEncontrado, diagnosticar, resumen_para_servicio

    try:
        return resumen_para_servicio(diagnosticar(abrir_indice=False))
    except ProyectoNoEncontrado:
        return None


def _refrescar_diagnostico(servicio) -> None:
    try:
        servicio.diagnostico = (time.monotonic(), _calcular_diagnostico())
    except Exception:  # noqa: BLE001 -- se conserva el último diagnóstico y se reintenta luego
        _log.exception(t("runtime.log_ready"))
    finally:
        servicio.refrescando_diagnostico = False


def _diagnostico_cacheado(servicio) -> dict | None:
    """``resumen_para_servicio`` del proyecto en la carpeta actual, sin hacer esperar a ``/ready``.

    El primero se calcula al arrancar (``lifespan``). Si tiene más de 30 s, se
    devuelve igual y se refresca en segundo plano, una sola vez a la vez: un
    healthcheck con timeout corto nunca paga el diagnóstico (en frío, segundos).
    """
    with servicio.candado_diagnostico:
        if servicio.diagnostico is None:  # sin lifespan (p. ej. una prueba): una vez, en línea
            servicio.diagnostico = (time.monotonic(), _calcular_diagnostico())
        momento, resumen = servicio.diagnostico
        if time.monotonic() - momento >= _TTL_DIAGNOSTICO_S and not servicio.refrescando_diagnostico:
            servicio.refrescando_diagnostico = True
            threading.Thread(target=_refrescar_diagnostico, args=(servicio,), daemon=True).start()
    return resumen


def crear_app(
    motor: QueryEngine | None = None,
    *,
    constructor_motor: ConstructorMotor | None = None,
    modo: ModoServicio | None = None,
) -> FastAPI:
    """Crea una aplicación aislada e inyecta su motor.

    Sin motor explícito, la entrada de producción lo construye al iniciar.
    Antes del lifespan queda un motor vacío que permite probar la capa HTTP
    y resolver conversación sin abrir modelos ni índices. ``modo`` sale de las
    variables de entorno si no se da (``ipsis.aplicacion.modo``).
    """
    modo = modo or modo_servicio()
    cfg_dominio = configuracion_asistente()
    cfg_limite = limite_de_peticiones()
    estado = EstadoAplicacion(
        motor=motor or Motor(),
        constructor_motor=(constructor_motor or _construir_motor_produccion) if motor is None else None,
        claves_widget=list(cfg_dominio.get("claves_widget", [])),
        limitador=LimitadorPeticiones(
            capacidad=cfg_limite["capacidad"],
            tasa_por_segundo=cfg_limite["tasa_por_segundo"],
        ),
        registro=registro_del_proyecto(cfg_dominio),
    )

    @asynccontextmanager
    async def lifespan(aplicacion: FastAPI):
        servicio: EstadoAplicacion = aplicacion.state.servicio
        try:
            if servicio.constructor_motor is not None:
                servicio.motor = servicio.constructor_motor()
            servicio.motor.calentar()
            servicio.abstencion_calibrada = getattr(
                servicio.motor,
                "abstencion_calibrada",
                bool(getattr(servicio.motor, "politica_abstencion", None)),
            )
            # El diagnóstico se calcula aquí, antes de declararse listo: /ready nunca lo espera.
            servicio.diagnostico = (time.monotonic(), _calcular_diagnostico())
            servicio.listo = True
            servicio.error_arranque = None
        except Exception as exc:  # se expone en /ready; el proceso sigue vivo
            servicio.listo = False
            servicio.error_arranque = f"{type(exc).__name__}: {exc}"
        try:
            yield
        finally:
            servicio.motor.cerrar()
            servicio.listo = False

    docs = {} if modo.docs_activos else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    aplicacion = FastAPI(title="ipsis", version=__version__, lifespan=lifespan,
                         license_info={"name": "AGPL-3.0-only", "identifier": "AGPL-3.0-only"},
                         description=t("runtime.api_description", url=modo.fuente), **docs)
    aplicacion.state.servicio = estado
    aplicacion.state.modo = modo
    aplicacion.add_middleware(
        _CORSSinAdmin,
        allow_origins=cfg_dominio.get("cors_origenes", []),
        allow_methods=["*"],
        allow_headers=["*", NOMBRE_CABECERA_CLAVE_WIDGET],
    )

    @aplicacion.middleware("http")
    async def cache_de_estaticos(request: Request, siguiente):
        respuesta = await siguiente(request)
        ruta = request.url.path
        if ruta in _ESTATICOS or ruta.startswith("/admin/panel") or ruta.startswith("/avatars/"):
            if modo.desarrollo:
                respuesta.headers["Cache-Control"] = "no-store"  # los cambios se ven al recargar
            elif request.query_params.get("v"):
                respuesta.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                respuesta.headers["Cache-Control"] = "public, max-age=300"
        return respuesta

    @aplicacion.exception_handler(Exception)
    async def error_interno(request: Request, exc: Exception):
        import uuid

        from fastapi.responses import JSONResponse

        identificador = uuid.uuid4().hex[:12]
        _log.exception("error %s en %s", identificador, request.url.path)
        detalle = f"{type(exc).__name__}: {exc}" if modo.desarrollo else "internal error"
        return JSONResponse(status_code=500, content={"detail": detalle, "id": identificador})

    def _refrescar(servicio: EstadoAplicacion) -> None:
        try:
            recargar_presentacion(servicio.motor)
        except Exception as exc:  # noqa: BLE001 -- un tono roto no tumba el servicio; doctor lo explica
            _log.warning(t("runtime.log_personality", error=exc))

    if modo.admin_activo:
        from ipsis.servicio.admin import crear_router_admin, crear_router_panel

        aplicacion.include_router(crear_router_panel(modo, _DIR_ESTATICOS))
        def _recargar_en_segundo_plano(reindexar: bool) -> bool:
            if estado.tarea.get("state") == "running":
                return False
            estado.tarea = {"state": "running", "reindex": reindexar}
            threading.Thread(target=recargar_motor, args=(estado,), kwargs={"reindexar": reindexar},
                             daemon=True).start()
            return True

        aplicacion.include_router(crear_router_admin(modo, estado.limitador, al_cambiar=lambda: _refrescar(estado),
                                                     servicio=estado, recargar=_recargar_en_segundo_plano))
    for problema in modo.problemas:
        _log.warning(problema)

    @aplicacion.get("/source", include_in_schema=False)
    def fuente():
        """AGPL §13: enlace al código fuente del servicio (``IPSIS_SOURCE_URL``)."""
        from fastapi.responses import RedirectResponse

        return RedirectResponse(modo.fuente, status_code=307)

    @aplicacion.get("/health")
    def health():
        return {"status": "alive", "mode": modo.publico}

    @aplicacion.get("/ready")
    def ready(request: Request):
        """Listo para consultas: el motor cargó y el diagnóstico del proyecto no
        tiene nada bloqueante. ``project`` separa lo que bloquea (con su acción)
        de lo opcional; es ``None`` si el servicio corre fuera de un proyecto."""
        from fastapi.responses import JSONResponse

        servicio = _estado(request)
        proyecto = _diagnostico_cacheado(servicio)
        bloquea = proyecto is not None and not proyecto["ready"]
        if not servicio.listo or bloquea:
            motivo = (servicio.error_arranque or "models/index not loaded yet") if not servicio.listo \
                else "; ".join(f"{b['key']}: {b['message']}" for b in proyecto["blocking"])
            return JSONResponse(status_code=503, content={
                "status": "not_ready", "ready": False, "mode": modo.publico, "detail": f"not ready: {motivo}",
                "project": proyecto})
        motor_activo = servicio.motor
        coleccion = getattr(getattr(motor_activo, "retriever", None), "coleccion", None)
        control = motor_activo.control_admision
        return {
            "status": "ready",
            "ready": True,
            "mode": modo.publico,
            "backend": motor_activo.backend,
            "pipeline": getattr(motor_activo, "pipeline", "v1"),
            "collection": getattr(coleccion, "nombre", motor_activo.backend),
            "n_chunks": motor_activo.n_chunks(),
            "n_inventory_entities": len(motor_activo.inventario_entidades()),
            "calibrated_abstention": servicio.abstencion_calibrada,
            "max_concurrency": control.config.concurrencia_maxima if control is not None else None,
            "project": proyecto,
        }

    @aplicacion.get("/config", response_model=ConfigWidget)
    def configuracion_widget(request: Request):
        from ipsis.aplicacion.estilos import cargar_estilos
        from ipsis.aplicacion.personalidad import config_avatar_publica

        _refrescar(_estado(request))
        from ipsis.aplicacion.widget import citas_presentacion, ubicacion_widget

        from ipsis.aplicacion.widget import presentacion_publica, ubicacion_publica

        dominio = configuracion_asistente()
        idioma = dominio.get("idioma", "es")
        interfaz = interfaz_del_idioma(idioma)
        es_enrutador = getattr(_estado(request).motor, "pipeline", "v1") == "v2"
        microcopy = microcopia_del_widget(idioma, dominio.get("nombre_asistente") or
                                         interfaz.get("default_assistant_name", ""))
        if es_enrutador:
            interfaz = dict(interfaz)
            interfaz["placeholder"] = interfaz["search_placeholder"]
            interfaz["subtitle"] = interfaz["search_subtitle"]
            # El saludo de búsqueda no promete una respuesta única, independientemente del tono.
            microcopy = {**microcopy, "welcome": [interfaz["search_greeting"]]}
        nombre = dominio.get("nombre_asistente") or interfaz.get("default_assistant_name", "")
        estilos = cargar_estilos()
        presentacion = presentacion_publica(estilos)
        return ConfigWidget(
            assistant_name=nombre,
            domain_description=dominio.get("descripcion_dominio") or interfaz.get("default_domain_description", ""),
            greeting=interfaz["search_greeting"] if es_enrutador else
                     _estado(request).motor.respuesta_conversacional("greeting"),
            response_mode="ranked_sources" if es_enrutador else None,
            preset=presentacion["preset"],
            density=presentacion["density"],
            citations=citas_presentacion(presentacion["citations"]),
            show_status_label=presentacion["show_status_label"],
            text_align=presentacion["text_align"],
            language=idioma,
            interface=interfaz,
            microcopy=microcopy,
            placement=ubicacion_publica(ubicacion_widget(estilos)),
            avatar=config_avatar_publica(),
        )

    @aplicacion.get("/avatars/{nombre}.avatar.json")
    def avatar_definicion(nombre: str):
        from ipsis.aplicacion.personalidad import definicion_publica

        try:
            return definicion_publica(nombre)
        except (FileNotFoundError, ValueError) as exc:  # nombre inválido, inexistente o definición rota
            raise HTTPException(status_code=404, detail="avatar not available") from exc

    @aplicacion.get("/widget.js")
    def widget_js():
        return FileResponse(_DIR_ESTATICOS / "widget.js", media_type="application/javascript; charset=utf-8")

    @aplicacion.get("/avatar.js")
    def avatar_js():
        """Motor del avatar (ESM, bajo demanda). Licencias en /avatar.js.LICENSE.txt."""
        return FileResponse(_DIR_ESTATICOS / "avatar.js", media_type="text/javascript; charset=utf-8")

    @aplicacion.get("/avatar.js.LICENSE.txt")
    def avatar_licencia():
        return FileResponse(_DIR_ESTATICOS / "avatar.js.LICENSE.txt", media_type="text/plain; charset=utf-8")

    @aplicacion.get("/styles.css")
    def estilos_css():
        from ipsis.aplicacion.estilos import render_css

        return Response(content=render_css(), media_type="text/css; charset=utf-8")

    @aplicacion.get("/widget/demo.html")
    def widget_demo():
        if not modo.demo_activa:
            raise HTTPException(status_code=404, detail="not available in production (IPSIS_DEMO=1 enables it)")
        import html
        import re
        from ipsis.recursos.mensajes import t

        contenido = (_DIR_ESTATICOS / "demo.html").read_text(encoding="utf-8")
        contenido = re.sub(r"\{\{(\w+)\}\}", lambda m: html.escape(t(f"demo.{m.group(1)}"), quote=True), contenido)
        admin = f'<a href="/admin/panel">{html.escape(t("demo.admin"))}</a>' if modo.admin_activo else ""
        return Response(content=contenido.replace("[[ADMIN_LINK]]", admin), media_type="text/html; charset=utf-8")

    @aplicacion.post(
        "/ask",
        response_model=RespuestaConsulta,
        # exact_answer solo aparece cuando el lector la marcó.
        response_model_exclude_unset=True,
        dependencies=[Depends(_verificar_seguridad)],
    )
    def preguntar(peticion: PeticionConsulta, request: Request) -> RespuestaConsulta:
        servicio = _estado(request)
        _refrescar(servicio)
        with capturar_traza(activo=servicio.registro is not None):
            try:
                if peticion.continuation is not None:
                    continuar = getattr(servicio.motor, "continuar", None)
                    if not callable(continuar):
                        raise HTTPException(status_code=400, detail="engine does not support search continuation")
                    if callable(getattr(servicio.motor, "consultar_con_presupuesto", None)):
                        resultado = continuar(peticion.question, peticion.session_id,
                                              peticion.continuation, deadline_ms=peticion.deadline_ms)
                    else:
                        resultado = continuar(peticion.question, peticion.session_id, peticion.continuation)
                else:
                    consultar = getattr(servicio.motor, "consultar_con_presupuesto", None)
                    if callable(consultar):
                        resultado = consultar(peticion.question, peticion.session_id,
                                              deadline_ms=peticion.deadline_ms)
                    else:
                        resultado = servicio.motor.consultar(peticion.question, peticion.session_id)
                contrato = resultado.contrato_http or resultado.diagnostico["contrato_http"]
                respuesta = RespuestaConsulta.model_validate(respuesta_publica(contrato))
            except Exception as exc:
                if servicio.registro is not None:
                    try:
                        servicio.registro.registrar_error(peticion.question, exc)
                    except (OSError, TypeError, ValueError) as error_registro:
                        _log.warning(t("runtime.log_query_log", error=error_registro))
                if isinstance(exc, ContinuacionInvalida):
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                if isinstance(exc, MotorNoListo):
                    raise HTTPException(status_code=503, detail="service not ready, see /ready") from exc
                if isinstance(exc, MotorSaturado):
                    raise HTTPException(
                        status_code=503,
                        detail="service saturated (concurrency limit reached), retry in a moment",
                        headers={"Retry-After": "1"},
                    ) from exc
                raise
            if servicio.registro is not None:
                try:
                    servicio.registro.registrar(peticion.question, resultado)
                except (OSError, TypeError, ValueError) as exc:  # el registro nunca tumba una respuesta
                    _log.warning(t("runtime.log_query_log", error=exc))
            return respuesta

    return aplicacion


# Entrada compatible para ``uvicorn ipsis.servicio.api:app``.
app = crear_app()


__all__ = [
    "Confianza", "ConfigWidget", "Filtros", "Fragmento", "PeticionConsulta",
    "RespuestaConsulta", "app", "crear_app", "recargar_motor", "respuesta_publica",
]
