"""Configuración del proyecto y materialización de plantillas globales."""
from __future__ import annotations

from pathlib import Path
import re
import unicodedata
from copy import deepcopy

import yaml

from rag.recursos import leer_plantilla
from rag.esquemas_configuracion import (
    CONFIG_VERSION,
    validar_asistente,
    validar_motor,
)

RUTA_PROYECTO = "configuracion/motor.yaml"
RUTA_DOMINIO = "configuracion/asistente.yaml"

_DOMINIO_POR_DEFECTO = {
    "config_version": CONFIG_VERSION,
    "nombre_asistente": "Asistente documental",
    "descripcion_dominio": "los documentos cargados",
    "idioma": "es",
    "perfil": "_generico",
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
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
    return validar_motor(datos)


def cargar_dominio(ruta: str = RUTA_DOMINIO) -> dict:
    p = Path(ruta)
    if not p.exists():
        return dict(_DOMINIO_POR_DEFECTO)
    datos = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
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
    motor = deepcopy(cargar_proyecto(ruta_motor))
    dominio = deepcopy(cargar_dominio(ruta_dominio))
    return {
        "snapshot_version": 1,
        "config_version": CONFIG_VERSION,
        "motor": motor,
        "dominio": dominio,
    }


def guardar_snapshot_configuracion(
    ruta: str = ".cache/configuracion-efectiva.yaml",
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


def config_recuperacion(cfg: dict | None = None, ruta: str = RUTA_PROYECTO) -> dict:
    cfg = cfg if cfg is not None else cargar_proyecto(ruta)
    return cfg["recuperacion"]


def config_abstencion(
    cfg: dict | None = None,
    ruta: str = RUTA_PROYECTO,
    retriever: str | None = None,
) -> dict | None:
    cfg = cfg if cfg is not None else cargar_proyecto(ruta)
    original = cfg.get("abstencion")
    if original is None:
        return None
    salida = deepcopy(original)
    perfiles = salida.pop("perfiles_retriever", {})
    perfil = perfiles.get(retriever) if retriever is not None else None
    if perfil is not None:
        salida["version"] = perfil.get("version", salida.get("version"))
        salida["capa_a_fuera_dominio"]["senal"] = perfil["senal"]
        salida["capa_a_fuera_dominio"]["umbral"] = perfil["umbral_fuera_dominio"]
        salida["confianza_alta"]["senal"] = perfil["senal"]
        salida["confianza_alta"]["umbral"] = perfil["umbral_confianza_alta"]
    return salida


def config_servicio(cfg: dict | None = None, ruta: str = RUTA_PROYECTO) -> dict:
    cfg = cfg if cfg is not None else cargar_proyecto(ruta)
    return cfg.get("servicio", {"concurrencia_maxima": 4})


def config_redaccion(cfg: dict | None = None, ruta: str = RUTA_PROYECTO) -> dict:
    cfg = cfg if cfg is not None else cargar_proyecto(ruta)
    return cfg.get("redaccion", {
        "metodo_seleccion": "lexico",
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


CLAVES_DOMINIO_VALIDAS = {
    "nombre_asistente", "descripcion_dominio", "idioma", "perfil",
    "cors_origenes", "claves_widget",
}
_CLAVES_LISTA_SEPARADA_POR_COMA = {"cors_origenes", "claves_widget"}


def _encabezado_comentarios(ruta: Path) -> str:
    if not ruta.exists():
        return "# Identidad del asistente. Editable con `rag configurar clave=valor`.\n"
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True)
    fin = 0
    for linea in lineas:
        if linea.strip() == "" or linea.lstrip().startswith("#"):
            fin += 1
        else:
            break
    return "".join(lineas[:fin])


def actualizar_dominio(pares: dict[str, str], ruta: str = RUTA_DOMINIO) -> dict:
    from rag.dominio import RUTA_DOMINIOS, _perfiles_disponibles

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
        disponibles = _perfiles_disponibles(RUTA_DOMINIOS)
        if nuevo["perfil"] not in disponibles:
            raise ValueError(
                f"el perfil {nuevo['perfil']!r} no existe en {RUTA_DOMINIOS}/ "
                f"(disponibles: {disponibles or '(ninguno)'})"
            )

    ruta_p.parent.mkdir(parents=True, exist_ok=True)
    ruta_p.write_text(
        _encabezado_comentarios(ruta_p)
        + yaml.safe_dump(nuevo, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return nuevo


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


def inicializar_asistente_si_falta(ruta: str = RUTA_DOMINIO) -> bool:
    return _crear_desde_recurso_si_falta(ruta, "asistente.yaml")


def inicializar_proyecto_si_falta(
    coleccion_base: str, ruta: str = RUTA_PROYECTO
) -> bool:
    return _crear_desde_recurso_si_falta(
        ruta, "motor.yaml", coleccion_base=coleccion_base
    )


def inicializar_plantillas_si_falta(
    ruta: str = "configuracion/textos.yaml",
) -> bool:
    return _crear_desde_recurso_si_falta(ruta, "textos.yaml")


def inicializar_estilos_si_falta(
    ruta: str = "configuracion/estilos.yaml", origen: str | None = None
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
    return _crear_desde_recurso_si_falta(ruta, "estilos.yaml")
