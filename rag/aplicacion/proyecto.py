"""Casos de uso del proyecto: configurar el asistente."""
from __future__ import annotations

from pathlib import Path

import yaml

from rag.configuracion.carga import (
    CLAVES_DOMINIO_VALIDAS,
    RUTA_DOMINIO,
    _CLAVES_LISTA_SEPARADA_POR_COMA,
    _encabezado_comentarios,
    cargar_dominio,
)


def actualizar_dominio(pares: dict[str, str], ruta: str = RUTA_DOMINIO) -> dict:
    desconocidas = set(pares) - CLAVES_DOMINIO_VALIDAS
    if desconocidas:
        raise ValueError(
            f"clave(s) desconocida(s) para 'rag configurar': {sorted(desconocidas)}. "
            f"Válidas: {sorted(CLAVES_DOMINIO_VALIDAS)}"
        )

    ruta_p = Path(ruta)
    nuevo = cargar_dominio(ruta)
    for clave, valor in pares.items():
        if clave in _CLAVES_LISTA_SEPARADA_POR_COMA:
            nuevo[clave] = [v.strip() for v in valor.split(",") if v.strip()]
        else:
            nuevo[clave] = valor

    if "perfil" in pares:
        from rag.configuracion.perfiles import PERFILES_INSTALABLES

        if nuevo["perfil"] not in PERFILES_INSTALABLES:
            raise ValueError(f"perfil desconocido {nuevo['perfil']!r} (disponibles: {list(PERFILES_INSTALABLES)})")

    if "idioma" in pares:
        from rag.lenguaje.paquete import idiomas_disponibles

        if nuevo["idioma"] not in idiomas_disponibles():
            raise ValueError(
                f"no hay paquete de idioma {nuevo['idioma']!r} (disponibles: {idiomas_disponibles()})"
            )

    ruta_p.parent.mkdir(parents=True, exist_ok=True)
    ruta_p.write_text(
        _encabezado_comentarios(ruta_p)
        + yaml.safe_dump(nuevo, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return nuevo


# ---------------------------------------------------------------------------
# rag init y preparación del proyecto activo
# ---------------------------------------------------------------------------
class ProyectoExistente(Exception):
    """``rag init`` sin ``--force`` sobre un proyecto ya inicializado."""


class InicioProyecto:
    """Lo que creó ``inicializar_proyecto`` (para que la CLI lo informe)."""

    def __init__(self, nuevo: dict, creo_motor: bool, creo_dominio: bool, creo_estilos: bool) -> None:
        self.nuevo = nuevo
        self.creo_motor = creo_motor
        self.creo_dominio = creo_dominio
        self.creo_estilos = creo_estilos
        self.ruta_asistente = RUTA_DOMINIO
        from rag.ingesta.catalogo import CATALOGO_PATH

        self.ruta_catalogo = CATALOGO_PATH


def inicializar_proyecto(
    nombre_asistente: str | None = None,
    descripcion_dominio: str | None = None,
    idioma: str | None = None,
    perfil: str | None = None,
    forzar: bool = False,
) -> InicioProyecto:
    """Crea la configuración de un proyecto nuevo y su corpus vacío.

    Lanza ``ProyectoExistente`` si ya hay un ``asistente.yaml`` y no se pide
    ``forzar``, y ``ValueError`` si el idioma o un valor no son válidos.
    """
    from rag.configuracion.carga import (
        inicializar_asistente_si_falta,
        inicializar_dominio_si_falta,
        inicializar_estilos_si_falta,
        inicializar_proyecto_si_falta,
        slug_coleccion,
    )
    from rag.ingesta.catalogo import CATALOGO_PATH, plantilla_catalogo_vacio
    from rag.lenguaje.paquete import idiomas_disponibles

    ruta_dominio = Path(RUTA_DOMINIO)
    if ruta_dominio.exists() and not forzar:
        raise ProyectoExistente(RUTA_DOMINIO)
    if ruta_dominio.exists():
        ruta_dominio.unlink()  # --force: parte de los valores por defecto, no fusiona con lo viejo

    idioma = idioma or "es"
    if idioma not in idiomas_disponibles():
        raise ValueError(f"no hay paquete de idioma {idioma!r}. Disponibles: {', '.join(idiomas_disponibles())}.")

    inicializar_asistente_si_falta()
    nuevo = actualizar_dominio({
        "nombre_asistente": nombre_asistente or "Asistente documental",
        "descripcion_dominio": descripcion_dominio or "los documentos cargados",
        "idioma": idioma,
        "perfil": perfil or "medium",
    })

    Path("documentos").mkdir(parents=True, exist_ok=True)
    ruta_catalogo = Path(CATALOGO_PATH)
    if not ruta_catalogo.exists():
        ruta_catalogo.parent.mkdir(parents=True, exist_ok=True)
        ruta_catalogo.write_text(plantilla_catalogo_vacio(), encoding="utf-8")

    creo_motor = inicializar_proyecto_si_falta(coleccion_base=slug_coleccion(nuevo["nombre_asistente"]))
    creo_dominio = inicializar_dominio_si_falta(descripcion_dominio=nuevo["descripcion_dominio"])
    creo_estilos = inicializar_estilos_si_falta()
    return InicioProyecto(nuevo, creo_motor, creo_dominio, creo_estilos)


def completar_proyecto_existente() -> None:
    """Añade archivos faltantes usando defaults sin sobrescribir personalizaciones."""
    from rag.configuracion.carga import (
        inicializar_dominio_si_falta,
        inicializar_estilos_si_falta,
        inicializar_proyecto_si_falta,
        slug_coleccion,
    )
    from rag.ingesta.catalogo import CATALOGO_PATH, plantilla_catalogo_vacio

    dominio = cargar_dominio()
    inicializar_proyecto_si_falta(
        coleccion_base=slug_coleccion(dominio.get("nombre_asistente", "Asistente documental"))
    )
    inicializar_dominio_si_falta(
        descripcion_dominio=dominio.get("descripcion_dominio", "los documentos cargados")
    )
    inicializar_estilos_si_falta()
    ruta_catalogo = Path(CATALOGO_PATH)
    if not ruta_catalogo.is_file():
        ruta_catalogo.parent.mkdir(parents=True, exist_ok=True)
        ruta_catalogo.write_text(plantilla_catalogo_vacio(), encoding="utf-8")


def guardar_snapshot(salida: str):
    """Configuración efectiva, con defaults resueltos, en ``salida``."""
    from rag.configuracion.carga import guardar_snapshot_configuracion

    return guardar_snapshot_configuracion(salida)


def migrar_proyecto_activo() -> list[str]:
    """Lleva el proyecto del directorio actual a la estructura vigente."""
    from rag.configuracion.migraciones import migrar_proyecto

    return migrar_proyecto()


# ---------------------------------------------------------------------------
# Lecturas que necesita el servicio HTTP
# ---------------------------------------------------------------------------
def configuracion_asistente() -> dict:
    """``configuracion/asistente.yaml`` validado (nombre, idioma, perfil…)."""
    return cargar_dominio()


def limite_de_peticiones() -> dict:
    """``seguridad.limite_peticiones`` de ``configuracion/motor.yaml``."""
    from rag.configuracion.carga import config_seguridad

    return config_seguridad()["limite_peticiones"]


def interfaz_del_idioma(idioma: str) -> dict:
    """Textos de la interfaz del widget en el idioma del proyecto."""
    from rag.lenguaje.paquete import cargar_paquete

    return cargar_paquete(idioma, proyecto=Path.cwd()).interfaz
