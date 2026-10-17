"""Casos de uso del proyecto: configurar el asistente."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


from ipsis.configuracion import rutas
from ipsis.configuracion.archivos import volcar
from ipsis.configuracion.carga import (
    CLAVES_DOMINIO,
    CLAVES_DOMINIO_VALIDAS,
    RUTA_DOMINIO,
    _CLAVES_LISTA_SEPARADA_POR_COMA,
    _encabezado_comentarios,
    cargar_dominio,
)
from ipsis.recursos.mensajes import t


def resumen_para_terminal() -> str:
    """Perfil e idioma del proyecto, sin abrir el índice ni cargar modelos."""
    dominio = cargar_dominio()
    return f"{dominio.get('perfil', '-')} · {dominio.get('idioma', '-')}"


def _booleano(clave: str, valor: str) -> bool:
    texto = valor.strip().lower()
    if texto in {"true", "si", "sí", "1", "yes", "on"}:
        return True
    if texto in {"false", "no", "0", "off"}:
        return False
    raise ValueError(t("app.expects_boolean", key=clave, value=valor))


def configurar(pares: dict[str, str], ruta: str = RUTA_DOMINIO) -> dict:
    """``ipsis configure key=value``: claves de ``assistant.yaml`` (inglés); devuelve el archivo con esas claves."""
    desconocidas = set(pares) - CLAVES_DOMINIO_VALIDAS
    if desconocidas:
        raise ValueError(t("app.unknown_configure_keys", keys=sorted(desconocidas),
                           valid=sorted(CLAVES_DOMINIO_VALIDAS)))
    from ipsis.configuracion.glosario import a_externo

    return a_externo(actualizar_dominio({CLAVES_DOMINIO[clave]: valor for clave, valor in pares.items()}, ruta),
                     "asistente")


def actualizar_dominio(pares: dict[str, str], ruta: str = RUTA_DOMINIO) -> dict:
    """Cambia ``assistant.yaml`` con claves internas (la usan init, perfil y configurar)."""

    ruta_p = Path(ruta)
    nuevo = cargar_dominio(ruta)
    for clave, valor in pares.items():
        if clave == "registro.activo":
            nuevo["registro"] = {**(nuevo.get("registro") or {}), "activo": _booleano(clave, valor)}
        elif clave == "postura.modo":
            from ipsis.configuracion.glosario import POSTURAS

            interno = {externo: interno for interno, externo in POSTURAS.items()}
            modo = valor.strip().lower()
            if modo not in interno and modo not in POSTURAS:
                raise ValueError(t("app.unknown_posture", value=valor, available=sorted(interno)))
            nuevo["postura"] = {**(nuevo.get("postura") or {}), "modo": interno.get(modo, modo)}
        elif clave == "postura.max_alternativas":
            if not valor.strip().isdigit() or not 1 <= int(valor) <= 5:
                raise ValueError(t("app.posture_alternatives_range", value=valor))
            nuevo["postura"] = {**(nuevo.get("postura") or {}), "max_alternativas": int(valor)}
        elif clave in _CLAVES_LISTA_SEPARADA_POR_COMA:
            nuevo[clave] = [v.strip() for v in valor.split(",") if v.strip()]
        else:
            nuevo[clave] = valor

    if "perfil" in pares:
        from ipsis.configuracion.perfiles import PERFILES_INSTALABLES

        if nuevo["perfil"] not in PERFILES_INSTALABLES:
            raise ValueError(t("app.unknown_profile", name=nuevo["perfil"], available=list(PERFILES_INSTALABLES)))

    if "idioma" in pares:
        from ipsis.lenguaje.paquete import validar_codigo_idioma

        validar_codigo_idioma(nuevo["idioma"])  # sin paquete propio, rige el respaldo

    ruta_p.parent.mkdir(parents=True, exist_ok=True)
    # Temporal + os.replace: un fallo a mitad nunca deja assistant.yaml cortado.
    temporal = ruta_p.with_name(ruta_p.name + ".tmp")
    temporal.write_text(
        _encabezado_comentarios(ruta_p)
        + volcar(nuevo, "asistente"),
        encoding="utf-8",
    )
    os.replace(temporal, ruta_p)
    return nuevo


# ---------------------------------------------------------------------------
# ipsis init y preparación del proyecto activo
# ---------------------------------------------------------------------------
class ProyectoExistente(Exception):
    """``ipsis init`` sin ``--force`` sobre un proyecto ya inicializado."""


class InicioProyecto:
    """Lo que creó ``inicializar_proyecto`` (para que la CLI lo informe)."""

    def __init__(self, nuevo: dict, creo_motor: bool, creo_dominio: bool, creo_estilos: bool) -> None:
        self.nuevo = nuevo
        self.creo_motor = creo_motor
        self.creo_dominio = creo_dominio
        self.creo_estilos = creo_estilos
        self.ruta_asistente = RUTA_DOMINIO
        from ipsis.ingesta.catalogo import CATALOGO_PATH

        self.ruta_catalogo = CATALOGO_PATH


def inicializar_proyecto(
    nombre_asistente: str | None = None,
    descripcion_dominio: str | None = None,
    idioma: str | None = None,
    perfil: str | None = None,
    forzar: bool = False,
) -> InicioProyecto:
    """Crea la configuración de un proyecto nuevo y su corpus vacío.

    Lanza ``ProyectoExistente`` si ya hay un ``assistant.yaml`` y no se pide
    ``forzar``, y ``ValueError`` si el idioma o un valor no son válidos.
    """
    from ipsis.configuracion.carga import (
        inicializar_asistente_si_falta,
        inicializar_dominio_si_falta,
        inicializar_estilos_si_falta,
        inicializar_personalidad_si_falta,
        inicializar_proyecto_si_falta,
        slug_coleccion,
    )
    from ipsis.ingesta.catalogo import CATALOGO_PATH, plantilla_catalogo_vacio
    from ipsis.lenguaje.paquete import validar_codigo_idioma

    ruta_dominio = Path(RUTA_DOMINIO)
    if ruta_dominio.exists() and not forzar:
        raise ProyectoExistente(RUTA_DOMINIO)
    if ruta_dominio.exists():
        ruta_dominio.unlink()  # --force: parte de los valores por defecto, no fusiona con lo viejo

    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.recursos.mensajes import idioma_interfaz

    idioma = validar_codigo_idioma(idioma or idioma_interfaz())
    interfaz = cargar_paquete(idioma).interfaz

    inicializar_asistente_si_falta()
    nuevo = actualizar_dominio({
        "nombre_asistente": nombre_asistente or interfaz["default_assistant_name"],
        "descripcion_dominio": descripcion_dominio or interfaz["default_domain_description"],
        "idioma": idioma,
        "perfil": perfil or "medium",
    })

    Path(rutas.DOCUMENTOS).mkdir(parents=True, exist_ok=True)
    ruta_catalogo = Path(CATALOGO_PATH)
    if not ruta_catalogo.exists():
        ruta_catalogo.parent.mkdir(parents=True, exist_ok=True)
        ruta_catalogo.write_text(plantilla_catalogo_vacio(), encoding="utf-8")

    creo_motor = inicializar_proyecto_si_falta(coleccion_base=slug_coleccion(nuevo["nombre_asistente"]))
    creo_dominio = inicializar_dominio_si_falta(descripcion_dominio=nuevo["descripcion_dominio"])
    creo_estilos = inicializar_estilos_si_falta()
    inicializar_personalidad_si_falta()
    return InicioProyecto(nuevo, creo_motor, creo_dominio, creo_estilos)


def completar_proyecto_existente() -> None:
    """Añade archivos faltantes usando defaults sin sobrescribir personalizaciones."""
    from ipsis.configuracion.carga import (
        inicializar_dominio_si_falta,
        inicializar_estilos_si_falta,
        inicializar_personalidad_si_falta,
        inicializar_proyecto_si_falta,
        slug_coleccion,
    )
    from ipsis.ingesta.catalogo import CATALOGO_PATH, plantilla_catalogo_vacio

    dominio = cargar_dominio()
    inicializar_proyecto_si_falta(
        coleccion_base=slug_coleccion(dominio.get("nombre_asistente", "Asistente documental"))
    )
    inicializar_dominio_si_falta(
        descripcion_dominio=dominio.get("descripcion_dominio", "los documentos cargados")
    )
    inicializar_estilos_si_falta()
    inicializar_personalidad_si_falta()
    ruta_catalogo = Path(CATALOGO_PATH)
    if not ruta_catalogo.is_file():
        ruta_catalogo.parent.mkdir(parents=True, exist_ok=True)
        ruta_catalogo.write_text(plantilla_catalogo_vacio(), encoding="utf-8")


def guardar_snapshot(salida: str):
    """Configuración efectiva, con defaults resueltos, en ``salida``."""
    from ipsis.configuracion.carga import guardar_snapshot_configuracion

    return guardar_snapshot_configuracion(salida)


def carpeta_de_proyecto(carpeta: str | Path) -> bool:
    """Si la carpeta ya es un proyecto (también con la estructura anterior, en español)."""
    carpeta = Path(carpeta)
    marcas = (rutas.ASISTENTE, rutas.CATALOGO, "configuracion/asistente.yaml", "documentos/catalogo.yaml")
    return any((carpeta / marca).is_file() for marca in marcas)


def migrar_proyecto_activo() -> list[str]:
    """Lleva el proyecto del directorio actual a la estructura vigente."""
    from ipsis.configuracion.migraciones import migrar_proyecto

    return migrar_proyecto()


# ---------------------------------------------------------------------------
# Lecturas que necesita el servicio HTTP
# ---------------------------------------------------------------------------
def configuracion_asistente() -> dict:
    """``config/assistant.yaml`` validado (nombre, idioma, perfil…)."""
    return cargar_dominio()


def limite_de_peticiones() -> dict:
    """``seguridad.limite_peticiones`` de ``config/engine.yaml``."""
    from ipsis.configuracion.carga import config_seguridad

    return config_seguridad()["limite_peticiones"]


# Microcopia del widget que ahora es del tono: clave de la interfaz ← situación.
_MICROCOPIA = {"saludo": "welcome", "esperando": "waiting", "error_red": "network_error",
               "error_limite": "rate_limit_error", "error_servicio": "service_error",
               "invitacion_citas": "citations_hint"}


def microcopia_del_widget(idioma: str, nombre_asistente: str) -> dict[str, list[str]]:
    """Variantes del tono activo para los textos del widget (el widget rota entre ellas)."""
    from ipsis.configuracion.personalidad import cargar_personalidad
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.lenguaje.tonos import SITUACIONES, cargar_tono

    paquete = cargar_paquete(idioma, proyecto=Path.cwd())
    tono = cargar_tono(idioma, cargar_personalidad(Path.cwd()).tono.activo, proyecto=Path.cwd(),
                       sobrescrituras=paquete.plantillas_legado)
    return {s: [v.format(assistant_name=nombre_asistente) for v in tono.variantes(s)]
            for s, regla in SITUACIONES.items() if regla.origen == "widget"}


def interfaz_del_idioma(idioma: str) -> dict:
    """Textos de la interfaz del widget: los fijos del idioma más la microcopia del tono."""
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.lenguaje.tonos import cargar_tono

    from ipsis.configuracion.personalidad import cargar_personalidad

    paquete = cargar_paquete(idioma, proyecto=Path.cwd())
    tono = cargar_tono(idioma, cargar_personalidad(Path.cwd()).tono.activo, proyecto=Path.cwd(),
                       sobrescrituras=paquete.plantillas_legado)
    return {**paquete.interfaz, **{s: tono.variantes(s)[0] for s in _MICROCOPIA.values()}}


# ---------------------------------------------------------------------------
# ipsis profile show | cambiar
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
    hash_archivos: str | None = None


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


def idioma_con_respaldo(codigo: str) -> bool:
    """El idioma no tiene paquete propio: rigen las reglas universales y los textos en inglés."""
    from ipsis.lenguaje.paquete import cargar_paquete

    return cargar_paquete(codigo).respaldo


def validar_perfil_instalable(nombre: str) -> str:
    from ipsis.configuracion.perfiles import PERFILES_INSTALABLES

    disponibles = ", ".join(PERFILES_INSTALABLES)
    if nombre in PERFILES_INSTALABLES:
        return nombre
    if nombre == "bm25":
        raise PerfilInvalido(t("app.bm25_not_installable", available=disponibles))
    raise PerfilInvalido(t("app.unknown_profile_long", name=nombre, available=disponibles))


def estado_indice(perfil: str, stemmer: str | None = None) -> EstadoIndice:
    """Si el índice del proyecto sirve para ``perfil``, mirando los manifiestos.

    El perfil abriría la colección de su modelo denso. Si su manifiesto existe
    y es compatible (modelo, dimensión y versión del payload), sirve. Si no,
    pero hay un índice del proyecto construido con otro modelo, es
    incompatible. Si no hay ninguno, no hay índice todavía. Con ``stemmer``
    también se exige el mismo stemmer (el del paquete de idioma activo).
    """
    import json

    from ipsis.configuracion import rutas
    from ipsis.configuracion.carga import cargar_proyecto, config_recuperacion
    from ipsis.indice.manifiesto import ManifiestoIndice, es_compatible, ruta_manifiesto
    from ipsis.indice.qdrant import nombre_coleccion_versionada
    from ipsis.ingesta.indice_media import es_coleccion_media
    from ipsis.modelos.catalogo import obtener

    cfg_rec = config_recuperacion(cargar_proyecto(), perfil=perfil)
    modelo = cfg_rec["modelo"]
    base = cfg_rec["coleccion_base"]
    nombre = nombre_coleccion_versionada(base, modelo, cfg_rec["version_coleccion"])
    propio = ruta_manifiesto(nombre)
    if propio.is_file():
        manifiesto = ManifiestoIndice.model_validate(json.loads(propio.read_text(encoding="utf-8")))
        compatible = es_compatible(manifiesto, modelo, stemmer=stemmer, dimension=obtener(modelo).dimension)
        return EstadoIndice("compatible" if compatible else "incompatible", modelo, manifiesto.modelo_denso,
                            nombre, manifiesto.hash_corpus, manifiesto.stemmer, manifiesto.n_chunks,
                            manifiesto.hash_archivos)
    otros = []
    for ruta in sorted(Path(rutas.INDICE).glob("*.manifest.json")):
        manifiesto = ManifiestoIndice.model_validate(json.loads(ruta.read_text(encoding="utf-8")))
        if manifiesto.coleccion.startswith(base + "_") and not es_coleccion_media(manifiesto.coleccion):
            otros.append(manifiesto)
    if not otros:
        return EstadoIndice("sin_indice", modelo)
    ultimo = max(otros, key=lambda m: m.fecha)
    return EstadoIndice("incompatible", modelo, ultimo.modelo_denso, ultimo.coleccion, ultimo.hash_corpus,
                        ultimo.stemmer, ultimo.n_chunks)


def estado_calibracion(perfil_instalacion, indice: EstadoIndice) -> EstadoCalibracionPerfil:
    """Vigencia de ``config/calibration.yaml`` con la regla del motor
    (``motivo_no_aplicable``): perfil, modelos y corpus del índice compatible."""
    from ipsis.configuracion import rutas
    from ipsis.configuracion.calibracion import EstadoCalibracion, leer_calibracion, motivo_no_aplicable

    archivo = leer_calibracion(rutas.CALIBRACION)
    if archivo is None:
        return EstadoCalibracionPerfil("sin_calibracion")
    hash_corpus = indice.hash_corpus if indice.estado == "compatible" else None
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.lenguaje.sinonimos import huella_lexica
    from ipsis.configuracion.carga import cargar_dominio

    hash_lexico = huella_lexica(cargar_paquete(cargar_dominio().get("idioma", "es"), proyecto=Path.cwd()))
    motivo = motivo_no_aplicable(archivo, perfil=perfil_instalacion.perfil,
                                 modelos=perfil_instalacion.modelos.model_dump(), hash_corpus=hash_corpus,
                                 hash_lexico=hash_lexico)
    if motivo is None:
        return EstadoCalibracionPerfil("vigente")
    if archivo.estado != EstadoCalibracion.CALIBRADO:
        return EstadoCalibracionPerfil("no_habilitada", motivo)
    return EstadoCalibracionPerfil("obsoleta", motivo)


def perfil_de_instalacion(nombre: str):
    """Perfil ``nombre`` con los ``ajustes_perfil`` del proyecto (si hay uno), sin
    calibración: lo que importa para modelos, índice y presupuesto. Valida los
    ajustes (``ValueError`` si no sirven para ese perfil)."""
    from ipsis.configuracion import rutas
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto
    from ipsis.configuracion.perfiles import ajustes_de_idioma, perfil_efectivo

    motor = cargar_proyecto() if Path(rutas.MOTOR).is_file() else {}
    ajustes = motor.get("ajustes_perfil")
    if motor.get("pipeline", "v2") == "v2":  # el reranker propio del idioma es de v2
        ajustes, _ = ajustes_de_idioma(nombre, ajustes, cargar_dominio().get("idioma"))
    return perfil_efectivo(nombre, ajustes, ruta_calibracion=None)


def resumen_perfil() -> ResumenPerfil:
    """Perfil activo, sus modelos y presupuesto, y si el índice y la calibración le sirven."""
    nombre = cargar_dominio().get("perfil", "light")
    instalacion = perfil_de_instalacion(nombre)
    indice = estado_indice(nombre)
    return ResumenPerfil(
        perfil=nombre, descripcion=instalacion.descripcion, presupuesto_p95_ms=instalacion.presupuesto_p95_ms,
        modelos=instalacion.modelos.model_dump(), indice=indice,
        calibracion=estado_calibracion(instalacion, indice),
    )


def cambiar_perfil(destino: str) -> CambioPerfil:
    """Cambia ``assistant.yaml::perfil`` y dice qué consecuencias tiene.

    No descarga modelos, no reindexa, no calibra ni borra nada: el índice y
    ``calibration.yaml`` quedan como estaban (el motor ignora una calibración
    de otra procedencia). Los ``ajustes_perfil`` del proyecto se conservan y se
    validan contra el perfil destino antes de escribir.
    """
    destino = validar_perfil_instalable(destino)
    anterior = cargar_dominio().get("perfil", "light")
    instalacion = perfil_de_instalacion(destino)  # valida los ajustes del proyecto antes de escribir
    if anterior != destino:
        actualizar_dominio({"perfil": destino})
    indice = estado_indice(destino)
    return CambioPerfil(anterior, destino, anterior != destino, indice, estado_calibracion(instalacion, indice))
