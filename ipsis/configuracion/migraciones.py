"""Migración de la estructura de archivos de un proyecto a la versión vigente.

``ipsis.configuracion.esquemas`` migra el contenido de cada YAML en memoria; este
módulo mueve y fusiona archivos en disco. Es idempotente: sobre un proyecto ya
migrado no hace nada. Devuelve la lista de cambios para mostrarla al usuario.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from ipsis.configuracion import rutas
from ipsis.recursos.mensajes import t


def _leer_yaml(ruta: Path) -> dict:
    return (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}) if ruta.is_file() else {}


def _escribir_yaml(ruta: Path, datos: dict, encabezado: str = "") -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(encabezado + yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _encabezado(ruta: Path) -> str:
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True) if ruta.is_file() else []
    fin = 0
    for linea in lineas:
        if linea.strip() == "" or linea.lstrip().startswith("#"):
            fin += 1
        else:
            break
    return "".join(lineas[:fin])


def _mover(origen: Path, destino: Path, cambios: list[str], raiz: Path) -> None:
    if not origen.exists():
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origen.is_dir():
        destino.mkdir(parents=True, exist_ok=True)
        for hijo in origen.iterdir():
            objetivo = destino / hijo.name
            if not objetivo.exists():
                shutil.move(str(hijo), str(objetivo))
        if not any(origen.iterdir()):
            origen.rmdir()
    elif not destino.exists():
        shutil.move(str(origen), str(destino))
    cambios.append(t("core.moved", source=origen.relative_to(raiz).as_posix(), target=destino.relative_to(raiz).as_posix()))


def _migrar_dominio(raiz: Path, perfil: str, cambios: list[str]) -> None:
    destino = raiz / rutas.DOMINIO
    carpeta_perfiles = raiz / rutas.CONFIGURACION / "dominios"
    viejo_perfil = carpeta_perfiles / perfil / "perfil.yaml"
    viejo_categorias = raiz / rutas.CONFIGURACION / "categorias.yaml"
    if destino.exists() or not (viejo_perfil.exists() or viejo_categorias.exists()):
        return
    datos = _leer_yaml(viejo_perfil)
    for clave in ("nombre_asistente", "descripcion_dominio", "idioma"):
        datos.pop(clave, None)  # la identidad vive en assistant.yaml
    if viejo_categorias.exists():
        datos["taxonomia"] = _leer_yaml(viejo_categorias)
    _escribir_yaml(destino, datos, t("core.domain_header"))
    cambios.append(t("core.domain_created", path=rutas.DOMINIO, profile=perfil))
    if viejo_perfil.exists():
        shutil.rmtree(viejo_perfil.parent)
    if viejo_categorias.exists():
        viejo_categorias.unlink()
    otros = [p.name for p in carpeta_perfiles.iterdir() if p.is_dir() and p.name != "idiomas"] if carpeta_perfiles.exists() else []
    if otros:
        cambios.append(t("core.unused_domains", profiles=otros))


def _diferencias(propio, base):
    """Partes de ``propio`` que difieren de ``base`` (None si son iguales)."""
    if isinstance(propio, dict) and isinstance(base, dict):
        salida = {}
        for clave, valor in propio.items():
            dif = _diferencias(valor, base.get(clave))
            if dif is not None:
                salida[clave] = dif
        return salida or None
    return None if propio == base else propio


def _con_textos_del_tono(base: dict, idioma: str) -> dict:
    """El paquete de idioma con los textos que hoy viven en el tono ``cordial``,
    en su forma anterior: así se reconoce qué cambió el proyecto."""
    from importlib.resources import files

    recurso = files("ipsis.recursos").joinpath("tonos", idioma, "cordial.yaml")
    if not recurso.is_file():
        return base
    situaciones = (yaml.safe_load(recurso.read_text(encoding="utf-8")) or {}).get("situations") or {}
    # Con los nombres de variable anteriores, para comparar con textos.yaml tal como era.
    tono = {s: [_variables_anteriores(v) for v in textos] for s, textos in situaciones.items()}
    mensajes = dict(base.get("mensajes") or {})
    mensajes.update({clave: tono[situacion][0] for clave, situacion in (
        ("sin_respuesta", "no_answer"), ("premisa_no_encontrada", "premise_not_found"),
        ("relacionado_intro", "related_intro"), ("relacionado_foco_ausente", "missing_focus"))})
    mensajes["conectores"] = {**(mensajes.get("conectores") or {}),
                              **{c: tono[s] for c, s in (("apertura", "opening"), ("complemento", "addition"),
                                                         ("condicion", "condition"), ("excepcion", "exception"))}}
    conversacional = {**(base.get("conversacional") or {}),
                      "respuestas": {c: tono[s] for c, s in (("saludo", "greeting"), ("agradecimiento", "thanks"),
                                                             ("despedida", "farewell"), ("capacidad", "capability"))}}
    return {**base, "mensajes": mensajes, "conversacional": conversacional}


def _variables_anteriores(texto: str) -> str:
    from ipsis.configuracion.personalidad import VARIABLES_ANTERIORES

    for anterior, actual in VARIABLES_ANTERIORES.items():
        texto = texto.replace("{" + actual + "}", "{" + anterior + "}")
    return texto


def _migrar_textos(raiz: Path, cambios: list[str]) -> None:
    """``config/textos.yaml`` pasa al paquete de idioma (P3.5).

    Solo lo que el proyecto había cambiado se conserva, en
    ``config/language.yaml``.
    """
    viejo = raiz / rutas.CONFIGURACION / "textos.yaml"
    if not viejo.is_file():
        return
    from importlib.resources import files

    textos = _leer_yaml(viejo)
    idioma = _leer_yaml(raiz / rutas.ASISTENTE).get("idioma", "es")
    carpeta = files("ipsis.recursos").joinpath("idiomas")
    recurso = carpeta.joinpath(f"{idioma}.yaml")
    if not recurso.is_file():
        recurso = carpeta.joinpath("es.yaml")
    base = yaml.safe_load(recurso.read_text(encoding="utf-8")) or {}
    base = _con_textos_del_tono(base, recurso.name.removesuffix(".yaml"))
    abstencion = textos.get("abstencion") or {}
    equivalente = {
        "mensajes": {
            "sin_respuesta": abstencion.get("generico"),
            "premisa_no_encontrada": abstencion.get("premisa_no_encontrada"),
            "relacionado_intro": abstencion.get("zona_gris_intro"),
            "conectores": textos.get("conectores"),
        },
        "conversacional": textos.get("conversacional"),
    }
    equivalente["mensajes"] = {k: v for k, v in equivalente["mensajes"].items() if v is not None}
    equivalente = {k: v for k, v in equivalente.items() if v}
    propio = _diferencias(equivalente, base)
    destino = raiz / rutas.IDIOMA
    if propio and not destino.exists():
        _escribir_yaml(destino, propio, t("core.language_header"))
        cambios.append(t("core.language_created", path=rutas.IDIOMA))
    viejo.unlink()
    cambios.append(t("core.texts_removed"))


# --- v5: estructura y claves en inglés -------------------------------------------------------------
_CARPETAS_V5 = (("configuracion", rutas.CONFIGURACION), ("documentos", rutas.DOCUMENTOS), (".rag", rutas.INTERNO))
_ARCHIVOS_V5 = (
    ("config/asistente.yaml", rutas.ASISTENTE), ("config/motor.yaml", rutas.MOTOR),
    ("config/estilos.yaml", rutas.ESTILOS), ("config/personalidad.yaml", rutas.PERSONALIDAD),
    ("config/dominio.yaml", rutas.DOMINIO), ("config/idioma.yaml", rutas.IDIOMA),
    ("config/calibracion.yaml", rutas.CALIBRACION), ("config/avatares", rutas.AVATARES),
    ("documents/catalogo.yaml", rutas.CATALOGO),
    ("golden/banco", rutas.GOLDEN_BANCO), ("golden/bank/manifiesto.json", rutas.GOLDEN_MANIFIESTO),
    ("golden/reportes", rutas.GOLDEN_REPORTES), ("golden/LEEME.txt", "golden/README.txt"),
    (".ipsis/indice", rutas.INDICE), (".ipsis/registros", ".ipsis/logs"),
    (".ipsis/logs/consultas.jsonl", rutas.REGISTRO_CONSULTAS),
    (".ipsis/configuracion-efectiva.yaml", rutas.SNAPSHOT), (".ipsis/widget-vista-previa.html", rutas.VISTA_PREVIA),
)
# Archivo del proyecto → su entrada en el glosario.
_GLOSARIO_V5 = ((rutas.ASISTENTE, "asistente"), (rutas.MOTOR, "motor"), (rutas.ESTILOS, "estilos"),
                (rutas.PERSONALIDAD, "personalidad"), (rutas.DOMINIO, "dominio"), (rutas.CALIBRACION, "calibracion"),
                (rutas.CATALOGO, "catalogo"))
_QDRANT_ANTERIORES = (".cache/qdrant_local", ".rag/indice/qdrant", ".ipsis/indice/qdrant")


def _reubicar_v5(raiz: Path, cambios: list[str]) -> None:
    """Carpetas y archivos con nombres en español → inglés (config/, documents/, .ipsis/index…)."""
    for viejo, nuevo in _CARPETAS_V5:
        _mover(raiz / viejo, raiz / nuevo, cambios, raiz)
    for viejo, nuevo in _ARCHIVOS_V5:
        _mover(raiz / viejo, raiz / nuevo, cambios, raiz)
    indice = raiz / rutas.INDICE
    if indice.is_dir():
        for viejo, nuevo in ((".manifiesto.json", ".manifest.json"), (".estadisticas.json", ".stats.json")):
            for archivo in indice.glob("*" + viejo):
                _mover(archivo, archivo.with_name(archivo.name[: -len(viejo)] + nuevo), cambios, raiz)


def _activar_estructural_en_disco(externo: dict) -> bool:
    """v8 (ADR 0009) sobre un ``engine.yaml`` con claves en inglés: v2 sin preparación elegida → estructural."""
    if externo.get("pipeline", "v2") != "v2":
        return False
    recuperacion = externo.setdefault("retrieval", {})
    if "preparation" in recuperacion:
        return False
    recuperacion["preparation"] = {"mode": "structural_v1", "max_unit_words": 400, "child_words": 80}
    return True


def _reescribir_en_ingles(raiz: Path, cambios: list[str]) -> None:
    """Reescribe con claves y valores en inglés los YAML que aún los tienen en español."""
    from ipsis.configuracion.esquemas import CONFIG_VERSION
    from ipsis.configuracion.glosario import a_externo

    for relativa, archivo in _GLOSARIO_V5:
        ruta = raiz / relativa
        datos = _leer_yaml(ruta)
        if not datos:
            continue
        externo = a_externo(datos, archivo)
        version_previa = int(externo.get("config_version", 0))
        if archivo == "motor" and 7 <= version_previa < 8 and _activar_estructural_en_disco(externo):
            cambios.append(t("core.structural_migrated", path=relativa))
        if archivo in ("asistente", "motor") and int(externo.get("config_version", 0)) < CONFIG_VERSION:
            externo["config_version"] = CONFIG_VERSION
        if archivo == "personalidad":
            from ipsis.configuracion.personalidad import vocabulario_actual

            externo = vocabulario_actual(externo)
        if archivo == "motor":
            recuperacion = externo.get("retrieval") or {}
            if recuperacion.get("qdrant_path") in _QDRANT_ANTERIORES:
                recuperacion["qdrant_path"] = rutas.QDRANT
        if externo != datos:
            _escribir_yaml(ruta, externo, _encabezado(ruta))
            cambios.append(t("core.rewritten_english", path=relativa))


def migrar_proyecto(raiz: str | Path = ".") -> list[str]:
    """Lleva un proyecto anterior a la estructura vigente. Devuelve los cambios hechos."""
    raiz = Path(raiz).resolve()
    cambios: list[str] = []
    _reubicar_v5(raiz, cambios)
    cambios.extend(_migrar_v3(raiz))
    _reescribir_en_ingles(raiz, cambios)
    return cambios


def _migrar_v3(raiz: Path) -> list[str]:
    """Lleva un proyecto v2 a la estructura v3 (ya reubicado con nombres en inglés)."""
    cambios: list[str] = []
    asistente = raiz / rutas.ASISTENTE
    if not asistente.is_file():
        return cambios
    datos = _leer_yaml(asistente)
    if int(datos.get("config_version", 0)) < 3:
        perfil = datos.pop("perfil", "_generico") or "_generico"
        _migrar_dominio(raiz, perfil, cambios)
        datos["perfil"] = "light"  # perfil de instalación; sin modelos adicionales
        datos["config_version"] = 3
        _escribir_yaml(asistente, datos, _encabezado(asistente))
        cambios.append(t("core.assistant_v3", path=rutas.ASISTENTE))

    motor = raiz / rutas.MOTOR
    datos_motor = _leer_yaml(motor)
    if datos_motor and int(datos_motor.get("config_version", 0)) < 3:
        recuperacion = datos_motor.get("recuperacion") or {}
        if recuperacion.get("qdrant_path") == ".cache/qdrant_local":
            recuperacion["qdrant_path"] = rutas.QDRANT
        datos_motor["config_version"] = 3
        _escribir_yaml(motor, datos_motor, _encabezado(motor))
        cambios.append(t("core.engine_v3", path=rutas.MOTOR))

    # Las palabras de idioma viven en el paquete de idioma desde P3.1.
    carpeta_dominios = raiz / rutas.CONFIGURACION / "dominios"
    if (carpeta_dominios / "idiomas").is_dir():
        shutil.rmtree(carpeta_dominios / "idiomas")
        cambios.append(t("core.languages_removed"))
    if carpeta_dominios.is_dir() and not any(carpeta_dominios.iterdir()):
        carpeta_dominios.rmdir()

    _migrar_textos(raiz, cambios)

    _mover(raiz / ".cache" / "qdrant_local", raiz / rutas.QDRANT, cambios, raiz)
    _mover(raiz / ".cache" / "vocab_bm25", raiz / rutas.INDICE, cambios, raiz)
    _mover(raiz / "data" / "golden", raiz / rutas.GOLDEN_BANCO, cambios, raiz)
    _mover(raiz / rutas.GOLDEN_BANCO / "manifiesto.json", raiz / rutas.GOLDEN_MANIFIESTO, cambios, raiz)
    for vacio in (raiz / ".cache", raiz / "data"):
        if vacio.is_dir() and not any(vacio.iterdir()):
            vacio.rmdir()
    return cambios


__all__ = ["migrar_proyecto"]
