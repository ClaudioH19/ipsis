"""Casos de uso del panel ``/admin``: estado del proyecto, umbrales y documentos.

La capa HTTP (``ipsis.servicio.admin``) solo traduce peticiones; aquí está la
lógica, con los mismos archivos que usa la CLI: los umbrales se guardan en
``config/engine.yaml::profile_overrides.default_thresholds`` y los documentos se
cargan como con ``ipsis load``. Las claves públicas van en inglés.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ipsis.recursos.mensajes import t

LIMITE_SUBIDA = 20 * 1024 * 1024  # bytes por archivo


def documentos() -> list[dict]:
    """El catálogo, con lo que el panel muestra de cada documento."""
    from ipsis.ingesta.catalogo import CATALOGO_PATH, cargar_catalogo

    if not Path(CATALOGO_PATH).is_file():
        return []
    return [{"doc_id": e.get("doc_id"), "title": e.get("doc_titulo"), "file": e.get("archivo"),
             "version": e.get("version"), "active": e.get("vigente", True) is not False}
            for e in cargar_catalogo()]


def cargar_subido(nombre: str, contenido: bytes) -> dict:
    """Un archivo subido desde el panel: mismo camino que ``ipsis load``.

    Solo el nombre base (nunca una ruta), una extensión soportada y a lo sumo
    ``LIMITE_SUBIDA`` bytes. Se guarda en una carpeta temporal y se cataloga; no
    reindexa (eso es ``POST /admin/reindex``)."""
    from ipsis.aplicacion.corpus import cargar_documentos
    from ipsis.ingesta.parsear import EXTENSIONES_SOPORTADAS

    base = Path(nombre.replace("\\", "/")).name.strip()
    if not base or base.startswith(".") or Path(base).suffix.lower() not in EXTENSIONES_SOPORTADAS:
        raise ValueError(t("app.upload_type", name=nombre, valid=", ".join(sorted(EXTENSIONES_SOPORTADAS))))
    if not contenido:
        raise ValueError(t("app.upload_empty", name=base))
    if len(contenido) > LIMITE_SUBIDA:
        raise ValueError(t("app.upload_size", name=base, mb=LIMITE_SUBIDA // (1024 * 1024)))
    with tempfile.TemporaryDirectory(prefix="ipsis-subida-") as carpeta:
        ruta = Path(carpeta) / base
        ruta.write_bytes(contenido)
        (resultado,) = cargar_documentos([ruta])
    return {"file": base, "doc_id": resultado.doc_id, "title": resultado.doc_titulo,
            "duplicate": resultado.ya_existia, "rejected": resultado.rechazo,
            "warnings": list(resultado.advertencias)}


def estado() -> dict:
    """Lo que muestra la pestaña Estado: perfil, índice, documentos y el diagnóstico
    de ``ipsis doctor`` (sin abrir el índice)."""
    from ipsis.aplicacion.diagnostico import diagnosticar
    from ipsis.aplicacion.proyecto import resumen_perfil

    perfil = resumen_perfil()
    reporte = diagnosticar(abrir_indice=False)
    return {
        "profile": perfil.perfil,
        "description": perfil.descripcion,
        "p95_budget_ms": perfil.presupuesto_p95_ms,
        "models": perfil.modelos,
        "index": {"state": perfil.indice.estado, "chunks": perfil.indice.n_chunks,
                  "model": perfil.indice.modelo_indice, "required_model": perfil.indice.modelo_requerido},
        "documents": documentos(),
        "doctor": [{"key": c.clave, "name": c.nombre, "level": c.estado.value, "message": c.mensaje,
                    "actions": list(c.acciones)} for c in reporte.chequeos],
    }


__all__ = ["LIMITE_SUBIDA", "cargar_subido", "documentos", "estado"]
