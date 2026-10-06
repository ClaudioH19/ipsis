"""OCR de las páginas de un PDF que no traen texto (escaneos, fotos de páginas).

Opcional. Requiere el extra ``ipsis[ocr]`` (``pytesseract`` y ``pypdfium2``,
ambos Apache-2.0) y el programa Tesseract con los datos del idioma del
documento. Sin ellos, un PDF escaneado se rechaza como siempre y el mensaje
explica cómo activarlo. ``IPSIS_OCR=off`` lo desactiva aunque esté instalado.

El texto que devuelve el OCR pasa a ser el texto del documento: las citas y
sus offsets se anclan a él, igual que al texto extraído de un PDF digital.
Por eso cada página guarda la **confianza** de Tesseract (0–100, promedio de
sus palabras ponderado por su largo) y la carga avisa qué páginas se leyeron
así y cuáles quedaron con confianza baja.

Dentro de un proyecto, lo leído se guarda en ``.ipsis/ocr``: ``ipsis index``
reutiliza el texto de ``ipsis load`` (mismo texto, mismos offsets, sin volver a
leer) mientras no cambien el archivo, los idiomas ni la versión de Tesseract.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from ipsis.configuracion import rutas
from ipsis.recursos.mensajes import t

# Código de idioma de ipsis → datos de Tesseract.
IDIOMAS_TESSERACT = {"es": "spa", "en": "eng", "pt": "por"}
# Resolución a la que se dibuja cada página antes de leerla: 300 ppp es la que
# recomienda Tesseract para texto de cuerpo normal.
RESOLUCION_PPP = 300
# Bajo esta confianza media, una página se avisa como dudosa.
CONFIANZA_BAJA = 85.0

_progreso: ContextVar[Callable[[str], None] | None] = ContextVar("progreso_ocr", default=None)


@contextmanager
def con_progreso(avisar: Callable[[str], None]) -> Iterator[None]:
    """Mientras dure, el OCR cuenta lo que hace con ``avisar`` (la CLI le pasa ``print``)."""
    token = _progreso.set(avisar)
    try:
        yield
    finally:
        _progreso.reset(token)


def _avisar(texto: str) -> None:
    avisar = _progreso.get()
    if avisar is not None:
        avisar(texto)


@dataclass(frozen=True)
class MotorOCR:
    idiomas: str  # para Tesseract, p. ej. "spa+eng"
    version: str = ""


@dataclass(frozen=True)
class PaginaOCR:
    texto: str
    confianza: float  # 0–100; 0 si no reconoció ninguna palabra

    @property
    def baja(self) -> bool:
        return self.confianza < CONFIANZA_BAJA


def _comando_tesseract() -> str | None:
    """``IPSIS_TESSERACT``, el del PATH o, en Windows, el de la instalación habitual
    (el instalador no lo agrega al PATH)."""
    import shutil

    if os.environ.get("IPSIS_TESSERACT"):
        return os.environ["IPSIS_TESSERACT"]
    if shutil.which("tesseract"):
        return None  # pytesseract ya lo encuentra
    candidatos = [Path(os.environ.get(base, "")) / "Tesseract-OCR" / "tesseract.exe"
                  for base in ("ProgramFiles", "ProgramFiles(x86)")]
    candidatos.append(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
    return next((str(c) for c in candidatos if c.is_file()), None)


def motor_ocr(idioma: str | None) -> tuple[MotorOCR | None, str]:
    """El OCR para ``idioma`` y, si no se puede usar, por qué (un texto para el usuario)."""
    if os.environ.get("IPSIS_OCR", "").strip().lower() in {"off", "0", "no", "false"}:
        return None, t("core.ocr_off")
    try:
        import pypdfium2  # noqa: F401
        import pytesseract
    except ImportError:
        return None, t("core.ocr_missing_extra")
    comando = _comando_tesseract()
    if comando:
        pytesseract.pytesseract.tesseract_cmd = comando
    try:
        disponibles = set(pytesseract.get_languages(config=""))
        version = str(pytesseract.get_tesseract_version())
    except Exception:  # noqa: BLE001 -- sin el programa, pytesseract falla al invocarlo
        return None, t("core.ocr_missing_tesseract")
    principal = IDIOMAS_TESSERACT.get((idioma or "es").split("-")[0], "eng")
    if principal not in disponibles:
        return None, t("core.ocr_missing_language", language=principal)
    # El inglés como segundo idioma ayuda con siglas y términos técnicos.
    idiomas = principal + ("+eng" if principal != "eng" and "eng" in disponibles else "")
    return MotorOCR(idiomas, version), ""


def _leer_imagen(imagen, idiomas: str) -> PaginaOCR:
    """Una sola pasada de Tesseract: el texto (líneas y párrafos como los ve) y la
    confianza media de sus palabras, ponderada por el largo de cada una."""
    import pytesseract

    datos = pytesseract.image_to_data(imagen, lang=idiomas, output_type=pytesseract.Output.DICT)
    parrafos: dict[tuple[int, int], dict[int, list[str]]] = {}
    peso = suma = 0.0
    for i, palabra in enumerate(datos["text"]):
        palabra = (palabra or "").strip()
        if not palabra:
            continue
        clave = (datos["block_num"][i], datos["par_num"][i])
        parrafos.setdefault(clave, {}).setdefault(datos["line_num"][i], []).append(palabra)
        confianza = float(datos["conf"][i])
        if confianza >= 0:
            peso += len(palabra)
            suma += confianza * len(palabra)
    texto = "\n\n".join("\n".join(" ".join(palabras) for _, palabras in sorted(lineas.items()))
                        for _, lineas in sorted(parrafos.items()))
    return PaginaOCR(texto, round(suma / peso, 1) if peso else 0.0)


def _carpeta_cache() -> Path | None:
    """``.ipsis/ocr`` del proyecto del directorio actual (sin proyecto, no se guarda)."""
    return Path(rutas.INTERNO) / "ocr" if Path(rutas.CONFIGURACION).is_dir() else None


def leer_paginas(ruta: str, indices: list[int], motor: MotorOCR) -> dict[int, PaginaOCR]:
    """Las páginas ``indices`` (base 0) de ``ruta`` leídas con OCR, contando el avance."""
    import pypdfium2

    nombre = Path(ruta).name
    huella = hashlib.sha256(Path(ruta).read_bytes()).hexdigest()[:16]
    cache = _carpeta_cache()
    salida: dict[int, PaginaOCR] = {}
    _avisar(t("core.ocr_start", file=nombre, n=len(indices), languages=motor.idiomas))
    documento = None
    try:
        for n, i in enumerate(indices, start=1):
            archivo = cache / f"{huella}_p{i}_{motor.idiomas}_{RESOLUCION_PPP}_{motor.version}.json" if cache else None
            if archivo is not None and archivo.is_file():
                guardado = json.loads(archivo.read_text(encoding="utf-8"))
                salida[i] = PaginaOCR(guardado["texto"], guardado["confianza"])
                origen = t("core.ocr_cached")
            else:
                if documento is None:
                    documento = pypdfium2.PdfDocument(ruta)
                imagen = documento[i].render(scale=RESOLUCION_PPP / 72).to_pil()
                salida[i] = _leer_imagen(imagen, motor.idiomas)
                origen = ""
                if archivo is not None:
                    archivo.parent.mkdir(parents=True, exist_ok=True)
                    archivo.write_text(json.dumps({"texto": salida[i].texto, "confianza": salida[i].confianza},
                                                  ensure_ascii=False), encoding="utf-8")
            _avisar(t("core.ocr_page", page=i + 1, i=n, n=len(indices), confidence=f"{salida[i].confianza:.0f}",
                      note=t("core.ocr_page_low") if salida[i].baja else "", source=origen))
    finally:
        if documento is not None:
            documento.close()
    return salida


def idioma_del_proyecto() -> str | None:
    """El idioma activo o, al cargar fuera de una consulta, el de ``config/assistant.yaml``."""
    from ipsis.lenguaje.entidades import idioma_activo

    paquete = idioma_activo()
    if paquete is not None:
        return paquete.codigo
    try:
        from ipsis.configuracion.carga import cargar_dominio

        return cargar_dominio().get("idioma")
    except Exception:  # noqa: BLE001 -- sin proyecto, el idioma por defecto
        return None


__all__ = ["CONFIANZA_BAJA", "IDIOMAS_TESSERACT", "MotorOCR", "PaginaOCR", "con_progreso", "idioma_del_proyecto",
           "leer_paginas", "motor_ocr"]
