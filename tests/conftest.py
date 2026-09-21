"""Fixtures globales basadas únicamente en datos sintéticos."""
from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from rag.dominio import cargar_perfil_generico
from rag.reglas_extraccion import configurar_perfil


@pytest.fixture(scope="session", autouse=True)
def _perfil_generico_de_la_suite():
    configurar_perfil(cargar_perfil_generico())
    yield
    configurar_perfil(None)


@pytest.fixture(scope="session")
def ruta_docx_sintetico(tmp_path_factory: pytest.TempPathFactory) -> Path:
    ruta = tmp_path_factory.mktemp("documentos_sinteticos") / "manual_x100.docx"
    doc = Document()
    doc.add_heading("Manual del Equipo X100", level=1)
    doc.add_paragraph("Documento ficticio creado exclusivamente para las pruebas.")
    doc.add_heading("Operación", level=1)
    doc.add_paragraph("Para encender el equipo X100, mantén presionado el botón verde durante 3 segundos.")
    doc.add_heading("Mantenimiento", level=1)
    doc.add_paragraph("Limpia el filtro cada 30 días, salvo que el entorno tenga mucho polvo.")
    tabla = doc.add_table(rows=2, cols=2)
    tabla.cell(0, 0).text = "Componente"
    tabla.cell(0, 1).text = "Intervalo"
    tabla.cell(1, 0).text = "Filtro"
    tabla.cell(1, 1).text = "30 días"
    doc.save(ruta)
    return ruta
