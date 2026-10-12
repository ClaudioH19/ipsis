"""Configuración del proyecto y materialización de plantillas globales."""
from __future__ import annotations

from pathlib import Path
import re
import unicodedata
from copy import deepcopy

import yaml

from ipsis.configuracion import rutas
from ipsis.configuracion.archivos import interpretar
from ipsis.configuracion.glosario import a_externo
from ipsis.recursos import leer_plantilla
from ipsis.recursos.mensajes import t
from ipsis.configuracion.esquemas import (
    CONFIG_VERSION,
    migrar_asistente,
    validar_asistente,
    validar_motor,
)

RUTA_PROYECTO = rutas.MOTOR
RUTA_DOMINIO = rutas.ASISTENTE

_DOMINIO_POR_DEFECTO = {
    "config_version": CONFIG_VERSION,
    "nombre_asistente": "Asistente documental",
    "descripcion_dominio": "los documentos cargados",
    "idioma": "es",
    "perfil": "light",
    "cors_origenes": [],
    "claves_widget": [],
}


def slug_coleccion(valor: str) -> str:
    """Devuelve un identificador estable y seguro para una coleccion.

    Se deriva del nombre visible del asistente para que dos proyectos que
    usan el perfil generico no compartan accidentalmente el mismo indice.
    """
    normalizado = unicodedata.normalize("NFKD", valor)
    sin_acentos = "".join(c for c in normalizado if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "_", sin_acentos.lower()).strip("_")
    return slug or "asistente_documental"


def cargar_proyecto(ruta: str = RUTA_PROYECTO) -> dict:
    datos = interpretar(Path(ruta).read_text(encoding="utf-8"), "motor")
    return validar_motor(datos)


def cargar_dominio(ruta: str = RUTA_DOMINIO) -> dict:
    p = Path(ruta)
    if not p.exists():
        return dict(_DOMINIO_POR_DEFECTO)
    # Se migra antes de aplicar los valores por defecto: si no, un archivo
    # antiguo sin config_version recibiría la versión vigente sin migrarse.
    datos = migrar_asistente(interpretar(p.read_text(encoding="utf-8"), "asistente"))
    salida = {**_DOMINIO_POR_DEFECTO, **datos}
    for clave, por_defecto in _DOMINIO_POR_DEFECTO.items():
        if salida.get(clave) is None:
            salida[clave] = list(por_defecto) if isinstance(por_defecto, list) else por_defecto
    return validar_asistente(salida)


def configuracion_efectiva(
    *, ruta_motor: str = RUTA_PROYECTO, ruta_dominio: str = RUTA_DOMINIO
) -> dict:
    """Devuelve el snapshot serializable de configuración resuelta.

    La salida contiene defaults aplicados y separa configuración del motor y
    del dominio. No incluye secretos derivados ni muta los objetos cargados.
    """
    from ipsis.configuracion.personalidad import cargar_personalidad

    motor = deepcopy(cargar_proyecto(ruta_motor))
    dominio = deepcopy(cargar_dominio(ruta_dominio))
    personalidad = cargar_personalidad(Path(ruta_motor).parent.parent).model_dump(mode="json")
    # Con los nombres de los archivos (inglés): es lo que el usuario compara con su configuración.
    return {
        "snapshot_version": 1,
        "config_version": CONFIG_VERSION,
        "engine": a_externo(motor, "motor"),
        "assistant": a_externo(dominio, "asistente"),
        "personality": a_externo(personalidad, "personalidad"),
    }


