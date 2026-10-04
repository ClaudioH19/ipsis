"""Casos de uso del proyecto: configurar el asistente."""
from __future__ import annotations

import os
from dataclasses import dataclass
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
    # Temporal + os.replace: un fallo a mitad nunca deja asistente.yaml cortado.
    temporal = ruta_p.with_name(ruta_p.name + ".tmp")
    temporal.write_text(
        _encabezado_comentarios(ruta_p)
        + yaml.safe_dump(nuevo, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    os.replace(temporal, ruta_p)
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


# ---------------------------------------------------------------------------
# rag perfil mostrar | cambiar
# ---------------------------------------------------------------------------
class PerfilInvalido(ValueError):
    """El perfil pedido no es instalable."""


@dataclass(frozen=True)
class EstadoIndice:
    """``sin_indice``, ``compatible`` o ``incompatible`` para un perfil, según
    los manifiestos del índice (lo que realmente se construyó)."""

    estado: str
    modelo_requerido: str
    modelo_indice: str | None = None  # con qué modelo denso se construyó el índice encontrado
    coleccion: str | None = None
    hash_corpus: str | None = None
    stemmer: str | None = None  # con qué stemmer se construyeron sus estadísticas léxicas
    n_chunks: int | None = None


@dataclass(frozen=True)
class EstadoCalibracionPerfil:
    """``sin_calibracion``, ``vigente``, ``obsoleta`` (procedencia distinta) o
    ``no_habilitada`` (guardada solo para auditoría). Usa la misma regla que el motor."""

    estado: str
    motivo: str | None = None


@dataclass(frozen=True)
class ResumenPerfil:
    perfil: str
    descripcion: str
    presupuesto_p95_ms: int
    modelos: dict
    indice: EstadoIndice
    calibracion: EstadoCalibracionPerfil


@dataclass(frozen=True)
class CambioPerfil:
    anterior: str
    nuevo: str
    cambio_real: bool
    indice: EstadoIndice
    calibracion: EstadoCalibracionPerfil

    @property
    def requiere_reindexar(self) -> bool:
        return self.cambio_real and self.indice.estado == "incompatible"


def validar_perfil_instalable(nombre: str) -> str:
    from rag.configuracion.perfiles import PERFILES_INSTALABLES

    disponibles = ", ".join(PERFILES_INSTALABLES)
    if nombre in PERFILES_INSTALABLES:
        return nombre
    if nombre == "bm25":
        raise PerfilInvalido("bm25 es un perfil de diagnóstico de 'rag benchmark', no un perfil instalable. "
                             f"Perfiles disponibles: {disponibles}")
    raise PerfilInvalido(f"perfil desconocido {nombre!r}. Perfiles disponibles: {disponibles}")


def estado_indice(perfil: str, stemmer: str | None = None) -> EstadoIndice:
    """Si el índice del proyecto sirve para ``perfil``, mirando los manifiestos.

    El perfil abriría la colección de su modelo denso. Si su manifiesto existe
    y es compatible (modelo, dimensión y versión del payload), sirve. Si no,
    pero hay un índice del proyecto construido con otro modelo, es
    incompatible. Si no hay ninguno, no hay índice todavía. Con ``stemmer``
    también se exige el mismo stemmer (el del paquete de idioma activo).
    """
    import json

    from rag.configuracion import rutas
    from rag.configuracion.carga import cargar_proyecto, config_recuperacion
    from rag.indice.manifiesto import ManifiestoIndice, es_compatible, ruta_manifiesto
    from rag.indice.qdrant import nombre_coleccion_versionada
    from rag.modelos.catalogo import obtener

    cfg_rec = config_recuperacion(cargar_proyecto(), perfil=perfil)
    modelo = cfg_rec["modelo"]
    base = cfg_rec["coleccion_base"]
    nombre = nombre_coleccion_versionada(base, modelo, cfg_rec["version_coleccion"])
    propio = ruta_manifiesto(nombre)
    if propio.is_file():
        manifiesto = ManifiestoIndice.model_validate(json.loads(propio.read_text(encoding="utf-8")))
        compatible = es_compatible(manifiesto, modelo, stemmer=stemmer, dimension=obtener(modelo).dimension)
        return EstadoIndice("compatible" if compatible else "incompatible", modelo, manifiesto.modelo_denso,
                            nombre, manifiesto.hash_corpus, manifiesto.stemmer, manifiesto.n_chunks)
    otros = []
    for ruta in sorted(Path(rutas.INDICE).glob("*.manifiesto.json")):
        manifiesto = ManifiestoIndice.model_validate(json.loads(ruta.read_text(encoding="utf-8")))
        if manifiesto.coleccion.startswith(base + "_"):
            otros.append(manifiesto)
    if not otros:
        return EstadoIndice("sin_indice", modelo)
    ultimo = max(otros, key=lambda m: m.fecha)
    return EstadoIndice("incompatible", modelo, ultimo.modelo_denso, ultimo.coleccion, ultimo.hash_corpus,
                        ultimo.stemmer, ultimo.n_chunks)


def estado_calibracion(perfil_instalacion, indice: EstadoIndice) -> EstadoCalibracionPerfil:
    """Vigencia de ``configuracion/calibracion.yaml`` con la regla del motor
    (``motivo_no_aplicable``): perfil, modelos y corpus del índice compatible."""
    from rag.configuracion import rutas
    from rag.configuracion.calibracion import EstadoCalibracion, leer_calibracion, motivo_no_aplicable

    archivo = leer_calibracion(rutas.CALIBRACION)
    if archivo is None:
        return EstadoCalibracionPerfil("sin_calibracion")
    hash_corpus = indice.hash_corpus if indice.estado == "compatible" else None
    motivo = motivo_no_aplicable(archivo, perfil=perfil_instalacion.perfil,
                                 modelos=perfil_instalacion.modelos.model_dump(), hash_corpus=hash_corpus)
    if motivo is None:
        return EstadoCalibracionPerfil("vigente")
    if archivo.estado != EstadoCalibracion.CALIBRADO:
        return EstadoCalibracionPerfil("no_habilitada", motivo)
    return EstadoCalibracionPerfil("obsoleta", motivo)


def _perfil_instalacion(nombre: str):
    from rag.configuracion.carga import cargar_proyecto
    from rag.configuracion.perfiles import perfil_efectivo

    return perfil_efectivo(nombre, cargar_proyecto().get("ajustes_perfil"))


def resumen_perfil() -> ResumenPerfil:
    """Perfil activo, sus modelos y presupuesto, y si el índice y la calibración le sirven."""
    nombre = cargar_dominio().get("perfil", "light")
    instalacion = _perfil_instalacion(nombre)
    indice = estado_indice(nombre)
    return ResumenPerfil(
        perfil=nombre, descripcion=instalacion.descripcion, presupuesto_p95_ms=instalacion.presupuesto_p95_ms,
        modelos=instalacion.modelos.model_dump(), indice=indice,
        calibracion=estado_calibracion(instalacion, indice),
    )


def cambiar_perfil(destino: str) -> CambioPerfil:
    """Cambia ``asistente.yaml::perfil`` y dice qué consecuencias tiene.

    No descarga modelos, no reindexa, no calibra ni borra nada: el índice y
    ``calibracion.yaml`` quedan como estaban (el motor ignora una calibración
    de otra procedencia). Los ``ajustes_perfil`` del proyecto se conservan y se
    validan contra el perfil destino antes de escribir.
    """
    destino = validar_perfil_instalable(destino)
    anterior = cargar_dominio().get("perfil", "light")
    instalacion = _perfil_instalacion(destino)  # valida los ajustes del proyecto antes de escribir
    if anterior != destino:
        actualizar_dominio({"perfil": destino})
    indice = estado_indice(destino)
    return CambioPerfil(anterior, destino, anterior != destino, indice, estado_calibracion(instalacion, indice))
