"""Piezas comunes del laboratorio: scorers fieles al motor, candidatos y registro por ejecución.

Los scorers reciben **los mismos ids de token** que produce el tokenizador del motor (``ipsis.modelos.onnx``,
truncado ``longest_first`` a ``max_tokens``), así que cualquier diferencia entre ellos es numérica: exportación o
cuantización, nunca tokenización.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for ruta in (REPO, REPO / "herramientas" / "evaluacion"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

from puntuar_fuera import cargar_candidatos, es_informal, metricas, rango_de  # noqa: E402

SALIDA = REPO / ".cache" / "laboratorio-reranker"

# Revisiones fijadas: el ONNX de onnx-community declara como base BAAI/bge-reranker-v2-m3.
ONNX_ID, ONNX_REV = "onnx-community/bge-reranker-v2-m3-ONNX", "6f5ff65298512715a1e669753bc754d2bc8f367b"
TORCH_ID, TORCH_REV = "BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
# Lo que usa el motor v2 en español (``esquemas.py``: lote_reranker, max_tokens_reranker).
LOTE_MOTOR, MAX_TOKENS_MOTOR = 2, 256

ARCHIVOS_ONNX = {
    "int8": ({"*": "onnx/model_int8.onnx"}, {}),
    "fp32": ({"*": "onnx/model.onnx"}, {"onnx/model.onnx": ("onnx/model.onnx_data",)}),
    "fp16": ({"*": "onnx/model_fp16.onnx"}, {}),
}


def spec_onnx(precision: str, max_tokens: int = MAX_TOKENS_MOTOR):
    """La entrada del catálogo del motor, cambiando solo el archivo ONNX, la revisión y la ventana."""
    from ipsis.modelos.catalogo import obtener

    archivos, externos = ARCHIVOS_ONNX[precision]
    return obtener(ONNX_ID).model_copy(update={
        "archivos_onnx": archivos, "datos_externos": externos, "revision": ONNX_REV, "max_tokens": max_tokens})


def descargar_archivos(spec) -> Path:
    """Archivo por archivo a la caché del motor. ``snapshot_download`` (lo que usa ``ipsis``) no vuelve a bajar
    nada si la carpeta de esa revisión ya existe, aunque los patrones pidan archivos nuevos: con el int8 ya en
    caché, el fp32 nunca llegaba."""
    from huggingface_hub import hf_hub_download

    from ipsis.modelos.descarga import archivos_requeridos, ruta_cache

    rutas = [hf_hub_download(spec.id_hf, archivo, revision=spec.revision, cache_dir=str(ruta_cache()))
             for archivo in archivos_requeridos(spec)]
    return Path(rutas[0]).parents[len(Path(archivos_requeridos(spec)[0]).parts) - 1]


class ScorerOnnx:
    """``RerankerOnnx`` del motor con la precisión pedida; ``lote`` reproduce cómo agrupa el motor."""

    def __init__(self, precision: str = "int8", max_tokens: int = MAX_TOKENS_MOTOR, hilos: int | None = None):
        from ipsis.modelos.reranker import RerankerOnnx

        spec = spec_onnx(precision, max_tokens)
        self.nombre, self.precision, self.max_tokens = f"onnx-{precision}", precision, max_tokens
        self.modelo = RerankerOnnx(spec, carpeta=descargar_archivos(spec), hilos=hilos)

    def ventana(self, max_tokens: int) -> None:
        """Cambia el truncado sin recargar la sesión (C2)."""
        self.max_tokens = max_tokens
        self.modelo.spec = self.modelo.spec.model_copy(update={"max_tokens": max_tokens})

    def codificar(self, pregunta: str, pasajes: list[str]):
        return self.modelo.tokenizar([(pregunta, p) for p in pasajes])

    def puntuar(self, pregunta: str, pasajes: list[str], lote: int = LOTE_MOTOR) -> list[float]:
        self.modelo.lote = lote
        return self.modelo.puntuar(pregunta, pasajes)

    def tokens(self, pregunta: str, pasaje: str) -> dict:
        """Longitud efectiva y si hubo truncado (se compara con la codificación sin límite)."""
        corto = self.modelo.tokenizar([(pregunta, pasaje)])[0]
        largo = self.modelo.tokenizar([(pregunta, pasaje)], max_tokens=1_000_000)[0]
        return {"tokens": sum(corto.attention_mask), "tokens_sin_limite": sum(largo.attention_mask),
                "truncado": sum(largo.attention_mask) > sum(corto.attention_mask)}


class ScorerTorch:
    """El modelo original en PyTorch fp32, alimentado con los ids del tokenizador del motor."""

    def __init__(self, tokenizador_motor: ScorerOnnx, hilos: int | None = None):
        import torch
        from transformers import AutoModelForSequenceClassification

        if hilos:
            torch.set_num_threads(hilos)
        self.torch, self.motor = torch, tokenizador_motor
        self.nombre, self.precision, self.max_tokens = "torch-fp32", "fp32", tokenizador_motor.max_tokens
        self.modelo = AutoModelForSequenceClassification.from_pretrained(
            TORCH_ID, revision=TORCH_REV, dtype=torch.float32).eval()

    def puntuar(self, pregunta: str, pasajes: list[str], lote: int = LOTE_MOTOR) -> list[float]:
        salida = []
        for i in range(0, len(pasajes), lote):
            cod = self.motor.codificar(pregunta, pasajes[i:i + lote])
            ids = self.torch.tensor([c.ids for c in cod], dtype=self.torch.long)
            mascara = self.torch.tensor([c.attention_mask for c in cod], dtype=self.torch.long)
            with self.torch.inference_mode():
                logits = self.modelo(input_ids=ids, attention_mask=mascara).logits
            salida.extend(float(x) for x in logits[:, 0])
        return salida


class ScorerOnnxLocal(ScorerOnnx):
    """Un ONNX exportado por ``afinar.py exportar`` (carpeta con ``onnx/model_int8.onnx``, tokenizador y config)."""

    def __init__(self, carpeta: str | Path, max_tokens: int = MAX_TOKENS_MOTOR, hilos: int | None = None,
                 archivo: str = "onnx/model_int8.onnx"):
        from ipsis.modelos.reranker import RerankerOnnx

        spec = spec_onnx("int8", max_tokens).model_copy(update={"archivos_onnx": {"*": archivo}, "revision": None})
        self.nombre, self.precision, self.max_tokens = f"local:{Path(carpeta).name}", "int8", max_tokens
        self.modelo = RerankerOnnx(spec, carpeta=Path(carpeta), hilos=hilos)


def crear_scorer(nombre: str, max_tokens: int = MAX_TOKENS_MOTOR, hilos: int | None = None, base=None):
    """``onnx-int8``, ``onnx-fp32``, ``onnx-fp16``, ``torch-fp32`` (este necesita un ``base`` ONNX para tokenizar) o
    ``local:<carpeta>`` (una copia afinada y exportada)."""
    if nombre.startswith("local:"):
        return ScorerOnnxLocal(nombre.removeprefix("local:"), max_tokens, hilos)
    if nombre.startswith("onnx-"):
        return ScorerOnnx(nombre.removeprefix("onnx-"), max_tokens, hilos)
    if nombre == "torch-fp32":
        return ScorerTorch(base or ScorerOnnx("int8", max_tokens, hilos), hilos)
    raise ValueError(f"scorer desconocido: {nombre}")


# ---------------------------------------------------------------------------
# Registro por ejecución
# ---------------------------------------------------------------------------
def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def huella(ruta: str | Path) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()[:16]


def entorno(hilos: int | None) -> dict:
    versiones = {}
    for paquete in ("torch", "transformers", "onnxruntime", "tokenizers", "numpy"):
        try:
            versiones[paquete] = __import__(paquete).__version__
        except ImportError:
            versiones[paquete] = None
    return {"commit": _git("rev-parse", "HEAD"), "sucio": bool(_git("status", "--porcelain", "--", "ipsis")),
            "python": platform.python_version(), "sistema": platform.platform(), "cpu": platform.processor(),
            "nucleos": os.cpu_count(), "hilos": hilos, "versiones": versiones}


class Ejecucion:
    """Carpeta ``.cache/laboratorio-reranker/<run_id>/`` con ``run.json`` y los archivos que agregue la etapa."""

    def __init__(self, nombre: str, config: dict, hilos: int | None = None):
        sello = datetime.now().strftime("%Y%m%d-%H%M%S")
        corto = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:6]
        self.run_id = f"{sello}-{nombre}-{corto}"
        self.carpeta = SALIDA / self.run_id
        self.carpeta.mkdir(parents=True, exist_ok=False)
        self.datos = {"run_id": self.run_id, "fecha": datetime.now().isoformat(timespec="seconds"),
                      "config": config, "entorno": entorno(hilos), "inicio": time.time()}

    def guardar(self, nombre: str, contenido) -> Path:
        ruta = self.carpeta / nombre
        if nombre.endswith(".jsonl"):
            ruta.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in contenido), encoding="utf-8")
        else:
            ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return ruta

    def cerrar(self, resumen: dict) -> Path:
        self.datos["duracion_s"] = round(time.time() - self.datos.pop("inicio"), 1)
        self.datos["resumen"] = resumen
        return self.guardar("run.json", self.datos)


__all__ = ["LOTE_MOTOR", "MAX_TOKENS_MOTOR", "SALIDA", "Ejecucion", "ScorerOnnx", "ScorerTorch", "cargar_candidatos",
           "crear_scorer", "es_informal", "huella", "metricas", "rango_de"]
