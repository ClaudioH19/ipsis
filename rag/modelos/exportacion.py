"""Exportar un modelo de Hugging Face a ONNX (solo desarrollo, extra ``[exportar]``).

Usa ``optimum`` (que necesita ``torch``) y, con ``int8``, la cuantización
dinámica post-entrenamiento de onnxruntime. Nada de esto se importa fuera de
este flujo: la producción corre sin torch. El resultado queda en una carpeta
de desarrollo; no se registra en el catálogo ni toca la caché de modelos.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

DEPENDENCIAS = ("optimum", "torch")
CARPETA = Path("exportados")


class ExportacionNoDisponible(RuntimeError):
    """Faltan las dependencias del extra ``[exportar]``."""

    def __init__(self, faltantes: list[str], instalar: str) -> None:
        super().__init__(f"faltan {', '.join(faltantes)}")
        self.faltantes = faltantes
        self.instalar = instalar


class ExportacionFallida(RuntimeError):
    """La conversión empezó y falló (versiones incompatibles, repositorio inexistente, red...)."""


@dataclass(frozen=True)
class Exportado:
    carpeta: Path
    onnx: Path
    int8: Path | None


def comando_instalacion() -> str:
    """``pip install`` del extra, con el nombre de distribución instalado."""
    from importlib.metadata import packages_distributions

    nombre = (packages_distributions().get("rag") or ["rag-extractivo"])[0]
    return f'pip install "{nombre}[exportar]"'


def dependencias_faltantes() -> list[str]:
    return [modulo for modulo in DEPENDENCIAS if importlib.util.find_spec(modulo) is None]


def carpeta_salida(id_hf: str) -> Path:
    return CARPETA / id_hf.replace("/", "--")


def _convertir(id_hf: str, salida: Path) -> None:
    from optimum.exporters.onnx import main_export

    main_export(id_hf, output=salida, task="auto")


def _cuantizar(origen: Path, destino: Path) -> None:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(str(origen), str(destino), weight_type=QuantType.QInt8)


def exportar(id_hf: str, int8: bool = False) -> Exportado:
    """Convierte ``id_hf`` a ``exportados/<org>--<modelo>/model.onnx`` (y ``model_int8.onnx``)."""
    if faltan := dependencias_faltantes():
        raise ExportacionNoDisponible(faltan, comando_instalacion())
    salida = carpeta_salida(id_hf)
    if salida.exists():
        raise FileExistsError(f"{salida} ya existe; bórrala o muévela antes de exportar de nuevo")
    onnx = salida / "model.onnx"
    cuantizado = salida / "model_int8.onnx" if int8 else None
    try:
        _convertir(id_hf, salida)
        if not onnx.is_file():
            raise FileNotFoundError(f"la exportación no produjo {onnx}")
        if cuantizado is not None:
            _cuantizar(onnx, cuantizado)
    except Exception as exc:  # noqa: BLE001 -- optimum, transformers y la red lanzan tipos propios
        import shutil

        shutil.rmtree(salida, ignore_errors=True)  # no deja una carpeta a medias que bloquee el reintento
        raise ExportacionFallida(f"{type(exc).__name__}: {exc}") from exc
    return Exportado(salida, onnx, cuantizado)


__all__ = ["ExportacionFallida", "ExportacionNoDisponible", "Exportado", "carpeta_salida", "comando_instalacion",
           "dependencias_faltantes", "exportar"]
