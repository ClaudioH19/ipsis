"""Casos de uso del corpus: cargar documentos e indexarlos."""
from __future__ import annotations

from pathlib import Path


class ErrorConfiguracion(Exception):
    """La configuración del proyecto no permite indexar (ver ``rag doctor``)."""


def archivos_de_ruta(ruta: Path) -> list[Path]:
    """Archivos soportados de ``ruta`` (un archivo o una carpeta recorrida)."""
    from rag.ingesta.parsear import EXTENSIONES_SOPORTADAS

    if ruta.is_file():
        return [ruta]
    if ruta.is_dir():
        return sorted(
            p for p in ruta.rglob("*")
            if p.is_file()
            and p.suffix.lower() in EXTENSIONES_SOPORTADAS
            and ".rag-extractivo" not in p.relative_to(ruta).parts
        )
    raise FileNotFoundError(f"no existe {ruta}")


def cargar_documentos(archivos: list[Path]):
    """Copia los archivos al corpus y los registra en el catálogo."""
    from rag.ingesta.catalogo import agregar_documentos_al_catalogo

    return agregar_documentos_al_catalogo([str(a) for a in archivos])


def indexar_proyecto(carpeta_corpus: str):
    """Configura idioma y perfil de dominio del proyecto y construye el índice.

    Un problema de configuración se informa como ``ErrorConfiguracion``; un
    fallo de la ingesta se propaga tal cual.
    """
    from rag.configuracion.carga import cargar_dominio, cargar_proyecto, config_recuperacion
    from rag.ingesta.ingesta import ejecutar_ingesta
    from rag.lenguaje.dominio import cargar_perfil
    from rag.lenguaje.entidades import configurar_idioma, configurar_perfil
    from rag.lenguaje.paquete import cargar_paquete

    try:
        dominio = cargar_dominio()
        configurar_perfil(cargar_perfil())
        configurar_idioma(cargar_paquete(dominio.get("idioma", "es"), proyecto=Path.cwd()))
        cfg_rec = config_recuperacion(cargar_proyecto())
    except Exception as e:  # noqa: BLE001 -- se informa como error de configuración
        raise ErrorConfiguracion(str(e)) from e
    return ejecutar_ingesta(carpeta_corpus=carpeta_corpus, cfg_rec=cfg_rec)


__all__ = ["ErrorConfiguracion", "archivos_de_ruta", "cargar_documentos", "indexar_proyecto"]
