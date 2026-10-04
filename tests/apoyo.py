"""Rutas y generadores compartidos por las pruebas.

``tests/`` está en ``pythonpath`` (ver ``pyproject.toml``), así que cualquier
prueba puede hacer ``from apoyo import ...``.
"""
from __future__ import annotations

import io
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[1]
DATOS = RAIZ_REPO / "tests" / "datos"
CORPUS = DATOS / "corpus"
BANCO_SINTETICO = DATOS / "banco" / "manifiesto.json"
CARACTERIZACION = DATOS / "caracterizacion"


def _pdf_pagina_con_texto(texto: str) -> bytes:
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = f"BT /F1 12 Tf 72 700 Td ({texto}) Tj ET".encode("latin-1")
    objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode())
        out.write(body)
        out.write(b"\nendobj\n")
    xref_offset = out.tell()
    n = len(objs) + 1
    out.write(f"xref\n0 {n}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (n, xref_offset))
    return out.getvalue()


def _pdf_pagina_vacia() -> bytes:
    """Una página SIN ningún operador de texto -- simula un PDF escaneado
    (imagen sin capa de texto): `extract_text()` devuelve una cadena vacía."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        b"<< /Length 0 >>\nstream\n\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode())
        out.write(body)
        out.write(b"\nendobj\n")
    xref_offset = out.tell()
    n = len(objs) + 1
    out.write(f"xref\n0 {n}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (n, xref_offset))
    return out.getvalue()


def _combinar_con_outline(paginas: list[bytes], marcadores: list[tuple[str, int]]) -> bytes:
    """Combina PDFs de una página cada uno en un solo documento y agrega
    marcadores (outline) reales con `pypdf.PdfWriter.add_outline_item` --
    genera un outline válido sin escribir su estructura interna a mano."""
    from pypdf import PdfReader, PdfWriter

    w = PdfWriter()
    for pdf_bytes in paginas:
        r = PdfReader(io.BytesIO(pdf_bytes))
        w.add_page(r.pages[0])
    for titulo, num_pagina in marcadores:
        w.add_outline_item(titulo, num_pagina)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PDF con capa de texto, CON outline
# ---------------------------------------------------------------------------


def definicion_avatar(**cambios) -> dict:
    """Definición mínima y válida para la librería (la acepta ``parseAvatarDefinition``)."""
    def expresion(alto: float) -> dict:
        ojo = {"width": 18, "height": alto, "x": 0, "y": -10, "angle": 0}
        return {"head": {"x": 0, "y": 0, "z": 0}, "perspective": 1, "motion": {"eyes": "none", "body": "none"},
                "eyes": {"spacing": 36, "left": dict(ojo), "right": dict(ojo)}}

    parpadeo = {"enabled": True, "initialDelayMs": 1000, "minIntervalMs": 3000, "maxIntervalMs": 6000,
                "durationMs": 150}
    paso = {"expression": "contento", "holdMs": 400, "transitionMs": 100, "transition": "smooth"}
    datos = {"schema": "bible-strong/avatar-definition", "schemaVersion": 1, "name": "Prueba",
             "body": {"primary": {"type": "sphere", "width": 200, "height": 200, "depth": 200, "roundness": 1},
                      "nodes": []},
             "colors": {"body": "#ffffff", "eyes": "#000000"},
             "expressions": {"neutral": expresion(40), "contento": expresion(16)},
             "expressionOrder": ["neutral", "contento"],
             "animations": {"inactivo": {"playbackMode": "loop", "steps": [{**paso, "expression": "neutral"}],
                                         "blink": parpadeo},
                            "contento": {"playbackMode": "once", "steps": [paso], "blink": parpadeo}},
             "animationOrder": ["inactivo", "contento"]}
    datos.update(cambios)
    return datos


def motor_minimo():
    """Motor sin índice con las plantillas del proyecto actual (para probar la API)."""
    from ipsis.configuracion.carga import cargar_dominio
    from ipsis.consulta.etapas.redaccion import cargar_plantillas
    from ipsis.consulta.motor import Motor
    from ipsis.lenguaje.paquete import cargar_paquete

    motor = Motor(plantillas=cargar_plantillas(cargar_paquete("es"), cargar_dominio()), idioma=cargar_paquete("es"))
    from ipsis.aplicacion.consulta import recargar_presentacion

    recargar_presentacion(motor)  # fija la marca inicial, como construir_motor
    return motor
