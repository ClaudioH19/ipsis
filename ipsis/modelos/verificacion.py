"""Prueba mínima de un modelo en caché: carga la sesión ONNX y hace una inferencia corta.

No mide calidad: solo comprueba que el modelo carga, tokeniza, ejecuta en
onnxruntime y devuelve una salida con la forma y los valores que espera su
contrato (vector normalizado, logit finito, lectura válida).
"""
from __future__ import annotations

import math
from pathlib import Path

from ipsis.modelos.catalogo import ModeloSpec

PREGUNTA = "¿Cada cuánto se cambia el filtro?"
PASAJE = "El filtro se cambia cada 6 meses."


class ModeloNoUtilizable(RuntimeError):
    """El modelo está en caché pero no carga (``etapa="carga"``) o su salida no es válida."""

    def __init__(self, etapa: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.etapa = etapa


def _clase(spec: ModeloSpec):
    if spec.tarea == "denso":
        from ipsis.modelos.denso import CodificadorDenso
        return CodificadorDenso
    if spec.tarea == "reranker":
        from ipsis.modelos.reranker import RerankerOnnx
        return RerankerOnnx
    from ipsis.modelos.lector import LectorOnnx
    return LectorOnnx


def _inferir(spec: ModeloSpec, modelo) -> None:
    import numpy as np

    if spec.tarea == "denso":
        vectores = np.asarray(modelo.codificar_consultas([PREGUNTA]))
        if vectores.shape != (1, spec.dimension):
            raise ValueError(f"vector de forma {vectores.shape}, se esperaba (1, {spec.dimension})")
        if not np.all(np.isfinite(vectores)) or abs(float(np.linalg.norm(vectores[0])) - 1.0) > 1e-3:
            raise ValueError("el vector no es finito o no está normalizado")
    elif spec.tarea == "reranker":
        puntajes = modelo.puntuar(PREGUNTA, [PASAJE])
        if len(puntajes) != 1 or not math.isfinite(puntajes[0]):
            raise ValueError(f"puntaje inválido: {puntajes}")
    else:
        lectura = modelo.leer(PREGUNTA, [PASAJE])[0]
        if not (math.isfinite(lectura.prob_respuesta) and math.isfinite(lectura.prob_sin_respuesta)):
            raise ValueError("probabilidades no finitas")


def probar(spec: ModeloSpec, carpeta: Path) -> None:
    """Lanza ``ModeloNoUtilizable`` si el modelo no carga o su inferencia no es válida."""
    modelo = _clase(spec)(spec, carpeta, hilos=1)
    try:
        modelo.sesion  # noqa: B018 -- fuerza la carga para distinguirla de la inferencia
        modelo.tokenizador  # noqa: B018
    except Exception as exc:  # noqa: BLE001 -- onnxruntime y tokenizers lanzan tipos propios
        raise ModeloNoUtilizable("carga", f"{spec.archivo_onnx()} no carga: {exc}") from exc
    try:
        _inferir(spec, modelo)
    except Exception as exc:  # noqa: BLE001
        raise ModeloNoUtilizable("inferencia", f"la inferencia de prueba falló: {exc}") from exc


__all__ = ["ModeloNoUtilizable", "probar"]
