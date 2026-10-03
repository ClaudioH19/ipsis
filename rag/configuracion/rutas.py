"""Rutas del proyecto del cliente, relativas a su raíz.

Es la única fuente de verdad sobre dónde vive cada archivo. Ver la estructura
completa en ``docs/plan/arquitectura.md`` §1.5.
"""
from __future__ import annotations

CONFIGURACION = "configuracion"
ASISTENTE = "configuracion/asistente.yaml"
MOTOR = "configuracion/motor.yaml"
ESTILOS = "configuracion/estilos.yaml"
DOMINIO = "configuracion/dominio.yaml"
IDIOMA = "configuracion/idioma.yaml"
CALIBRACION = "configuracion/calibracion.yaml"

DOCUMENTOS = "documentos"
CATALOGO = "documentos/catalogo.yaml"

GOLDEN = "golden"
GOLDEN_BANCO = "golden/banco"
GOLDEN_MANIFIESTO = "golden/banco/manifiesto.json"
GOLDEN_REPORTES = "golden/reportes"

INTERNO = ".rag"  # generado; no se versiona
INDICE = ".rag/indice"
QDRANT = ".rag/indice/qdrant"
SNAPSHOT = ".rag/configuracion-efectiva.yaml"
VISTA_PREVIA = ".rag/widget-vista-previa.html"
