"""``ipsis sync``: pone al día el catálogo y el índice cuando cambia la carpeta de documentos."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ipsis.configuracion import rutas


@dataclass
class ResultadoSync:
    plan: object
    agregados: list = field(default_factory=list)
    resumen_indice: object | None = None
    version_anterior: int | None = None
    version_nueva: int | None = None
    podadas: list[str] = field(default_factory=list)
    indexado: bool = False
    media_cambio: bool = False  # las fichas de media/ cambiaron desde el último índice


def subir_version_coleccion(ruta_motor: str = rutas.MOTOR) -> tuple[int, int]:
    """Sube ``collection_version`` en ``config/engine.yaml`` editando solo esa línea (los comentarios se conservan)."""
    ruta = Path(ruta_motor)
    texto = ruta.read_text(encoding="utf-8")
    m = re.search(r"^(\s*(?:collection_version|version_coleccion):[ \t]*)(\d+)([ \t]*(?:#.*)?)$", texto, re.MULTILINE)
    if m is None:
        raise ValueError("config/engine.yaml no declara collection_version")
    antes = int(m.group(2))
    ruta.write_text(texto[:m.start()] + f"{m.group(1)}{antes + 1}{m.group(3)}" + texto[m.end():], encoding="utf-8")
    return antes, antes + 1


def podar_versiones_antiguas(nombre_vigente: str, cfg_rec: dict, directorio: str = rutas.INDICE) -> list[str]:
    """Borra las colecciones de la misma serie con versión menor que la vigente (y sus archivos auxiliares)."""
    m = re.fullmatch(r"(?P<base>.+)_v(?P<n>\d+)(?P<sufijo>__.+)?", nombre_vigente)
    if m is None:
        return []
    carpeta = Path(directorio)
    antiguas = []
    for manifiesto in carpeta.glob("*.manifest.json"):
        nombre = manifiesto.name[:-len(".manifest.json")]
        o = re.fullmatch(r"(?P<base>.+)_v(?P<n>\d+)(?P<sufijo>__.+)?", nombre)
        if o and o["base"] == m["base"] and (o["sufijo"] or "") == (m["sufijo"] or "") and int(o["n"]) < int(m["n"]):
            antiguas.append(nombre)
    if not antiguas:
        return []
    from ipsis.indice.qdrant import crear_cliente_qdrant

    cliente = crear_cliente_qdrant(qdrant_path=cfg_rec["qdrant_path"], modo=None, url_servidor=None)
    try:
        for nombre in antiguas:
            if cliente.collection_exists(nombre):
                cliente.delete_collection(nombre)
            for archivo in carpeta.glob(f"{nombre}.*"):
                archivo.unlink()
    finally:
        cliente.close()
    return sorted(antiguas)


def sincronizar(*, solo_plan: bool = False, indexar: bool = True, forzar: bool = False, podar: bool = False,
                carpeta: str = rutas.DOCUMENTOS) -> ResultadoSync:
    """Compara la carpeta con el catálogo, actualiza el catálogo y reindexa si hizo falta.

    Con la preparación estructural un índice existente no se sobrescribe: se crea uno nuevo en la versión
    siguiente de la colección (``collection_version``) y, con ``podar``, se borran las anteriores."""
    from ipsis.aplicacion.corpus import indexar_proyecto
    from ipsis.configuracion.carga import config_recuperacion
    from ipsis.indice.qdrant import ColeccionExistente
    from ipsis.ingesta import sincronizar as nucleo
    from ipsis.ingesta.indice_media import huella_fichas, media_desactualizado

    plan = nucleo.planificar(carpeta)
    resultado = ResultadoSync(plan=plan)
    # Sin media/ no se lee configuración alguna: ``sync`` sigue funcionando como antes en un proyecto mínimo.
    resultado.media_cambio = huella_fichas() is not None and media_desactualizado(config_recuperacion())
    if solo_plan:
        return resultado
    if plan.hay_cambios:
        resultado.agregados = nucleo.aplicar(plan, carpeta).agregados
    if not indexar or not (plan.hay_cambios or forzar or resultado.media_cambio):
        return resultado
    try:
        resultado.resumen_indice = indexar_proyecto(carpeta)
    except ColeccionExistente:
        resultado.version_anterior, resultado.version_nueva = subir_version_coleccion()
        resultado.resumen_indice = indexar_proyecto(carpeta)
    resultado.indexado = True
    if podar and resultado.resumen_indice is not None:
        cfg = config_recuperacion()
        resultado.podadas = podar_versiones_antiguas(resultado.resumen_indice.nombre_coleccion, cfg)
        media = resultado.resumen_indice.media
        if media is not None and media.nombre_coleccion:  # la serie del carril es aparte: se poda aparte
            resultado.podadas = sorted(resultado.podadas + podar_versiones_antiguas(media.nombre_coleccion, cfg))
    return resultado


__all__ = ["ResultadoSync", "podar_versiones_antiguas", "sincronizar", "subir_version_coleccion"]
