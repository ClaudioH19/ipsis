"""Rutas del proyecto del cliente, relativas a su raíz.

Es la única fuente de verdad sobre dónde vive cada archivo. Ver la estructura
completa en ``docs/guia/configuracion.md``.
"""
from __future__ import annotations

CONFIGURACION = "configuracion"
ASISTENTE = "configuracion/asistente.yaml"
MOTOR = "configuracion/motor.yaml"
ESTILOS = "configuracion/estilos.yaml"
DOMINIO = "configuracion/dominio.yaml"
IDIOMA = "configuracion/idioma.yaml"
CALIBRACION = "configuracion/calibracion.yaml"
PERSONALIDAD = "configuracion/personalidad.yaml"
AVATARES = "configuracion/avatares"

DOCUMENTOS = "documentos"
CATALOGO = "documentos/catalogo.yaml"

GOLDEN = "golden"
GOLDEN_BANCO = "golden/banco"
GOLDEN_MANIFIESTO = "golden/banco/manifiesto.json"
GOLDEN_REPORTES = "golden/reportes"

INTERNO = ".ipsis"  # generado; no se versiona
INDICE = ".ipsis/indice"
QDRANT = ".ipsis/indice/qdrant"
SNAPSHOT = ".ipsis/configuracion-efectiva.yaml"
REGISTRO_CONSULTAS = ".ipsis/registros/consultas.jsonl"
VISTA_PREVIA = ".ipsis/widget-vista-previa.html"
