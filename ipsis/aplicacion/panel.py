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


def _umbrales_externos() -> dict[str, str]:
    """Nombre interno de cada umbral → su nombre en ``engine.yaml``."""
    from ipsis.configuracion.glosario import UMBRALES

    return {interno: clave.externa for interno, clave in UMBRALES.items()}


def umbrales(efectivos: dict[str, float] | None = None) -> list[dict]:
    """Cada umbral con su valor efectivo, el del perfil y el del proyecto, y de dónde
    sale: ``calibration`` (``config/calibration.yaml`` aplicada), ``project``
    (``profile_overrides``) o ``profile``. ``efectivos`` son los de la política del
    motor en ejecución (ya con la calibración); sin ellos, perfil + proyecto."""
    from ipsis.aplicacion.proyecto import perfil_de_instalacion
    from ipsis.configuracion.carga import cargar_dominio
    from ipsis.configuracion.perfiles import perfil_efectivo

    nombre = cargar_dominio().get("perfil", "light")
    base = perfil_efectivo(nombre, None, ruta_calibracion=None).umbrales_por_defecto
    proyecto = perfil_de_instalacion(nombre).umbrales_por_defecto
    efectivos = efectivos or proyecto
    filas = []
    for interno, externo in _umbrales_externos().items():
        if interno not in base and interno not in proyecto and interno not in efectivos:
            continue
        valor = efectivos.get(interno, proyecto.get(interno))
        if valor is not None and valor != proyecto.get(interno):
            origen = "calibration"
        elif proyecto.get(interno) != base.get(interno):
            origen = "project"
        else:
            origen = "profile"
        filas.append({"key": externo, "value": valor, "profile": base.get(interno), "project": proyecto.get(interno),
                      "source": origen})
    return filas


def cambiar_umbrales(cambios: dict[str, float | None]) -> list[dict]:
    """Escribe los umbrales del proyecto (``None`` quita el ajuste y vuelve al perfil).

    Valida nombres (los de ``engine.yaml``) y valores en [0, 1], y que el perfil
    resultante sea válido antes de escribir. Una calibración aplicada sigue
    teniendo precedencia sobre ``ok``, ``oov_ok`` y ``focus``."""
    from ipsis.configuracion import rutas
    from ipsis.configuracion.archivos import escribir, leer
    from ipsis.configuracion.carga import _encabezado_comentarios, cargar_dominio
    from ipsis.configuracion.perfiles import perfil_efectivo

    por_externo = {externo: interno for interno, externo in _umbrales_externos().items()}
    errores = []
    for clave, valor in cambios.items():
        if clave not in por_externo:
            errores.append(t("app.unknown_threshold", key=clave, valid=sorted(por_externo)))
        elif valor is not None and (isinstance(valor, bool) or not isinstance(valor, (int, float))
                                    or not 0.0 <= float(valor) <= 1.0):
            errores.append(t("app.threshold_range", key=clave, value=valor))
    if errores:
        raise ValueError("; ".join(errores))
    datos = leer(rutas.MOTOR, "motor")
    ajustes = dict(datos.get("ajustes_perfil") or {})
    actuales = dict(ajustes.get("umbrales_por_defecto") or {})
    for clave, valor in cambios.items():
        if valor is None:
            actuales.pop(por_externo[clave], None)
        else:
            actuales[por_externo[clave]] = float(valor)
    if actuales:
        ajustes["umbrales_por_defecto"] = actuales
    else:
        ajustes.pop("umbrales_por_defecto", None)
    perfil_efectivo(cargar_dominio().get("perfil", "light"), ajustes, ruta_calibracion=None)  # valida
    if ajustes:
        datos["ajustes_perfil"] = ajustes
    else:
        datos.pop("ajustes_perfil", None)
    escribir(rutas.MOTOR, datos, "motor", encabezado=_encabezado_comentarios(Path(rutas.MOTOR)))
    return umbrales()


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


def estado(umbrales_efectivos: dict[str, float] | None = None) -> dict:
    """Lo que muestra la pestaña Estado: perfil, índice, calibración, umbrales,
    documentos y el diagnóstico de ``ipsis doctor`` (sin abrir el índice)."""
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
        "calibration": {"state": perfil.calibracion.estado, "reason": perfil.calibracion.motivo},
        "thresholds": umbrales(umbrales_efectivos),
        "documents": documentos(),
        "doctor": [{"key": c.clave, "name": c.nombre, "level": c.estado.value, "message": c.mensaje,
                    "actions": list(c.acciones)} for c in reporte.chequeos],
    }


__all__ = ["LIMITE_SUBIDA", "cambiar_umbrales", "cargar_subido", "documentos", "estado", "umbrales"]
