"""La documentación no contradice al código.

Las guías de uso (inglés y español) documentan todos los comandos de la CLI, los enlaces relativos existen y los
datos que se copian a mano (modelos de cada perfil, ``config_version``, formatos, secciones de cada guía en inglés
y en español, versión publicada) coinciden con su fuente de verdad en el código.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
GUIA = RAIZ / "docs" / "guide" / "usage.md"
GUIA_ES = RAIZ / "docs" / "es" / "guia" / "uso.md"


def _comandos(parser, ruta=()):
    for accion in parser._actions:
        if isinstance(accion, argparse._SubParsersAction):
            for nombre, sub in accion.choices.items():
                if any(isinstance(a, argparse._SubParsersAction) for a in sub._actions):
                    yield from _comandos(sub, ruta + (nombre,))
                else:
                    yield ruta + (nombre,)


@pytest.mark.parametrize("guia", [GUIA, GUIA_ES], ids=["en", "es"])
def test_cada_comando_aparece_en_la_guia_de_uso(guia):
    from ipsis.cli import construir_parser

    texto = guia.read_text(encoding="utf-8")
    faltan = [" ".join(c) for c in _comandos(construir_parser()) if f"ipsis {' '.join(c)}" not in texto]
    assert not faltan, f"documenta en {guia.relative_to(RAIZ)}: {faltan}"


def test_los_enlaces_relativos_de_la_documentacion_existen():
    import re

    raiz = RAIZ
    archivos = [raiz / "README.md", raiz / "README.es.md", raiz / "CHANGELOG.md", raiz / "CONTRIBUTING.md", raiz / "SECURITY.md",
                raiz / "CODE_OF_CONDUCT.md", raiz / ".github" / "PULL_REQUEST_TEMPLATE.md",
                raiz / "tests" / "datos" / "banco_universal" / "README.md", *sorted((raiz / "docs").rglob("*.md")),
                *sorted((raiz / "examples").rglob("*.md")), raiz / "herramientas" / "avatar" / "LEEME.md"]
    rotos = []
    for archivo in archivos:
        if not archivo.is_file() or "node_modules" in archivo.parts:
            continue
        texto = re.sub(r"```.*?```", "", archivo.read_text(encoding="utf-8"), flags=re.S)
        enlaces = re.findall(r"\]\(([^)\s]+)\)", texto) + re.findall(r'(?:src|srcset|href)="([^"]+)"', texto)
        for destino in enlaces:
            if re.match(r"^[a-z]+:|^#|^mailto:", destino):
                continue
            ruta = destino.split("#")[0]
            if ruta and not (archivo.parent / ruta).exists():
                rotos.append(f"{archivo.relative_to(raiz)} → {destino}")
    assert not rotos, rotos


# ---------------------------------------------------------------------------
# Coherencia entre el código y la documentación (plan de coherencia, C1).
#
# Cada prueba que hoy falla lleva ``xfail(strict=True)`` con la tarea del plan que la arregla: esa tarea quita
# la marca, y si alguien arregla la documentación antes, ``strict`` avisa para que la quite.
# ---------------------------------------------------------------------------

README_EN, README_ES = RAIZ / "README.md", RAIZ / "README.es.md"
INSTALACION_EN = RAIZ / "docs" / "guide" / "installation.md"
INSTALACION_ES = RAIZ / "docs" / "es" / "guia" / "instalacion.md"
FUENTES_V2 = RAIZ / "docs" / "methodology" / "fuentes-v2.md"


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _sin_codigo(texto: str) -> str:
    """El texto sin bloques ```; ahí hay comentarios con ``#`` que no son encabezados."""
    return re.sub(r"```.*?```", "", texto, flags=re.S)


def _fila_de_perfil(texto: str, perfil: str) -> str:
    """La línea de la tabla de perfiles que empieza con ``| `perfil` |``; cada perfil tiene una sola por archivo."""
    filas = [linea for linea in texto.splitlines() if linea.strip().startswith(f"| `{perfil}` |")]
    assert len(filas) == 1, f"se esperaba una fila de `{perfil}` y hay {len(filas)}"
    return filas[0]


# Cómo nombra la documentación a cada modelo. Un modelo nuevo sin alias se busca por su nombre corto (lo que va
# tras la última «/», sin «-ONNX»); si la documentación lo abrevia, se declara aquí.
ALIAS_DE_MODELOS = {
    "multilingual-e5-small": "e5-small",
    "mmarco-mMiniLMv2-L12-H384-v1": "mMiniLM",
    "mdeberta-v3-base-squad2": "mDeBERTa",  # el sufijo -onnx se quita antes de buscar el alias
}


def _nombre_en_la_documentacion(id_modelo: str) -> str:
    corto = re.sub(r"-ONNX$", "", id_modelo.rsplit("/", 1)[-1], flags=re.I)
    return ALIAS_DE_MODELOS.get(corto, corto)


@pytest.mark.parametrize("archivo", [README_EN, README_ES, INSTALACION_EN, INSTALACION_ES],
                         ids=["README.md", "README.es.md", "installation.md", "instalacion.md"])
def test_tabla_de_perfiles_nombra_los_modelos_vigentes(archivo):
    """La fila de cada perfil nombra sus modelos (``models.dense``, ``models.reranker`` y los reranker por idioma).

    No exige el lector: v2 no lo carga, así que la fila de ``medium`` no debe presentarlo como parte del perfil.
    Las filas se localizan por su inicio, ``| `light` |`` y ``| `medium` |`` (la tabla puede ir con sangría).
    """
    from ipsis.configuracion.perfiles import cargar_perfil_instalacion

    texto = _leer(archivo)
    problemas = []
    for nombre in ("light", "medium"):
        perfil = cargar_perfil_instalacion(nombre)
        fila = _fila_de_perfil(texto, nombre)
        esperados = [perfil.modelos.denso, perfil.modelos.reranker, *perfil.reranker_por_idioma.values()]
        for id_modelo in dict.fromkeys(filter(None, esperados)):
            alias = _nombre_en_la_documentacion(id_modelo)
            if alias.casefold() not in fila.casefold():
                problemas.append(f"{archivo.name}: la fila de `{nombre}` no nombra {alias} ({id_modelo})")
        if nombre == "medium" and perfil.modelos.lector:
            lector = _nombre_en_la_documentacion(perfil.modelos.lector)
            if lector.casefold() in fila.casefold():
                problemas.append(f"{archivo.name}: la fila de `medium` presenta el lector {lector}, que v2 no carga")
    assert not problemas, problemas


# ``config_version`` de otros archivos no es el de assistant.yaml / engine.yaml: ``personality.yaml`` lleva el suyo.
CONFIG_VERSION_AJENA = {
    "docs/guide/personality.md": "config_version del tono (personality.yaml), no del proyecto",
    "docs/es/guia/personalidad.md": "config_version del tono (personality.yaml), no del proyecto",
}
CON_EJEMPLOS_DE_CONFIGURACION = [*sorted((RAIZ / "docs" / "guide").glob("*.md")),
                                 *sorted((RAIZ / "docs" / "es" / "guia").glob("*.md")), FUENTES_V2]


def _parametros_de_config_version() -> list:
    parametros = []
    for ruta in CON_EJEMPLOS_DE_CONFIGURACION:
        if ruta.relative_to(RAIZ).as_posix() in CONFIG_VERSION_AJENA:
            continue
        parametros.append(pytest.param(ruta, id=ruta.relative_to(RAIZ / "docs").as_posix()))
    return parametros


@pytest.mark.parametrize("ruta", _parametros_de_config_version())
def test_ejemplos_usan_la_config_version_vigente(ruta):
    """Todo ``config_version: N`` dentro de un bloque de código usa ``CONFIG_VERSION``.

    ``CONFIG_VERSION_AJENA`` deja fuera las guías cuyo ``config_version`` es el de otro archivo.
    """
    from ipsis.configuracion.esquemas import CONFIG_VERSION

    bloques = re.findall(r"```[a-z]*\n(.*?)```", _leer(ruta), flags=re.S)
    versiones = [int(n) for bloque in bloques for n in re.findall(r"^\s*config_version:\s*(\d+)\s*$", bloque, flags=re.M)]
    desactualizadas = sorted({v for v in versiones if v != CONFIG_VERSION})
    assert not desactualizadas, f"{ruta.relative_to(RAIZ)} usa config_version {desactualizadas}; el código está en {CONFIG_VERSION}"


@pytest.mark.parametrize("ruta, patron", [
    pytest.param(RAIZ / "docs" / "guide" / "configuration.md", r"current\s+version\s+is\s+`(\d+)`", id="en"),
    pytest.param(RAIZ / "docs" / "es" / "guia" / "configuracion.md", r"versión\s+vigente\s+es\s+la\s+`(\d+)`", id="es"),
])
def test_la_guia_de_configuracion_describe_la_version_vigente(ruta, patron):
    """La frase «la versión vigente es N» y la tabla «Versión / Qué cambió» llegan hasta ``CONFIG_VERSION``."""
    from ipsis.configuracion.esquemas import CONFIG_VERSION

    texto = _leer(ruta)
    declarada = re.search(patron, texto)
    assert declarada, f"{ruta.name}: no se encontró la frase de la versión vigente"
    filas = {int(n) for n in re.findall(r"^\|\s*(\d+)\s*\|", texto, flags=re.M)}
    faltan = [v for v in range(2, CONFIG_VERSION + 1) if v not in filas]
    problemas = []
    if int(declarada.group(1)) != CONFIG_VERSION:
        problemas.append(f"dice que la vigente es {declarada.group(1)}; el código está en {CONFIG_VERSION}")
    if faltan:
        problemas.append(f"la tabla de versiones no describe {faltan}")
    assert not problemas, f"{ruta.name}: {problemas}"


# Cómo nombran los README a cada formato (``\b`` evita que «XLS» se dé por nombrado con «XLSX»; se admite el plural).
NOMBRE_DE_FORMATO = {".docx": "DOCX", ".pdf": "PDF", ".md": "Markdown", ".markdown": "Markdown", ".tex": "LaTeX",
                     ".txt": "TXT", ".xlsx": "XLSX", ".xls": "XLS", ".csv": "CSV", ".tsv": "TSV"}


@pytest.mark.parametrize("readme", [README_EN, README_ES], ids=["en", "es"])
def test_formatos_soportados_en_los_readme(readme):
    """Cada extensión de ``EXTENSIONES_SOPORTADAS`` se nombra en el README."""
    from ipsis.ingesta.parsear import EXTENSIONES_SOPORTADAS

    sin_nombre = sorted(EXTENSIONES_SOPORTADAS - NOMBRE_DE_FORMATO.keys())
    assert not sin_nombre, f"agrega a NOMBRE_DE_FORMATO cómo se llama {sin_nombre} en los README"
    texto = _leer(readme)
    faltan = sorted({NOMBRE_DE_FORMATO[e] for e in EXTENSIONES_SOPORTADAS
                     if not re.search(rf"\b{NOMBRE_DE_FORMATO[e]}s?\b", texto, flags=re.I)})
    assert not faltan, f"{readme.name} no nombra los formatos {faltan}"


# Pares (inglés, español) de ``docs/``. ``DIFERENCIAS_PERMITIDAS`` guarda, con su motivo, la diferencia de
# secciones ``##`` que se acepta entre los dos (``{"web.md": (diferencia, "motivo")}``).
PARES_DE_GUIAS = [("configuration", "configuracion"), ("deployment", "despliegue"), ("golden", "golden"),
                  ("installation", "instalacion"), ("integrations", "integraciones"),
                  ("inventories", "inventarios"), ("media", "multimedia"), ("personality", "personalidad"), ("usage", "uso"),
                  ("web", "web")]
DIFERENCIAS_PERMITIDAS: dict[str, tuple[int, str]] = {}


def _secciones(ruta: Path) -> int:
    return len(re.findall(r"^## ", _sin_codigo(_leer(ruta)), flags=re.M))


@pytest.mark.parametrize("en, es", PARES_DE_GUIAS, ids=[en for en, _ in PARES_DE_GUIAS])
def test_guias_en_y_es_tienen_las_mismas_secciones(en, es):
    """Cada guía de ``docs/guide/`` y su par de ``docs/es/guia/`` tienen las mismas secciones ``##``."""
    ruta_en, ruta_es = RAIZ / "docs" / "guide" / f"{en}.md", RAIZ / "docs" / "es" / "guia" / f"{es}.md"
    assert ruta_es.is_file(), f"falta {ruta_es.relative_to(RAIZ)}"
    diferencia = _secciones(ruta_en) - _secciones(ruta_es)
    permitida = DIFERENCIAS_PERMITIDAS.get(f"{en}.md", (0, ""))[0]
    assert diferencia == permitida, (f"{en}.md tiene {_secciones(ruta_en)} secciones ## y {es}.md {_secciones(ruta_es)}; "
                                     f"diferencia permitida: {permitida}")


def test_hay_una_guia_en_ingles_y_otra_en_espanol_por_cada_par():
    """``PARES_DE_GUIAS`` cubre todas las guías: una guía nueva en un idioma sin su par falla aquí."""
    en = {p.stem for p in (RAIZ / "docs" / "guide").glob("*.md")}
    es = {p.stem for p in (RAIZ / "docs" / "es" / "guia").glob("*.md")}
    assert en == {a for a, _ in PARES_DE_GUIAS}, f"guías en inglés sin declarar: {sorted(en ^ {a for a, _ in PARES_DE_GUIAS})}"
    assert es == {b for _, b in PARES_DE_GUIAS}, f"guías en español sin declarar: {sorted(es ^ {b for _, b in PARES_DE_GUIAS})}"


@pytest.mark.parametrize("readme", [README_EN, README_ES], ids=["en", "es"])
def test_badge_de_version_coincide_con_pyproject(readme):
    """El badge de versión de cada README dice lo mismo que ``project.version`` de ``pyproject.toml``."""
    import tomllib

    version = tomllib.loads(_leer(RAIZ / "pyproject.toml"))["project"]["version"]
    badge = re.search(r"img\.shields\.io/badge/(?:version|versi%C3%B3n)-([0-9][0-9A-Za-z.]*)-", _leer(readme))
    assert badge, f"{readme.name}: no se encontró el badge de versión"
    assert badge.group(1) == version, f"{readme.name} dice {badge.group(1)}; pyproject.toml dice {version}"


GUIAS_DE_USO = [pytest.param(GUIA, id="en"), pytest.param(GUIA_ES, id="es")]


def _filas_de_comandos(guia: Path) -> list[str]:
    """Las filas de la tabla de referencia de comandos: la tabla (líneas seguidas que empiezan con ``|``) que contiene
    la fila de ``ipsis load``. Otras tablas de la guía, como la de problemas frecuentes, también citan comandos."""
    bloques, actual = [], []
    for linea in _leer(guia).splitlines():
        if linea.startswith("|"):
            actual.append(linea)
        elif actual:
            bloques.append(actual)
            actual = []
    bloques.append(actual)
    tabla = next(b for b in bloques if any(f.startswith("| `ipsis load") for f in b))
    return [f for f in tabla if f.startswith("| `ipsis ")]