def guardar_snapshot_configuracion(
    ruta: str = rutas.SNAPSHOT,
    *,
    ruta_motor: str = RUTA_PROYECTO,
    ruta_dominio: str = RUTA_DOMINIO,
) -> str:
    """Persiste un snapshot reproducible y devuelve su ruta."""
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        yaml.safe_dump(
            configuracion_efectiva(ruta_motor=ruta_motor, ruta_dominio=ruta_dominio),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return str(destino)


def config_recuperacion(cfg: dict | None = None, ruta: str = RUTA_PROYECTO, perfil: str | None = None) -> dict:
    """Recuperación efectiva: si ``modelo`` falta, se usa el modelo denso del
    perfil; si el perfil fija un modo de recuperación (``bm25``), manda ese."""
    from ipsis.configuracion.perfiles import perfil_efectivo

    cfg = cfg if cfg is not None else cargar_proyecto(ruta)
    recuperacion = dict(cfg["recuperacion"])
    instalacion = perfil_efectivo(perfil or cargar_dominio().get("perfil", "light"),
                                cfg.get("ajustes_perfil"), ruta_calibracion=None)
    if not recuperacion.get("modelo"):
        recuperacion["modelo"] = instalacion.modelos.denso
    if instalacion.recuperacion_modo:
        recuperacion["modo"] = instalacion.recuperacion_modo
    if recuperacion.get("preparacion", {}).get("modo") == "estructural_v1":
        recuperacion["estrategia_chunking"] = "CH-STRUCT"
        recuperacion["con_header"] = True
        recuperacion["coleccion_base"] += "_estructura1"
        recuperacion["qdrant_path"] = str(Path(recuperacion["qdrant_path"]).with_name(
            Path(recuperacion["qdrant_path"]).name + "-estructura1"))
    return recuperacion


def config_servicio(cfg: dict | None = None, ruta: str = RUTA_PROYECTO) -> dict:
    cfg = cfg if cfg is not None else cargar_proyecto(ruta)
    return cfg.get("servicio", {"concurrencia_maxima": 4})


def config_redaccion(cfg: dict | None = None, ruta: str = RUTA_PROYECTO) -> dict:
    cfg = cfg if cfg is not None else cargar_proyecto(ruta)
    return cfg.get("redaccion", {
        "longitud_maxima_fragmento_chars": 10**9,
        "max_fragmentos_en_respuesta": 2,
        "score_relativo_minimo": 0.6,
        "cita_en_texto": "breve",
        "incluir_apertura": True,
    })


_LIMITE_PETICIONES_POR_DEFECTO = {"capacidad": 100, "tasa_por_segundo": 1.0}


def config_seguridad(cfg: dict | None = None, ruta: str = RUTA_PROYECTO) -> dict:
    try:
        cfg = cfg if cfg is not None else cargar_proyecto(ruta)
    except FileNotFoundError:
        cfg = {}
    limite = cfg.get("seguridad", {}).get(
        "limite_peticiones", _LIMITE_PETICIONES_POR_DEFECTO
    )
    return {"limite_peticiones": {**_LIMITE_PETICIONES_POR_DEFECTO, **limite}}


# `ipsis configure clave=valor`: clave del archivo (inglés) → clave interna.
CLAVES_DOMINIO = {
    "assistant_name": "nombre_asistente", "domain_description": "descripcion_dominio", "language": "idioma",
    "profile": "perfil", "cors_origins": "cors_origenes", "widget_keys": "claves_widget",
    "query_log.enabled": "registro.activo",
    "posture.mode": "postura.modo", "posture.max_alternatives": "postura.max_alternativas",
}
CLAVES_DOMINIO_VALIDAS = set(CLAVES_DOMINIO)
_CLAVES_LISTA_SEPARADA_POR_COMA = {"cors_origenes", "claves_widget"}


def _encabezado_comentarios(ruta: Path) -> str:
    if not ruta.exists():
        return t("runtime.assistant_header")
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True)
    fin = 0
    for linea in lineas:
        if linea.strip() == "" or linea.lstrip().startswith("#"):
            fin += 1
        else:
            break
    return "".join(lineas[:fin])


def _crear_desde_recurso_si_falta(ruta: str, recurso: str, **variables: str) -> bool:
    destino = Path(ruta)
    if destino.exists():
        return False
    texto = leer_plantilla(recurso)
    if variables:
        texto = texto.format(**variables)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return True


def inicializar_personalidad_si_falta(ruta: str = rutas.PERSONALIDAD) -> bool:
    return _crear_desde_recurso_si_falta(ruta, "personality.yaml")


def inicializar_asistente_si_falta(ruta: str = RUTA_DOMINIO) -> bool:
    return _crear_desde_recurso_si_falta(ruta, "assistant.yaml")


def inicializar_proyecto_si_falta(
    coleccion_base: str, ruta: str = RUTA_PROYECTO
) -> bool:
    return _crear_desde_recurso_si_falta(
        ruta, "engine.yaml", coleccion_base=coleccion_base
    )


def inicializar_estilos_si_falta(
    ruta: str = rutas.ESTILOS, origen: str | None = None
) -> bool:
    """Crea el tema editable; ``origen`` se conserva para compatibilidad."""
    destino = Path(ruta)
    if destino.exists():
        return False
    if origen:
        fuente = Path(origen)
        if fuente.exists() and fuente.resolve() != destino.resolve():
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(fuente.read_text(encoding="utf-8"), encoding="utf-8")
            return True
    return _crear_desde_recurso_si_falta(ruta, "styles.yaml")


def inicializar_dominio_si_falta(descripcion_dominio: str, ruta: str = rutas.DOMINIO) -> bool:
    """Crea ``config/domain.yaml`` desde la plantilla si no existe."""
    destino = Path(ruta)
    if destino.exists():
        return False
    texto = leer_plantilla("domain.yaml").replace("{descripcion_dominio}", descripcion_dominio)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return True
