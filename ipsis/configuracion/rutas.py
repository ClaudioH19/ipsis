"""Rutas del proyecto del cliente, relativas a su raíz.

Es la única fuente de verdad sobre dónde vive cada archivo. Ver la estructura
completa en ``docs/guide/configuration.md``.
"""
from __future__ import annotations

CONFIGURACION = "config"
ASISTENTE = "config/assistant.yaml"
MOTOR = "config/engine.yaml"
ESTILOS = "config/styles.yaml"
DOMINIO = "config/domain.yaml"
IDIOMA = "config/language.yaml"
CALIBRACION = "config/calibration.yaml"  # heredado: ya nada lo lee; solo la migración de proyectos antiguos lo reubica
PERSONALIDAD = "config/personality.yaml"
AVATARES = "config/avatars"

DOCUMENTOS = "documents"
CATALOGO = "documents/catalog.yaml"

MEDIA = "media"  # fichas de audio y video (un YAML por ficha)
MEDIA_ARCHIVOS = "media/files"  # archivos locales a los que apuntan las fichas

GOLDEN = "golden"
GOLDEN_BANCO = "golden/bank"
GOLDEN_MANIFIESTO = "golden/bank/manifest.json"
GOLDEN_REPORTES = "golden/reports"

INTERNO = ".ipsis"  # generado; no se versiona
INDICE = ".ipsis/index"
QDRANT = ".ipsis/index/qdrant"
SNAPSHOT = ".ipsis/effective-config.yaml"
REGISTRO_CONSULTAS = ".ipsis/logs/queries.jsonl"
VISTA_PREVIA = ".ipsis/widget-preview.html"
