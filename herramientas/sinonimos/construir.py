"""Descarga fuentes fijadas y convierte synsets en TSV reproducibles.

Solo desarrollo; no se importa ni se descarga nada al ejecutar ipsis.
Por defecto reconstruye desde los originales guardados en el repositorio.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import importlib.util
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from urllib.request import urlopen

RAIZ = Path(__file__).resolve().parents[2]
FUENTES = Path(__file__).with_name("fuentes.json")
POS = frozenset("nvars")
MAX_DESCARGA = 32 * 1024 * 1024
MAX_XML = 256 * 1024 * 1024
VERSION_CONVERSOR = 4
ORIGINALES = RAIZ / "herramientas/sinonimos/datos/fuentes"
SALIDA = RAIZ / "ipsis/recursos/sinonimos"
SUPLEMENTOS = RAIZ / "herramientas/sinonimos/datos/tesauros"


def fuentes_idioma(configuracion: dict, idioma: str) -> list[dict]:
    return [configuracion["sources"][idioma], *configuracion.get("supplements", {}).get(idioma, [])]


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _json(datos: dict) -> bytes:
    return (json.dumps(datos, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def cargar_fuentes(ruta: Path = FUENTES) -> dict:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if datos.get("schema_version") != 1:
        raise ValueError("Unsupported source manifest version")
    if set(datos.get("supplements", {})) - set(datos["sources"]):
        raise ValueError("Supplement language has no primary source")
    nombres = set()
    for idioma in datos["sources"]:
        for fuente in fuentes_idioma(datos, idioma):
            if idioma not in {"es", "en", "pt"} or fuente["format"] not in {"omw-tab", "wn-lmf-gzip", "mythes"}:
                raise ValueError(f"Invalid source: {idioma}")
            for archivo in [fuente["data"], *fuente["notices"]]:
                if (not re.fullmatch(r"[\w.-]+", archivo["filename"])
                        or not archivo["url"].startswith("https://")
                        or not re.fullmatch(r"[0-9a-f]{64}", archivo["sha256"])
                        or not 0 < archivo["bytes"] <= MAX_DESCARGA
                        or archivo["filename"] in nombres):
                    raise ValueError(f"Invalid download specification: {archivo}")
                nombres.add(archivo["filename"])
    return datos


def obtener_archivo(especificacion: dict, cache: Path, offline: bool = False) -> bytes:
    """Comprueba también la caché; nunca acepta un nuevo hash automáticamente."""
    ruta = cache / especificacion["filename"]
    comprimida = cache / (especificacion["filename"] + ".gz")
    if ruta.exists():
        datos = ruta.read_bytes()
    elif comprimida.exists():
        # Los TAB originales se guardan comprimidos sin pérdida en el repo.
        # El hash fijado sigue siendo el del original, después de descomprimir.
        with gzip.open(comprimida, "rb") as entrada:
            datos = entrada.read(especificacion["bytes"] + 1)
    else:
        if offline:
            raise ValueError(f"Missing cached source: {ruta}; use --download explicitly to fetch a new source")
        with urlopen(especificacion["url"], timeout=60) as respuesta:
            # Leer uno de más permite detectar una fuente que exceda lo fijado.
            datos = respuesta.read(especificacion["bytes"] + 1)
    if len(datos) != especificacion["bytes"] or sha256(datos) != especificacion["sha256"]:
        raise ValueError(f"Source checksum/size mismatch: {ruta}; inspect before downloading again")
    if not ruta.exists() and not comprimida.exists():
        cache.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(ruta.suffix + ".tmp")
        temporal.write_bytes(datos)
        temporal.replace(ruta)
    return datos


def archivar_fuentes(configuracion: dict, cache: Path, destino: Path = ORIGINALES,
                     *, suplementos: bool = False) -> dict:
    """Conserva los originales aprobados y los avisos; siempre sin red."""
    archivos = {}
    resumen = {}
    fuentes = [(idioma, fuente) for idioma in sorted(configuracion["sources"])
               for fuente in (configuracion.get("supplements", {}).get(idioma, [])
                              if suplementos else [configuracion["sources"][idioma]])]
    for idioma, fuente in fuentes:
        for spec in [fuente["data"], *fuente["notices"]]:
            datos = obtener_archivo(spec, cache, offline=True)
            nombre = spec["filename"]
            if spec is fuente["data"] and not nombre.endswith(".gz"):
                buffer = io.BytesIO()
                with gzip.GzipFile(filename="", fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as comprimido:
                    comprimido.write(datos)
                datos = buffer.getvalue()
                nombre += ".gz"
            archivos[nombre] = datos
            resumen[nombre] = {"language": idioma, "bytes": len(datos), "sha256": sha256(datos),
                               "original": spec}
            if suplementos:
                resumen[nombre]["source_id"] = fuente["id"]
    reporte = {"schema_version": 1, "reviewed_on": configuracion["reviewed_on"], "files": resumen}
    archivos["manifest.json"] = _json(reporte)
    for nombre, datos in archivos.items():
        archivo = destino / nombre
        if archivo.exists() and archivo.read_bytes() != datos:
            raise ValueError(f"Existing source archive differs: {archivo}; review before replacing")
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, datos in archivos.items():
        archivo = destino / nombre
        if not archivo.exists():
            archivo.write_bytes(datos)
    return reporte


def serializar_lexico(grupos: dict[tuple[str, str], set[str]], idioma: str, fuente: dict) -> bytes:
    """Léxico maestro completo, sin filtros: incluye locuciones y polisemia.

    CSV con tabulador conserva incluso comillas o caracteres de control en
    lemas originales. No se cambian tildes, mayúsculas ni formas escritas.
    """
    buffer = io.StringIO(newline="")
    buffer.write(f"# ipsis-lexicon\t1\t{idioma}\n")
    buffer.write(f"# source\t{fuente['id']}\t{fuente['version']}\t{fuente['data']['sha256']}\n")
    buffer.write("# synset_id\tpos\tlemmas...\n")
    escritor = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    for (synset, pos), lemas in sorted(grupos.items()):
        escritor.writerow([synset, pos, *sorted(lemas)])
    return buffer.getvalue().encode("utf-8")


def leer_omw(datos: bytes, etiqueta: str) -> dict[tuple[str, str], set[str]]:
    grupos: dict[tuple[str, str], set[str]] = defaultdict(set)
    for numero, linea in enumerate(datos.decode("utf-8-sig").splitlines(), 1):
        if not linea.strip() or linea.startswith("#"):
            continue
        campos = linea.split("\t")
        if len(campos) < 2:
            raise ValueError(f"Invalid OMW row {numero}: expected three columns")
        if campos[1] != etiqueta:
            continue  # definiciones y otras relaciones no son sinónimos
        if len(campos) != 3:
            raise ValueError(f"Invalid OMW lemma row {numero}: expected three columns")
        synset, _, lema = campos
        if not re.fullmatch(r"\d{8}-[nvars]", synset):
            raise ValueError(f"Invalid OMW synset on row {numero}: {synset}")
        grupos[(synset, synset[-1])].add(lema)
    if not grupos:
        raise ValueError(f"No OMW lemma groups found for {etiqueta}")
    return dict(grupos)


def _etiqueta(elemento) -> str:
    return elemento.tag.rsplit("}", 1)[-1]


def leer_mythes(datos: bytes) -> list[tuple[str, str, str, tuple[str, ...]]]:
    """Conserva entradas dirigidas y etiquetas; no convierte filas en synsets."""
    codificacion, separador, cuerpo = datos.partition(b"\n")
    encoding = codificacion.decode("ascii").strip().upper()
    if not separador or encoding not in {"UTF-8", "ISO8859-1", "ISO-8859-1"}:
        raise ValueError("Unsupported MyThes encoding")
    lineas = cuerpo.decode(encoding).splitlines()
    filas = []
    indice = 0
    while indice < len(lineas):
        numero = indice + 2
        campos = lineas[indice].split("|")
        if len(campos) != 2 or not campos[0].strip() or not campos[1].isdigit():
            raise ValueError(f"Invalid MyThes entry on line {numero}")
        palabra, cantidad = campos[0], int(campos[1])
        indice += 1
        if not 1 <= cantidad <= len(lineas) - indice:
            raise ValueError(f"Invalid MyThes meaning count on line {numero}")
        for sentido in range(cantidad):
            partes = lineas[indice].split("|")
            indice += 1
            if len(partes) < 2 or not partes[0].strip() or not any(p.strip() for p in partes[1:]):
                raise ValueError(f"Invalid MyThes meaning on line {indice + 1}")
            filas.append((f"{numero}:{sentido + 1}", palabra, partes[0], tuple(partes[1:])))
    if not filas:
        raise ValueError("Empty MyThes source")
    return filas


def vocabulario_mythes(filas: list) -> set[str]:
    palabras = set()
    for _, palabra, etiqueta, terminos in filas:
        palabras.add(palabra.strip())
        # WordNet/MyThes marca relaciones no equivalentes dentro del término.
        # No borrar la marca y presentar su contenido como un sinónimo.
        if "antôn" in etiqueta.casefold() or "antonym" in etiqueta.casefold():
            continue
        for termino in terminos:
            termino = termino.strip()
            if termino and not re.search(r" \((?:generic term|similar term|antonym|related term)\)$", termino):
                palabras.add(termino)
    return palabras


def construir_suplementos(idioma: str, configuracion: dict, cache: Path,
                         grupos: dict, offline: bool) -> tuple[dict[str, bytes], list[dict], dict]:
    fuentes = configuracion.get("supplements", {}).get(idioma, [])
    if not fuentes:
        return {}, [], {}
    palabras = {p: {configuracion["sources"][idioma]["id"]} for ps in grupos.values() for p in ps}
    originales = len(palabras)
    palabras_sueltas_originales = {p for p in palabras if normalizar(p) is not None}
    reportes = []
    artefactos = {}
    buffer = io.StringIO(newline="")
    buffer.write(f"# ipsis-thesaurus\t1\t{idioma}\n# source_id\tentry_id\theadword\tlabel\tterms...\n")
    escritor = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    for fuente in fuentes:
        if fuente["format"] != "mythes":
            raise ValueError("Supplements must preserve MyThes records")
        filas = leer_mythes(obtener_archivo(fuente["data"], cache, offline))
        terminos = vocabulario_mythes(filas)
        nuevos = len(terminos - palabras.keys())
        for termino in terminos:
            palabras.setdefault(termino, set()).add(fuente["id"])
        for entrada, palabra, etiqueta, miembros in filas:
            escritor.writerow([fuente["id"], entrada, palabra, etiqueta, *miembros])
        for aviso in fuente["notices"]:
            artefactos[f"licencias/{aviso['filename']}"] = obtener_archivo(aviso, cache, offline)
        reportes.append({"source": fuente, "records": len(filas), "unique_forms": len(terminos),
                         "additional_forms": nuevos})
    nombre_tesauro = f"{idioma}.thesaurus.tsv"
    artefactos[nombre_tesauro] = buffer.getvalue().encode("utf-8")
    buffer = io.StringIO(newline="")
    buffer.write(f"# ipsis-vocabulary\t1\t{idioma}\n# written_form\tsource_ids...\n")
    escritor = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    for palabra, procedencia in sorted(palabras.items()):
        escritor.writerow([palabra, *sorted(procedencia)])
    nombre_vocabulario = f"{idioma}.vocabulary.tsv"
    artefactos[nombre_vocabulario] = buffer.getvalue().encode("utf-8")
    if any(len(artefactos[n]) > configuracion.get("max_supplement_bytes", 64 * 1024 * 1024)
           for n in [nombre_tesauro, nombre_vocabulario]):
        raise ValueError("Supplement output exceeds size budget")
    resumen = {"base_forms": originales, "unique_forms": len(palabras),
               "additional_forms": len(palabras) - originales,
               "single_lowercase_forms": sum(normalizar(p) is not None for p in palabras),
               "additional_single_lowercase_forms": sum(normalizar(p) is not None and p not in palabras_sueltas_originales
                                                         for p in palabras),
               "files": [{"filename": n, "bytes": len(artefactos[n]), "sha256": sha256(artefactos[n])}
                         for n in [nombre_tesauro, nombre_vocabulario]]}
    return artefactos, reportes, resumen


def leer_lmf(datos: bytes, idioma: str, version: str) -> dict[tuple[str, str], set[str]]:
    miembros: dict[str, set[str]] = defaultdict(set)
    categorias: dict[str, str] = {}
    encontrados = 0
    with gzip.GzipFile(fileobj=io.BytesIO(datos)) as comprimido:
        xml = comprimido.read(MAX_XML + 1)
    if len(xml) > MAX_XML:
        raise ValueError("Decompressed WN-LMF exceeds size budget")
    # ElementTree no descarga el DTD externo de WN-LMF. Rechazar entidades
    # internas evita expansión; los escapes XML normales siguen permitidos.
    if b"<!ENTITY" in xml:
        raise ValueError("Internal XML entities are not supported")
    activo = False
    for evento, elemento in ET.iterparse(io.BytesIO(xml), events=("start", "end")):
        nombre = _etiqueta(elemento)
        if evento == "start" and nombre == "Lexicon":
            activo = elemento.get("language") == idioma
            if activo:
                encontrados += 1
                if elemento.get("version") != version:
                    raise ValueError("WN-LMF lexicon version does not match pinned version")
        if evento != "end":
            continue
        if nombre == "LexicalEntry":
            if activo:
                lemas = [h for h in elemento if _etiqueta(h) == "Lemma"]
                if len(lemas) != 1:
                    raise ValueError("WN-LMF entry must have exactly one lemma")
                lema = lemas[0].get("writtenForm", "")
                pos = lemas[0].get("partOfSpeech", "")
                if pos in POS:
                    for sentido in elemento:
                        if _etiqueta(sentido) == "Sense":
                            synset = sentido.get("synset", "")
                            if not re.fullmatch(r"[\w.-]+", synset):
                                raise ValueError("Missing or invalid WN-LMF synset reference")
                            miembros[synset].add(lema)
            elemento.clear()
        elif nombre == "Synset":
            if activo:
                categorias[elemento.get("id", "")] = elemento.get("partOfSpeech", "")
            elemento.clear()  # sus relaciones no se usan para crear grupos
        elif nombre == "Lexicon":
            activo = False
            elemento.clear()
    if encontrados != 1 or not miembros:
        raise ValueError(f"Expected one nonempty WN-LMF lexicon in {idioma}")
    if any(categorias.get(synset) not in POS for synset in miembros):
        raise ValueError("WN-LMF references an undeclared synset or unsupported synset POS")
    # Los adjetivos satélite pueden declarar `a` en Lemma y `s` en Synset.
    # La identidad del grupo viene del synset, no se divide por esas variantes.
    return {(synset, categorias[synset]): lemas for synset, lemas in miembros.items()}


def normalizar(lema: str) -> str | None:
    limpio = unicodedata.normalize("NFC", lema.strip())
    # No convertir nombres propios en palabras comunes por bajar mayúsculas.
    if not limpio.isalpha() or not limpio.islower():
        return None
    return limpio.lower()


def filtrar(grupos: dict[tuple[str, str], set[str]], filtros: dict) -> tuple[list[tuple[str, str, tuple[str, ...]]], dict]:
    max_miembros, max_sentidos = filtros["max_members"], filtros["max_senses"]
    if not 2 <= max_miembros <= 32 or not 1 <= max_sentidos <= 10:
        raise ValueError("Invalid synonym filter limits")
    normalizados = {}
    sentidos: dict[str, set[tuple[str, str]]] = defaultdict(set)
    descartados = 0
    for clave, lemas in grupos.items():
        palabras = set()
        for lema in lemas:
            palabra = normalizar(lema)
            if palabra is None:
                descartados += 1
            else:
                palabras.add(palabra)
                # Contar incluso sentidos en grupos que luego se descartarán.
                sentidos[palabra].add(clave)
        normalizados[clave] = palabras
    salida = []
    causas: Counter = Counter()
    ambiguos = {p for p, ss in sentidos.items() if len(ss) > max_sentidos}
    for (synset, pos), palabras in sorted(normalizados.items()):
        if len(palabras) > max_miembros:
            causas["oversized"] += 1
            continue
        restantes = tuple(sorted(palabras - ambiguos))
        if len(restantes) < 2:
            causas["fewer_than_two"] += 1
            continue
        salida.append((synset, pos, restantes))
    resumen = {
        "input_groups": len(grupos), "input_lemma_memberships": sum(map(len, grupos.values())),
        "excluded_non_single_lowercase_memberships": descartados,
        "excluded_polysemous_lemmas": len(ambiguos),
        "discarded_groups": dict(sorted(causas.items())),
        "output_groups": len(salida), "output_unique_lemmas": len({p for _, _, ps in salida for p in ps}),
    }
    return salida, resumen


def construir_idioma(idioma: str, configuracion: dict, cache: Path, offline: bool = False,
                     cache_suplementos: Path = SUPLEMENTOS) -> tuple[dict[str, bytes], dict]:
    fuente = configuracion["sources"][idioma]
    entrada = obtener_archivo(fuente["data"], cache, offline)
    if fuente["format"] == "omw-tab":
        grupos = leer_omw(entrada, fuente["lemma_tag"])
    else:
        grupos = leer_lmf(entrada, idioma, fuente["version"])
    filas, resumen = filtrar(grupos, configuracion["filters"])
    lexico = serializar_lexico(grupos, idioma, fuente)
    if not filas:
        raise ValueError(f"No synonym groups survived for {idioma}")
    cabecera = (f"# ipsis-synonyms\t1\t{idioma}\n"
                f"# source\t{fuente['id']}\t{fuente['version']}\t{fuente['data']['sha256']}\n"
                "# synset_id\tpos\tlemmas...\n")
    tsv = (cabecera + "".join("\t".join([sid, pos, *lemas]) + "\n" for sid, pos, lemas in filas)).encode("utf-8")
    if len(tsv) > configuracion["filters"]["max_output_bytes"]:
        raise ValueError(f"TSV for {idioma} exceeds output size budget")
    if len(lexico) > configuracion.get("max_lexicon_bytes", 16 * 1024 * 1024):
        raise ValueError(f"Full lexicon for {idioma} exceeds size budget")
    artefactos = {f"{idioma}.tsv": tsv, f"{idioma}.lexicon.tsv": lexico}
    for aviso in fuente["notices"]:
        artefactos[f"licencias/{aviso['filename']}"] = obtener_archivo(aviso, cache, offline)
    reporte = {
        "schema_version": 1, "converter_version": VERSION_CONVERSOR, "language": idioma,
        "reviewed_on": configuracion["reviewed_on"], "source": fuente,
        "approved_on": configuracion.get("approved_on"),
        "filters": configuracion["filters"], "statistics": resumen,
        "output": {"filename": f"{idioma}.tsv", "bytes": len(tsv), "sha256": sha256(tsv)},
        "lexicon": {"filename": f"{idioma}.lexicon.tsv", "bytes": len(lexico), "sha256": sha256(lexico),
                    "groups": len(grupos), "unique_lemmas": len({p for lemas in grupos.values() for p in lemas})},
    }
    extra, suplementos, vocabulario = construir_suplementos(idioma, configuracion, cache_suplementos, grupos, offline)
    artefactos.update(extra)
    if suplementos:
        reporte["supplements"] = suplementos
        reporte["vocabulary"] = vocabulario
    if configuracion.get("dictionary_manifest"):
        ruta = Path(__file__).with_name("diccionarios.py")
        spec = importlib.util.spec_from_file_location("ipsis_dictionary_builder", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        diccionarios = modulo.cargar_fuentes(Path(__file__).with_name(configuracion["dictionary_manifest"]))
        if idioma in diccionarios["sources"]:
            datos, informe = modulo.construir(idioma, diccionarios["sources"][idioma], artefactos[f"{idioma}.vocabulary.tsv"],
                                             usar_lexico=not configuracion.get("_raw_dictionaries", False))
            artefactos.update(datos)
            reporte["dictionary"] = {"manifest": f"diccionarios/{idioma}.manifest.json", "statistics": informe["statistics"],
                                     "source": informe["source"]}
    artefactos[f"{idioma}.manifest.json"] = _json(reporte)
    return artefactos, reporte


def atribuciones(reportes: dict[str, dict]) -> bytes:
    lineas = ["# Fuentes de los sinónimos\n", "Archivos derivados; cada fuente conserva sus propios avisos y licencia.\n",
              "Conversión: pertenencia a synsets, normalización NFC y filtros de palabras, sentidos y tamaño.",
              "Cada *.lexicon.tsv conserva todos los lemas y sentidos originales, sin esos filtros.",
              "Los TSV WordNet omiten definiciones; las vistas de diccionario conservan glosas para revisión offline.",
              "No se convierten flexiones ni relaciones semánticas distintas de sinonimia en equivalencias.\n"]
    for idioma, reporte in sorted(reportes.items()):
        fuente = reporte["source"]
        lineas += [f"## {idioma}: {fuente['label']}\n", f"- Fuente: {fuente['homepage']}",
                   f"- Versión/instantánea: `{fuente['version']}`; revisión: {reporte['reviewed_on']}",
                   f"- Licencia declarada: {fuente['license']}", f"- Atribución: {fuente['attribution']}",
                   f"- Descarga: {fuente['data']['url']}", f"- SHA-256 de entrada: `{fuente['data']['sha256']}`",
                   f"- SHA-256 del TSV: `{reporte['output']['sha256']}`",
                   f"- Filtros y conteos: `{idioma}.manifest.json`"]
        if "lexicon" in reporte:
            lineas.append(f"- Léxico maestro completo: `{reporte['lexicon']['filename']}`, SHA-256 `{reporte['lexicon']['sha256']}`")
        lineas += [f"- Aviso original: [licencias/{n['filename']}](licencias/{n['filename']})" for n in fuente["notices"]]
        lineas.append("")
        for suplemento in reporte.get("supplements", []):
            extra = suplemento["source"]
            lineas += [f"### Complemento: {extra['label']}\n", f"- Fuente: {extra['homepage']}",
                       f"- Versión: `{extra['version']}`; licencia declarada: {extra['license']}",
                       f"- Atribución: {extra['attribution']}",
                       f"- Descarga: {extra['data']['url']}; SHA-256: `{extra['data']['sha256']}`",
                       "- Transformación: decodificación a UTF-8 y TSV; se conservan etiquetas y términos originales.",
                       "- Las filas son entradas dirigidas del tesauro, no synsets ni grupos de equivalencia.",
                       "- Modificación preparada el " + reporte["reviewed_on"] + "; datos para revisión offline.",
                       *[f"- Aviso: [licencias/{n['filename']}](licencias/{n['filename']})" for n in extra["notices"]], ""]
        if "dictionary" in reporte:
            fuente = reporte["dictionary"]["source"]
            lineas += [f"### Diccionario extenso: {fuente['label']}\n", f"- Fuente: {fuente['homepage']}",
                       f"- Instantánea: {fuente['version']}; licencia: {fuente['license']}",
                       f"- Atribución: {fuente['attribution']}", f"- Descarga: {fuente['data']['url']}",
                       f"- SHA-256 del gzip original completo: `{fuente['data']['sha256']}`",
                       "- Original completo archivado sin pérdida en partes bajo herramientas/sinonimos/datos/diccionarios/.",
                       "- Derivados: entradas léxicas, vocabulario tipado, flexiones y relaciones explícitas de sinonimia.",
                       "- Se omiten etimología, pronunciación, traducciones y ejemplos en la vista léxica; el original los conserva.",
                       "- Las flexiones, alternativas y palabras de diccionario no se convierten en equivalencias.",
                       f"- Cambios preparados el {fuente['prepared_on']}; manifiesto: `{reporte['dictionary']['manifest']}`",
                       *[f"- Aviso/procedencia: [licencias/{n['filename']}](licencias/{n['filename']})" for n in fuente["notices"]], ""]
    return ("\n".join(lineas) + "\n").encode("utf-8")


def ejecutar(idiomas: list[str], configuracion: dict, cache: Path, salida: Path,
             *, offline: bool = False, comprobar: bool = False, cache_suplementos: Path = SUPLEMENTOS) -> list[dict]:
    # Construir y validar todo antes de escribir: un hash incorrecto no deja
    # una publicación con solo parte de los idiomas solicitados.
    artefactos: dict[str, bytes] = {}
    reportes = {}
    for idioma in sorted(set(idiomas)):
        archivos, reporte = construir_idioma(idioma, configuracion, cache, offline or comprobar, cache_suplementos)
        artefactos.update(archivos)
        reportes[idioma] = reporte
    # Una construcción de un solo idioma conserva las atribuciones de otros
    # ya publicados en esa carpeta, sin regenerar ni tocar sus TSV.
    for manifiesto in salida.glob("*.manifest.json"):
        previo = json.loads(manifiesto.read_text(encoding="utf-8"))
        reportes.setdefault(previo["language"], previo)
    artefactos["FUENTES.md"] = atribuciones(reportes)
    if comprobar:
        diferentes = [n for n, contenido in artefactos.items()
                      if not (salida / n).is_file() or (salida / n).read_bytes() != contenido]
        if diferentes:
            raise ValueError("Generated files differ: " + ", ".join(diferentes))
    else:
        for nombre, contenido in artefactos.items():
            destino = salida / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_suffix(destino.suffix + ".tmp")
            temporal.write_bytes(contenido)
            temporal.replace(destino)
    return [reportes[i] for i in sorted(set(idiomas))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build reproducible synonym tables from pinned WordNet sources")
    parser.add_argument("language", choices=["es", "en", "pt", "all"])
    parser.add_argument("--sources", type=Path, default=FUENTES)
    parser.add_argument("--cache", type=Path, default=ORIGINALES)
    parser.add_argument("--supplement-cache", type=Path, default=SUPLEMENTOS)
    parser.add_argument("--output", type=Path, default=SALIDA)
    red = parser.add_mutually_exclusive_group()
    red.add_argument("--offline", action="store_true", help="Use verified local sources (default)")
    red.add_argument("--download", action="store_true", help="Explicitly allow downloads when updating a source")
    parser.add_argument("--archive-sources", type=Path, help="Save lossless original sources and notices from --cache, offline")
    parser.add_argument("--archive-supplements", type=Path, help="Save lossless supplements from --supplement-cache, offline")
    parser.add_argument("--check", action="store_true", help="Verify outputs byte for byte, offline, without writes")
    parser.add_argument("--raw-dictionaries", action="store_true", help="Parse complete dictionary snapshots instead of verified lexical projections")
    args = parser.parse_args(argv)
    try:
        configuracion = cargar_fuentes(args.sources)
        configuracion["_raw_dictionaries"] = args.raw_dictionaries
        idiomas = list(configuracion["sources"]) if args.language == "all" else [args.language]
        if args.archive_sources or args.archive_supplements:
            if args.check:
                raise ValueError("Source archiving cannot be combined with --check")
        if args.archive_sources:
            archivar_fuentes(configuracion, args.cache, args.archive_sources)
        if args.archive_supplements:
            archivar_fuentes(configuracion, args.supplement_cache, args.archive_supplements, suplementos=True)
        resultados = ejecutar(idiomas, configuracion, args.cache, args.output,
                              offline=not args.download, comprobar=args.check, cache_suplementos=args.supplement_cache)
    except (OSError, ValueError, ET.ParseError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    for r in resultados:
        print(f"{r['language']}: {r['statistics']['output_groups']} groups, "
              f"{r['statistics']['output_unique_lemmas']} lemmas, {r['output']['bytes']} bytes, "
              f"sha256={r['output']['sha256']}")
        print(f"  full lexicon: {r['lexicon']['groups']} synsets, {r['lexicon']['unique_lemmas']} lemmas")
        if "vocabulary" in r:
            print(f"  combined vocabulary: {r['vocabulary']['unique_forms']} forms, "
                  f"{r['vocabulary']['additional_forms']} additional")
        if "dictionary" in r:
            d = r["dictionary"]["statistics"]
            print(f"  extended dictionary: {d['combined_unique_forms']} forms, {d['additional_forms']} additional, "
                  f"{d['dictionary_lemma_forms']} lemma forms", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
