"""Transporte HTTP del asistente documental.

La aplicación adapta ``Motor.consultar()`` al contrato HTTP V1. El pipeline,
sus componentes y sus recursos pertenecen al motor; FastAPI conserva solo el
estado propio de cada instancia de aplicación.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from rag import __version__
from rag.aplicacion.consulta import Motor, MotorNoListo, MotorSaturado, construir_motor_del_proyecto
from rag.aplicacion.proyecto import (
    configuracion_asistente,
    interfaz_del_idioma,
    limite_de_peticiones,
    microcopia_del_widget,
)
from rag.aplicacion.registro import RegistroConsultas, registro_del_proyecto
from rag.servicio.seguridad import (
    NOMBRE_CABECERA_CLAVE_WIDGET,
    LimitadorPeticiones,
    identificador_limitador,
    verificar_clave_widget,
)

_DIR_ESTATICOS = Path(__file__).resolve().parent / "estaticos"
_log = logging.getLogger(__name__)
ConstructorMotor = Callable[[], Motor]


class Filtros(BaseModel):
    version: Optional[str] = None
    documento: Optional[str] = None


class PeticionConsulta(BaseModel):
    pregunta: str
    id_sesion: str
    filtros: Filtros = Field(default_factory=Filtros)
    deadline_ms: int = 1500


class Fragmento(BaseModel):
    chunk_id: str
    doc_titulo: str
    seccion: str
    version: str
    pagina: Optional[int] = None
    offset_inicio: int
    offset_fin: int
    texto: str
    score: float


class Confianza(BaseModel):
    top1: float
    margen: float
    acuerdo_bm25: Optional[bool] = None


class RespuestaExacta(BaseModel):
    """Tramo literal que responde la pregunta (lo marca el lector QA)."""

    chunk_id: str
    texto: str
    offset_inicio: int
    offset_fin: int


class RespuestaConsulta(BaseModel):
    estado: Literal["ok", "relacionado", "conversacional", "sin_respuesta", "degradado", "saturado"]
    nivel_servicio: Literal["normal", "media", "alta"]
    respuesta: Optional[str]
    plan: Optional[Literal[
        "definicion", "procedimiento", "requisito", "dato_puntual",
        "comparacion", "excepcion", "extractivo", "zona_gris",
        "sin_respuesta", "conversacional",
    ]]
    fragmentos: list[Fragmento]
    confianza: Confianza
    latencia_ms: int
    respuesta_exacta: Optional[RespuestaExacta] = None
    # Solo en respuestas conversacionales (para el avatar del widget).
    categoria_conversacional: Optional[Literal["saludo", "agradecimiento", "despedida", "capacidad"]] = None


class ConfigWidget(BaseModel):
    nombre_asistente: str
    descripcion_dominio: str
    saludo: str
    preset: str = "clasico"
    densidad: Literal["comoda", "compacta"] = "comoda"
    citas: Literal["acordeon", "lista"] = "acordeon"  # las citas nunca se ocultan
    mostrar_etiqueta_estado: bool = True
    interfaz: dict[str, str] = {}
    # Variantes del tono para bienvenida, esperando, invitación a las citas y errores.
    microcopia: dict[str, list[str]] = {}
    # estilos.yaml::ubicacion: posición, desplazamientos, z_index, tamaño y lanzador.
    ubicacion: dict[str, str | int] = {}


@dataclass
class EstadoAplicacion:
    motor: Motor
    constructor_motor: ConstructorMotor | None
    claves_widget: list[str]
    limitador: LimitadorPeticiones
    listo: bool = False
    error_arranque: str | None = None
    abstencion_calibrada: bool = False
    registro: RegistroConsultas | None = None  # None: registro apagado, no se escribe nada


def _construir_motor_produccion() -> Motor:
    return construir_motor_del_proyecto()


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
            detail="límite de peticiones excedido, reintenta en unos segundos",
            headers={"Retry-After": "3"},
        )


def crear_app(
    motor: Motor | None = None,
    *,
    constructor_motor: ConstructorMotor | None = None,
) -> FastAPI:
    """Crea una aplicación aislada e inyecta su motor.

    Sin motor explícito, la entrada de producción lo construye al iniciar.
    Antes del lifespan queda un motor vacío que permite probar la capa HTTP
    y resolver conversación sin abrir modelos ni índices.
    """
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
                servicio.motor.politica_abstencion is not None,
            )
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

    aplicacion = FastAPI(title="rag-extractivo", version=__version__, lifespan=lifespan)
    aplicacion.state.servicio = estado
    aplicacion.add_middleware(
        CORSMiddleware,
        allow_origins=cfg_dominio.get("cors_origenes", []),
        allow_methods=["*"],
        allow_headers=["*", NOMBRE_CABECERA_CLAVE_WIDGET],
    )

    @aplicacion.get("/health")
    def health():
        return {"estado": "vivo"}

    @aplicacion.get("/ready")
    def ready(request: Request):
        servicio = _estado(request)
        if not servicio.listo:
            raise HTTPException(
                status_code=503,
                detail=f"no listo: {servicio.error_arranque or 'modelos/índice todavía no cargados'}",
            )
        motor_activo = servicio.motor
        coleccion = getattr(getattr(motor_activo, "retriever", None), "coleccion", None)
        control = motor_activo.control_admision
        return {
            "estado": "listo",
            "backend": motor_activo.backend,
            "coleccion": getattr(coleccion, "nombre", motor_activo.backend),
            "n_chunks": motor_activo.n_chunks(),
            "n_entidades_inventario": len(motor_activo.inventario_entidades()),
            "abstencion_calibrada": servicio.abstencion_calibrada,
            "concurrencia_maxima": control.config.concurrencia_maxima if control is not None else None,
        }

    @aplicacion.get("/config", response_model=ConfigWidget)
    def configuracion_widget(request: Request):
        from rag.aplicacion.estilos import cargar_estilos
        from rag.aplicacion.widget import citas_presentacion, ubicacion_widget

        dominio = configuracion_asistente()
        idioma = dominio.get("idioma", "es")
        nombre = dominio.get("nombre_asistente", "Asistente documental")
        interfaz = interfaz_del_idioma(idioma)
        estilos = cargar_estilos()
        presentacion = estilos.get("presentacion") or {}
        return ConfigWidget(
            nombre_asistente=nombre,
            descripcion_dominio=dominio.get("descripcion_dominio", "los documentos cargados"),
            saludo=_estado(request).motor.respuesta_conversacional("saludo"),
            preset=str(estilos.get("preset") or "clasico"),
            densidad=presentacion.get("densidad", "comoda"),
            citas=citas_presentacion(presentacion.get("citas")),
            mostrar_etiqueta_estado=presentacion.get("mostrar_etiqueta_estado", True),
            interfaz=interfaz,
            microcopia=microcopia_del_widget(idioma, nombre),
            ubicacion=ubicacion_widget(estilos),
        )

    @aplicacion.get("/widget.js")
    def widget_js():
        return FileResponse(_DIR_ESTATICOS / "widget.js", media_type="application/javascript; charset=utf-8")

    @aplicacion.get("/estilos.css")
    def estilos_css():
        from rag.aplicacion.estilos import render_css

        return Response(content=render_css(), media_type="text/css; charset=utf-8")

    @aplicacion.get("/widget/demo.html")
    def widget_demo():
        return FileResponse(_DIR_ESTATICOS / "demo.html", media_type="text/html; charset=utf-8")

    @aplicacion.post(
        "/consultar",
        response_model=RespuestaConsulta,
        # respuesta_exacta solo aparece cuando el lector la marcó.
        response_model_exclude_unset=True,
        dependencies=[Depends(_verificar_seguridad)],
    )
    def consultar(peticion: PeticionConsulta, request: Request) -> RespuestaConsulta:
        servicio = _estado(request)
        try:
            resultado = servicio.motor.consultar(peticion.pregunta, peticion.id_sesion)
        except MotorNoListo as exc:
            raise HTTPException(status_code=503, detail="servicio no listo, ver /ready") from exc
        except MotorSaturado as exc:
            raise HTTPException(
                status_code=503,
                detail="servicio saturado (límite de concurrencia alcanzado), reintente en un momento",
                headers={"Retry-After": "1"},
            ) from exc
        if servicio.registro is not None:
            try:
                servicio.registro.registrar(peticion.pregunta, resultado)
            except OSError as exc:  # el registro nunca tumba una respuesta
                _log.warning("no se pudo escribir el registro de consultas: %s", exc)
        return RespuestaConsulta.model_validate(resultado.diagnostico["contrato_http"])

    return aplicacion


# Entrada compatible para ``uvicorn rag.servicio.api:app``.
app = crear_app()


__all__ = [
    "Confianza", "ConfigWidget", "Filtros", "Fragmento", "PeticionConsulta",
    "RespuestaConsulta", "app", "crear_app",
]
