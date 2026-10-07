"""Diccionarios extensos: lectura incremental de instantáneas locales verificadas.

Las formas flexionadas y alternativas conservan su tipo; no son sinónimos.
No consulta la red. Los originales gzip se conservan íntegros en partes.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

VERSION = 1
RAIZ = Path(__file__).resolve().parents[2]
FUENTES = Path(__file__).with_name("diccionarios.json")
ORIGINALES = RAIZ / "herramientas/sinonimos/datos/diccionarios"
MAX_PARTE = 32 * 1024 * 1024
MAX_LINEA = 4 * 1024 * 1024
MAX_DESCOMPRIMIDO = 8 * 1024 * 1024 * 1024
TIPOS = {1: "lemma", 2: "inflected_entry", 4: "inflected_form", 8: "alternative",
         16: "explicit_synonym", 32: "legacy_vocabulary", 64: "unclassified_entry"}


def _json(objeto: dict) -> bytes:
    return (json.dumps(objeto, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def cargar_fuentes(ruta: Path = FUENTES) -> dict:
    cfg = json.loads(ruta.read_text(encoding="utf-8"))
    if cfg.get("schema_version") != 1 or set(cfg["sources"]) - {"es", "en", "pt"}:
        raise ValueError("Invalid dictionary manifest")
    for lang, fuente in cfg["sources"].items():
        specs = [*fuente["parts"], *fuente.get("lexical_parts", []), *fuente["notices"]]
        nombres = set()
        for spec in specs:
            if (not re.fullmatch(r"[\w.-]+", spec["filename"]) or spec["filename"] in nombres
                    or not re.fullmatch(r"[0-9a-f]{64}", spec["sha256"])
                    or not 0 < spec["bytes"] <= MAX_PARTE):
                raise ValueError(f"Invalid archived dictionary file for {lang}")
            nombres.add(spec["filename"])
        if (sum(s["bytes"] for s in fuente["parts"]) != fuente["data"]["bytes"]
                or not re.fullmatch(r"[0-9a-f]{64}", fuente["data"]["sha256"])
                or not fuente["data"]["url"].startswith("https://")):
            raise ValueError(f"Invalid complete dictionary specification for {lang}")
    return cfg


def verificar(fuente: dict, originales: Path) -> None:
    completo = hashlib.sha256()
    for spec in [*fuente["parts"], *fuente.get("lexical_parts", []), *fuente["notices"]]:
        parcial = hashlib.sha256()
        total = 0
        with (originales / spec["filename"]).open("rb") as f:
            while bloque := f.read(1024 * 1024):
                parcial.update(bloque)
                total += len(bloque)
                if spec in fuente["parts"]:
                    completo.update(bloque)
        if total != spec["bytes"] or parcial.hexdigest() != spec["sha256"]:
            raise ValueError(f"Dictionary checksum/size mismatch: {spec['filename']}")
    if completo.hexdigest() != fuente["data"]["sha256"]:
        raise ValueError("Complete dictionary checksum mismatch")


def archivar(original: Path, especificacion: dict, destino: Path, idioma: str) -> list[dict]:
    """Divide un gzip verificado sin modificar un solo byte de la descarga."""
    if idioma not in {"es", "en", "pt"}:
        raise ValueError("Unsupported dictionary language")
    digest = hashlib.sha256()
    total = 0
    with original.open("rb") as f:
        while datos := f.read(1024 * 1024):
            total += len(datos)
            digest.update(datos)
    if total != especificacion["bytes"] or digest.hexdigest() != especificacion["sha256"]:
        raise ValueError("Original download checksum/size mismatch")
    partes = []
    # Prevalidar cualquier archivo existente antes de guardar nuevas partes.
    with original.open("rb") as f:
        while datos := f.read(24 * 1024 * 1024):
            nombre = f"{idioma}.jsonl.gz.{len(partes) + 1:04d}.part"
            spec = {"filename": nombre, "bytes": len(datos), "sha256": hashlib.sha256(datos).hexdigest()}
            if (destino / nombre).exists() and (destino / nombre).read_bytes() != datos:
                raise ValueError(f"Archived original differs: {nombre}")
            partes.append(spec)
    destino.mkdir(parents=True, exist_ok=True)
    with original.open("rb") as f:
        for spec in partes:
            datos = f.read(spec["bytes"])
            if hashlib.sha256(datos).hexdigest() != spec["sha256"]:
                raise ValueError("Original changed during archiving")
            p = destino / spec["filename"]
            if not p.exists():
                p.write_bytes(datos)
    return partes


class _Partes(io.RawIOBase):
    def __init__(self, rutas: list[Path]):
        self.rutas = iter(rutas)
        self.actual = None

    def readable(self):
        return True

    def readinto(self, destino):
        while True:
            if self.actual is None:
                ruta = next(self.rutas, None)
                if ruta is None:
                    return 0
                self.actual = ruta.open("rb")
            n = self.actual.readinto(destino)
            if n:
                return n
            self.actual.close()
            self.actual = None

    def close(self):
        if self.actual is not None:
            self.actual.close()
        super().close()


def entradas(fuente: dict, originales: Path, *, usar_lexico: bool = True):
    verificar(fuente, originales)
    compacto = usar_lexico and bool(fuente.get("lexical_parts"))
    if compacto and fuente.get("lexical_schema_version") != VERSION:
        raise ValueError("Lexical snapshot schema changed; rebuild from raw dictionary")
    rutas = [originales / s["filename"] for s in (fuente["lexical_parts"] if compacto else fuente["parts"])]
    total = 0
    with io.BufferedReader(_Partes(rutas)) as partes, gzip.GzipFile(fileobj=partes) as raw:
        numero = 0
        while linea := raw.readline(MAX_LINEA + 1):
            numero += 1
            total += len(linea)
            if len(linea) > MAX_LINEA or total > MAX_DESCOMPRIMIDO:
                raise ValueError("Dictionary decompression exceeds budget")
            if linea.strip():
                objeto = json.loads(linea)
                if not isinstance(objeto, dict) or not isinstance(objeto.get("word"), str) or not objeto["word"]:
                    raise ValueError(f"Invalid dictionary entry on line {numero}")
                record_id = objeto.get("record_id") if compacto else numero
                if not isinstance(record_id, int) or record_id <= 0:
                    raise ValueError("Invalid lexical record identity")
                yield record_id, objeto


def _gzip(datos: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=buffer, mode="wb", mtime=0, compresslevel=6) as f:
        f.write(datos)
    return buffer.getvalue()


class _TSV:
    def __init__(self, columnas: list[str]):
        self.buffer = io.BytesIO()
        self.gz = gzip.GzipFile(filename="", fileobj=self.buffer, mode="wb", mtime=0, compresslevel=6)
        self.texto = io.TextIOWrapper(self.gz, encoding="utf-8", newline="")
        self.writer = csv.writer(self.texto, delimiter="\t", lineterminator="\n")
        self.writer.writerow(columnas)
        self.filas = 0

    def fila(self, campos):
        self.writer.writerow(campos)
        self.filas += 1

    def terminar(self):
        self.texto.flush()
        self.texto.detach().close()
        datos = self.buffer.getvalue()
        if len(datos) > MAX_PARTE:
            raise ValueError("Compressed dictionary output exceeds file budget")
        return datos


def _compactar(objeto: dict) -> dict:
    resultado = {k: objeto[k] for k in ("word", "lang_code", "pos", "forms", "synonyms", "etymology_number") if k in objeto}
    resultado["senses"] = [{k: s[k] for k in ("id", "glosses", "tags", "form_of", "alt_of", "synonyms") if k in s}
                           for s in objeto.get("senses", [])]
    return resultado


def _tipo(senses: list) -> int:
    flags = 0
    for sentido in senses:
        if sentido.get("form_of") or "form-of" in sentido.get("tags", []):
            flags |= 2
        elif sentido.get("alt_of") or "alt-of" in sentido.get("tags", []):
            flags |= 8
        else:
            flags |= 1
    return flags or 64


def construir(idioma: str, fuente: dict, vocabulario_previo: bytes, originales: Path = ORIGINALES,
              *, usar_lexico: bool = True) -> tuple[dict, dict]:
    previos = {fila[0] for fila in csv.reader(io.StringIO(vocabulario_previo.decode("utf-8")), delimiter="\t")
               if fila and not fila[0].startswith("#")}
    palabras = {p: 32 for p in previos}
    conteos = Counter()
    artefactos = {}
    bloque = io.BytesIO()
    numero_bloque = 0
    prefijo = f"diccionarios/{idioma}"
    formas = _TSV(["record_id", "pos", "headword", "form", "tags_json", "source_json"])
    sinonimos = _TSV(["record_id", "sense_id", "pos", "headword", "synonym", "qualifiers_json"])

    def guardar_bloque():
        nonlocal numero_bloque, bloque
        if not bloque.tell():
            return
        numero_bloque += 1
        artefactos[f"{prefijo}.entries.{numero_bloque:04d}.jsonl.gz"] = _gzip(bloque.getvalue())
        bloque = io.BytesIO()

    def agregar(palabra, flag):
        if isinstance(palabra, str) and palabra.strip() and palabra not in {"-", "—", "–"}:
            palabras[palabra] = palabras.get(palabra, 0) | flag

    for numero, objeto in entradas(fuente, originales, usar_lexico=usar_lexico):
        if objeto.get("lang_code") != idioma:
            raise ValueError(f"Dictionary contains unexpected language on line {numero}")
        palabra = objeto["word"]
        pos = objeto.get("pos", "")
        senses = objeto.get("senses", [])
        agregar(palabra, _tipo(senses))
        conteos["entries"] += 1
        conteos["proper_name_entries"] += pos == "name"
        reducido = _compactar(objeto)
        reducido["record_id"] = numero
        linea = _json(reducido)
        if bloque.tell() + len(linea) > 24 * 1024 * 1024:
            guardar_bloque()
        bloque.write(linea)
        for forma in objeto.get("forms", []):
            texto = forma.get("form")
            tags = forma.get("tags", [])
            if not isinstance(texto, str) or not texto.strip() or texto in {"-", "—", "–"}:
                continue
            if set(tags) & {"table-tags", "romanization", "transliteration", "ipa"}:
                conteos["excluded_nonlexical_forms"] += 1
                continue
            flag = 8 if set(tags) & {"alternative", "alternative-spelling", "variant"} else 4
            if "canonical" in tags:
                flag = _tipo(senses)
            agregar(texto, flag)
            formas.fila([numero, pos, palabra, texto, json.dumps(tags, ensure_ascii=False, sort_keys=True),
                         json.dumps(forma.get("source"), ensure_ascii=False, sort_keys=True)])
        for contexto in [objeto, *senses]:
            for sinonimo in contexto.get("synonyms", []):
                termino = sinonimo.get("word")
                if not isinstance(termino, str) or not termino.strip():
                    continue
                agregar(termino, 16)
                calificadores = {k: v for k, v in sinonimo.items() if k != "word"}
                sinonimos.fila([numero, contexto.get("id", "entry"), pos, palabra, termino,
                                json.dumps(calificadores, ensure_ascii=False, sort_keys=True)])
    guardar_bloque()
    if not conteos["entries"]:
        raise ValueError("Empty dictionary")
    vocabulario = _TSV(["written_form", "kinds"])
    for palabra, flags in sorted(palabras.items()):
        vocabulario.fila([palabra, ",".join(nombre for bit, nombre in TIPOS.items() if flags & bit)])
    artefactos[f"{prefijo}.vocabulary.tsv.gz"] = vocabulario.terminar()
    artefactos[f"{prefijo}.forms.tsv.gz"] = formas.terminar()
    artefactos[f"{prefijo}.synonym-edges.tsv.gz"] = sinonimos.terminar()
    for aviso in fuente["notices"]:
        artefactos[f"licencias/{aviso['filename']}"] = (originales / aviso["filename"]).read_bytes()
    resumen = {**conteos, "legacy_unique_forms": len(previos), "combined_unique_forms": len(palabras),
               "additional_forms": len(palabras) - len(previos),
               "single_lowercase_forms": sum(p.isalpha() and p.islower() for p in palabras),
               "additional_single_lowercase_forms": sum(p not in previos and p.isalpha() and p.islower() for p in palabras),
               "dictionary_lemma_forms": sum(bool(flags & 1) for flags in palabras.values()),
               "inflected_or_alternative_forms": sum(bool(flags & (2 | 4 | 8)) for flags in palabras.values()),
               "form_records": formas.filas, "synonym_records": sinonimos.filas}
    reporte = {"schema_version": 1, "converter_version": VERSION, "language": idioma, "source": fuente,
               "legacy_vocabulary_sha256": hashlib.sha256(vocabulario_previo).hexdigest(),
               "statistics": resumen, "files": [{"filename": n, "bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()}
                                                 for n, d in sorted(artefactos.items())]}
    artefactos[f"{prefijo}.manifest.json"] = _json(reporte)
    return artefactos, reporte
