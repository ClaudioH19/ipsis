"""OCR de las páginas de un PDF que no traen texto (escaneos, fotos de páginas).

Opcional. Requiere el extra ``ipsis[ocr]`` (``pytesseract`` y ``pypdfium2``,
ambos Apache-2.0) y el programa Tesseract con los datos del idioma del
documento. Sin ellos, un PDF escaneado se rechaza como siempre y el mensaje
explica cómo activarlo. ``IPSIS_OCR=off`` lo desactiva aunque esté instalado.

El texto que devuelve el OCR pasa a ser el texto del documento: las citas y
sus offsets se anclan a él, igual que al texto extraído de un PDF digital.
Por eso la carga avisa qué páginas se leyeron así: el OCR puede confundir
letras y conviene revisar esas citas.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from ipsis.recursos.mensajes import t

# Código de idioma de ipsis → datos de Tesseract.
IDIOMAS_TESSERACT = {"es": "spa", "en": "eng", "pt": "por"}
# Resolución a la que se dibuja cada página antes de leerla: 300 ppp es la que
# recomienda Tesseract para texto de cuerpo normal.
RESOLUCION_PPP = 300


def _comando_tesseract() -> str | None:
    """``IPSIS_TESSERACT``, el del PATH o, en Windows, el de la instalación habitual
    (el instalador no lo agrega al PATH)."""
    import shutil
    from pathlib import Path

    if os.environ.get("IPSIS_TESSERACT"):
        return os.environ["IPSIS_TESSERACT"]
    if shutil.which("tesseract"):
        return None  # pytesseract ya lo encuentra
    candidatos = [Path(os.environ.get(base, "")) / "Tesseract-OCR" / "tesseract.exe"
                  for base in ("ProgramFiles", "ProgramFiles(x86)")]
    candidatos.append(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
    return next((str(c) for c in candidatos if c.is_file()), None)


@dataclass(frozen=True)
class MotorOCR:
    idiomas: str  # para Tesseract, p. ej. "spa+eng"


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
    except Exception:  # noqa: BLE001 -- sin el programa, pytesseract falla al invocarlo
        return None, t("core.ocr_missing_tesseract")
    principal = IDIOMAS_TESSERACT.get((idioma or "es").split("-")[0], "eng")
    if principal not in disponibles:
        return None, t("core.ocr_missing_language", language=principal)
    # El inglés como segundo idioma ayuda con siglas y términos técnicos.
    idiomas = principal + ("+eng" if principal != "eng" and "eng" in disponibles else "")
    return MotorOCR(idiomas), ""


def leer_paginas(ruta: str, indices: list[int], motor: MotorOCR) -> dict[int, str]:
    """Texto de las páginas ``indices`` (base 0) de ``ruta``, leído con OCR."""
    import pypdfium2
    import pytesseract

    documento = pypdfium2.PdfDocument(ruta)
    try:
        salida = {}
        for i in indices:
            imagen = documento[i].render(scale=RESOLUCION_PPP / 72).to_pil()
            salida[i] = pytesseract.image_to_string(imagen, lang=motor.idiomas)
        return salida
    finally:
        documento.close()


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


__all__ = ["IDIOMAS_TESSERACT", "MotorOCR", "idioma_del_proyecto", "leer_paginas", "motor_ocr"]
