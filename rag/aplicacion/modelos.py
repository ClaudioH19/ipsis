"""Casos de uso de ``rag modelos``: listar, descargar, verificar y exportar.

Toda la información de cada modelo sale del catálogo (``rag.modelos.catalogo``)
y del perfil efectivo; la caché, la descarga, la prueba ONNX y la exportación
viven en ``rag.modelos``. Aquí solo se elige qué modelos tocar y se devuelve
un resultado que la CLI pueda imprimir.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rag.modelos.exportacion import ExportacionFallida, ExportacionNoDisponible, Exportado


class SinProyecto(RuntimeError):
    """El comando necesita el perfil activo y no hay proyecto en la carpeta."""


@dataclass(frozen=True)
class EstadoModelo:
    rol: str
    id_hf: str
    licencia: str
    atribucion: str | None
    parametros: int
    archivo: str  # ONNX que corresponde a la CPU actual
    en_cache: bool
    bytes_en_disco: int | None = None


@dataclass(frozen=True)
class ModelosPerfil:
    perfil: str
    modelos: list[EstadoModelo]


@dataclass(frozen=True)
class ModeloDescargado:
    rol: str
    id_hf: str
    estado: str  # "descargado" | "ya_disponible"
    ruta: Path
    licencia: str
    atribucion: str | None


@dataclass(frozen=True)
class ResultadoDescarga:
    perfil: str
    modelos: list[ModeloDescargado]
    cache: Path
    error: str | None = None  # primera descarga que falló; las siguientes no se intentan


@dataclass(frozen=True)
class VerificacionModelo:
    rol: str
    id_hf: str
    archivo: str
    estado: str  # "ok" | "falta" | "no_carga" | "inferencia_fallida"
    mensaje: str | None = None


@dataclass(frozen=True)
class ResultadoVerificacion:
    perfil: str
    modelos: list[VerificacionModelo]

    @property
    def ok(self) -> bool:
        return all(m.estado == "ok" for m in self.modelos)


def _perfil(perfil: str | None):
    """Perfil efectivo pedido (``--perfil``) o el activo del proyecto."""
    from rag.aplicacion.proyecto import perfil_de_instalacion, validar_perfil_instalable
    from rag.configuracion import rutas
    from rag.configuracion.carga import cargar_dominio

    if perfil is None:
        if not Path(rutas.MOTOR).is_file():
            raise SinProyecto("no hay un proyecto en esta carpeta, así que no hay perfil activo")
        perfil = cargar_dominio().get("perfil", "light")
    # Dentro de un proyecto, sus ajustes_perfil pueden cambiar modelos: el mismo perfil que el motor.
    return perfil_de_instalacion(validar_perfil_instalable(perfil))


def _modelos(instalacion):
    """(rol, spec) de los modelos que usa el perfil, sin repetir un mismo repositorio."""
    from rag.modelos.catalogo import obtener

    vistos: dict[str, tuple[str, object]] = {}
    for rol, id_hf in instalacion.modelos.model_dump().items():
        if id_hf and id_hf not in vistos:
            vistos[id_hf] = (rol, obtener(id_hf))
    return list(vistos.values())


def listar_modelos() -> ModelosPerfil:
    """Modelos del perfil activo, con licencia, archivo ONNX y estado de la caché."""
    instalacion = _perfil(None)
    return ModelosPerfil(instalacion.perfil, estado_modelos(instalacion))


def estado_modelos(instalacion) -> list[EstadoModelo]:
    """Estado en caché de cada modelo de un perfil efectivo. Solo mira la caché local:
    no descarga ni carga ONNX (para eso, ``verificar_modelos``)."""
    from rag.modelos.descarga import ruta_local, tamano_en_disco

    estados = []
    for rol, spec in _modelos(instalacion):
        try:
            carpeta = ruta_local(spec)
        except FileNotFoundError:
            carpeta = None
        estados.append(EstadoModelo(
            rol=rol, id_hf=spec.id_hf, licencia=spec.licencia, atribucion=spec.atribucion,
            parametros=spec.parametros, archivo=spec.archivo_onnx(), en_cache=carpeta is not None,
            bytes_en_disco=tamano_en_disco(spec, carpeta) if carpeta is not None else None,
        ))
    return estados


def descargar_modelos(perfil: str | None = None,
                      avisar: Callable[[str, str], None] | None = None) -> ResultadoDescarga:
    """Descarga a la caché global los modelos de ``perfil`` (o del activo) que falten.

    No cambia el perfil activo. ``avisar(rol, id_hf)`` se llama antes de cada
    descarga real, para que la CLI diga qué modelo baja.
    """
    from rag.modelos.descarga import ErrorDescarga, descargar, ruta_cache, ruta_local

    instalacion = _perfil(perfil)
    hechos: list[ModeloDescargado] = []
    for rol, spec in _modelos(instalacion):
        try:
            carpeta, estado = ruta_local(spec), "ya_disponible"
        except FileNotFoundError:
            if avisar:
                avisar(rol, spec.id_hf)
            try:
                carpeta, estado = descargar(spec), "descargado"
            except ErrorDescarga as exc:
                return ResultadoDescarga(instalacion.perfil, hechos, ruta_cache(), str(exc))
        hechos.append(ModeloDescargado(rol, spec.id_hf, estado, carpeta, spec.licencia, spec.atribucion))
    return ResultadoDescarga(instalacion.perfil, hechos, ruta_cache())


def verificar_modelos() -> ResultadoVerificacion:
    """Archivos completos e inferencia mínima de cada modelo del perfil activo; nunca descarga."""
    from rag.modelos.descarga import ruta_local
    from rag.modelos.verificacion import ModeloNoUtilizable, probar

    instalacion = _perfil(None)
    resultados = []
    for rol, spec in _modelos(instalacion):
        archivo = spec.archivo_onnx()
        try:
            probar(spec, ruta_local(spec))
        except FileNotFoundError as exc:
            resultados.append(VerificacionModelo(rol, spec.id_hf, archivo, "falta", str(exc)))
        except ModeloNoUtilizable as exc:
            estado = "no_carga" if exc.etapa == "carga" else "inferencia_fallida"
            resultados.append(VerificacionModelo(rol, spec.id_hf, archivo, estado, str(exc)))
        else:
            resultados.append(VerificacionModelo(rol, spec.id_hf, archivo, "ok"))
    return ResultadoVerificacion(instalacion.perfil, resultados)


def exportar_modelo(id_hf: str, int8: bool = False) -> Exportado:
    """Exporta ``id_hf`` a ONNX en una carpeta de desarrollo; no lo registra en el catálogo."""
    from rag.modelos.exportacion import exportar

    return exportar(id_hf, int8=int8)


__all__ = [
    "EstadoModelo", "ExportacionFallida", "ExportacionNoDisponible", "Exportado", "ModeloDescargado", "ModelosPerfil",
    "ResultadoDescarga", "ResultadoVerificacion", "SinProyecto", "VerificacionModelo",
    "descargar_modelos", "estado_modelos", "exportar_modelo", "listar_modelos", "verificar_modelos",
]
