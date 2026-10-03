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


def descargar(spec: ModeloSpec) -> Path:
    """Descarga (o reutiliza) los archivos del modelo y devuelve su carpeta."""
    carpeta = _snapshot(spec, solo_local=False)
    if not (carpeta / spec.archivo_onnx()).is_file():
        raise FileNotFoundError(f"la descarga de {spec.id_hf} no trajo {spec.archivo_onnx()}")
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
    if not (carpeta / spec.archivo_onnx()).is_file():
        raise FileNotFoundError(
            f"falta {spec.archivo_onnx()} de {spec.id_hf} en la caché. Ejecuta 'rag modelos descargar'."
        )
    return carpeta


def esta_en_cache(spec: ModeloSpec) -> bool:
    try:
        ruta_local(spec)
    except FileNotFoundError:
        return False
    return True


__all__ = ["descargar", "esta_en_cache", "ruta_cache", "ruta_local"]
