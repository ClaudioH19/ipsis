"""Descarga de modelos a una caché global y uso sin red.

La caché es común a todos los proyectos del usuario (``RAG_MODELOS_DIR`` o
``~/.cache/rag-extractivo/modelos``) y usa el formato de ``huggingface_hub``.
Con ``HF_HUB_OFFLINE=1`` nunca se intenta acceder a la red.
"""
from __future__ import annotations

import os
from pathlib import Path

from rag.modelos.catalogo import ModeloSpec


def ruta_cache() -> Path:
    elegido = os.environ.get("RAG_MODELOS_DIR")
    return Path(elegido) if elegido else Path.home() / ".cache" / "rag-extractivo" / "modelos"


def _snapshot(spec: ModeloSpec, *, solo_local: bool) -> Path:
    from huggingface_hub import snapshot_download

    carpeta = snapshot_download(
        repo_id=spec.id_hf,
        allow_patterns=spec.patrones(),
        cache_dir=str(ruta_cache()),
        local_files_only=solo_local,
    )
    return Path(carpeta)


class ErrorDescarga(RuntimeError):
    """No se pudo descargar un modelo; el mensaje dice qué hacer."""


def _sin_red() -> bool:
    return os.environ.get("HF_HUB_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}


def archivos_requeridos(spec: ModeloSpec) -> list[str]:
    """Lo que debe estar en la carpeta para usar el modelo (``*_data`` es opcional)."""
    return [spec.archivo_onnx(), *spec.archivos_extra]


def faltantes(spec: ModeloSpec, carpeta: Path) -> list[str]:
    return [archivo for archivo in archivos_requeridos(spec) if not (carpeta / archivo).is_file()]


def descargar(spec: ModeloSpec) -> Path:
    """Descarga (o reutiliza) los archivos del modelo y devuelve su carpeta."""
    try:
        carpeta = _snapshot(spec, solo_local=False)
    except Exception as exc:  # noqa: BLE001 -- el error de huggingface_hub varía por versión
        if _sin_red():
            raise ErrorDescarga(
                f"{spec.id_hf} no está en la caché ({ruta_cache()}) y HF_HUB_OFFLINE=1 impide descargarlo. "
                "Quita HF_HUB_OFFLINE, o descarga en una máquina con red y copia la caché (RAG_MODELOS_DIR)."
            ) from exc
        raise ErrorDescarga(f"no se pudo descargar {spec.id_hf}: {exc}") from exc
    if faltan := faltantes(spec, carpeta):
        raise ErrorDescarga(f"la descarga de {spec.id_hf} no trajo {', '.join(faltan)}")
    return carpeta


def ruta_local(spec: ModeloSpec) -> Path:
    """Carpeta del modelo en caché; falla con un mensaje accionable si falta."""
    try:
        carpeta = _snapshot(spec, solo_local=True)
    except Exception as exc:  # noqa: BLE001 -- el error de huggingface_hub varía por versión
        raise FileNotFoundError(
            f"el modelo {spec.id_hf} no está en la caché ({ruta_cache()}). "
            f"Ejecuta 'rag modelos descargar'."
        ) from exc
    if faltan := faltantes(spec, carpeta):
        raise FileNotFoundError(
            f"falta {', '.join(faltan)} de {spec.id_hf} en la caché. Ejecuta 'rag modelos descargar'."
        )
    return carpeta


def esta_en_cache(spec: ModeloSpec) -> bool:
    try:
        ruta_local(spec)
    except FileNotFoundError:
        return False
    return True


def tamano_en_disco(spec: ModeloSpec, carpeta: Path) -> int:
    """Bytes que ocupan los archivos del modelo (sigue los enlaces de la caché)."""
    archivos = [carpeta / a for a in archivos_requeridos(spec)] + [carpeta / (spec.archivo_onnx() + "_data")]
    return sum(a.stat().st_size for a in archivos if a.is_file())


__all__ = ["ErrorDescarga", "archivos_requeridos", "descargar", "esta_en_cache", "faltantes", "ruta_cache",
           "ruta_local", "tamano_en_disco"]