@pytest.mark.parametrize("guia", GUIAS_DE_USO)
def test_la_fila_de_ipsis_load_lista_todos_los_formatos(guia):
    """La tabla de comandos dice qué formatos carga ``ipsis load``: los mismos que ``EXTENSIONES_SOPORTADAS``.

    En esa fila Markdown se abrevia «MD»; el resto de los nombres es el de ``NOMBRE_DE_FORMATO``.
    """
    from ipsis.ingesta.parsear import EXTENSIONES_SOPORTADAS

    fila = next(f for f in _filas_de_comandos(guia) if f.startswith("| `ipsis load"))
    nombres = {**NOMBRE_DE_FORMATO, ".md": "MD", ".markdown": "MD"}
    sin_nombre = sorted(EXTENSIONES_SOPORTADAS - nombres.keys())
    assert not sin_nombre, f"agrega a NOMBRE_DE_FORMATO cómo se llama {sin_nombre}"
    faltan = sorted({nombres[e] for e in EXTENSIONES_SOPORTADAS if not re.search(rf"\b{nombres[e]}\b", fila)})
    assert not faltan, f"{guia.name}: la fila de `ipsis load` no lista {faltan}"


@pytest.mark.parametrize("guia", GUIAS_DE_USO)
def test_la_tabla_de_comandos_no_repite_filas(guia):
    """Ninguna firma de comando (el primer código de la fila) se repite en la tabla de referencia.

    Un mismo comando puede tener varias filas si su firma cambia (``ipsis ask "<pregunta>"`` con y sin
    ``--diagnostics``); una fila idéntica ya se coló en la guía en inglés (``ipsis sync``).
    """
    firmas = [re.match(r"\| `([^`]+)`", fila).group(1) for fila in _filas_de_comandos(guia)]
    repetidas = sorted({f for f in firmas if firmas.count(f) > 1})
    assert not repetidas, f"{guia.name} repite filas de {repetidas}"
