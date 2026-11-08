"""Conjunto v2, compartido por el experimento 1 (afinado) y el 2 (edición de pesos). Diseño: ``conjunto_v2.md``.

**Regla de etiquetas: sin juez externo.** Un pasaje es correcto o incorrecto solo por:

- un juicio humano publicado (MIRACL y NoMIRACL);
- el tramo de respuesta de un conjunto extractivo (SQAC, MLQA, XQuAD): correcto si contiene la respuesta,
  incorrecto si no la contiene.

Ningún modelo decide una etiqueta. bge solo **ordena** candidatos para elegir negativas difíciles y para medir la
línea base.

Etapas, en orden. Cada una lee la salida de la anterior en ``.cache/laboratorio-reranker/conjunto-v2/`` y escribe
la suya con ``resumen.json``:

    python laboratorio_reranker/conjunto.py recolectar          # 1. descarga las fuentes con revisión fijada
    python laboratorio_reranker/conjunto.py armar-candidatos    # 2. pasajes y candidatos etiquetados por pregunta
    python laboratorio_reranker/conjunto.py puntuar-base        # 3. bge int8 del motor sobre cada candidato (lento)
    python laboratorio_reranker/conjunto.py descartar-dudosas   # 4. quita negativas que podrían responder (reglas)
    python laboratorio_reranker/conjunto.py separar-particiones # 5. entrenamiento / desarrollo / prueba, sin fugas
    python laboratorio_reranker/conjunto.py exportar-parafrasis --parte evaluacion|entrenamiento  # 6a. preguntas a reescribir en registro informal
    python laboratorio_reranker/conjunto.py importar-parafrasis # 6b. valida y agrega las paráfrasis
    python laboratorio_reranker/conjunto.py congelar            # 7. archivos finales, hashes y línea base
    python laboratorio_reranker/conjunto.py evaluar --modelo onnx-int8|local:<carpeta>   # antes y después

Todo es determinista: semilla fija, revisiones fijadas y orden estable.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from comun import SALIDA

RAIZ = SALIDA / "conjunto-v2"
FUENTES_DIR = RAIZ / "1-fuentes"
SEMILLA = 13
_TILDES = str.maketrans("áéíóúÁÉÍÓÚüÜñÑ", "aeiouAEIOUuUnN")

# ---------------------------------------------------------------------------
# Fuentes: revisión fijada, licencia y tipo de etiqueta (README de la etapa 1 en conjunto_v2.md)
# ---------------------------------------------------------------------------
HF = "https://huggingface.co/datasets"
NOMIRACL_REV = "ecd08778d0426a5ca28ac99763b0c9ddc2c78e68"
MIRACL_REV = "5be20db9509754dadad47689368639fcec739c00"
MIRACL_CORPUS_REV = "d921ec7e349ce0d28daf30b2da9da5ee698bef0d"
SQAC_REV = "f9928e8819596a601b8887cc5f8598b15d589a82"
XQUAD_REV = "51adfef1c1287aab1d2d91b5bead9bcfb9c68583"
MLQA_URL, MLQA_SHA = "https://dl.fbaipublicfiles.com/MLQA/MLQA_V1.zip", \
    "246e8089933d13007fe80684d5c5c0713d6834cf8b3b4a0ec7c66f0a0d2baac8"

FUENTES = {
    # Juicios originales de MIRACL (qrels): ~10 pasajes juzgados por pregunta. La versión ``es-triplet-all`` de
    # sentence-transformers NO sirve: sus 100 negativas por pregunta son minadas, no juzgadas.
    "miracl": {"licencia": "Apache-2.0", "etiqueta": "humano", "archivos": {
        "miracl-topics-train.tsv": f"{HF}/miracl/miracl/resolve/{MIRACL_REV}/miracl-v1.0-es/topics/"
                                   "topics.miracl-v1.0-es-train.tsv",
        "miracl-qrels-train.tsv": f"{HF}/miracl/miracl/resolve/{MIRACL_REV}/miracl-v1.0-es/qrels/"
                                  "qrels.miracl-v1.0-es-train.tsv",
        **{f"miracl-corpus-{k}.jsonl.gz": f"{HF}/miracl/miracl-corpus/resolve/{MIRACL_CORPUS_REV}/"
                                          f"miracl-corpus-v1.0-es/docs-{k}.jsonl.gz" for k in range(21)}}},
    "nomiracl": {"licencia": "Apache-2.0 (textos CC BY-SA)", "etiqueta": "humano", "archivos": {
        "nomiracl-corpus.jsonl.gz": f"{HF}/miracl/nomiracl/resolve/{NOMIRACL_REV}/data/spanish/corpus.jsonl.gz",
        **{f"nomiracl-{t}-{s}.tsv": f"{HF}/miracl/nomiracl/resolve/{NOMIRACL_REV}/data/spanish/{t}/{s}.relevant.tsv"
           for t in ("topics", "qrels") for s in ("dev", "test")},
        **{f"nomiracl-topics-{s}-nr.tsv": f"{HF}/miracl/nomiracl/resolve/{NOMIRACL_REV}/data/spanish/topics/"
                                          f"{s}.non_relevant.tsv" for s in ("dev", "test")}}},
    "sqac": {"licencia": "CC BY-SA 4.0", "etiqueta": "tramo", "archivos": {
        f"sqac-{s}.json": f"{HF}/PlanTL-GOB-ES/SQAC/resolve/{SQAC_REV}/{s}.json" for s in ("train", "dev", "test")}},
    "mlqa": {"licencia": "CC BY-SA 3.0", "etiqueta": "tramo", "archivos": {"mlqa.zip": MLQA_URL}},
    "xquad": {"licencia": "CC BY-SA 4.0", "etiqueta": "tramo", "archivos": {
        "xquad-es.parquet": f"{HF}/google/xquad/resolve/{XQUAD_REV}/xquad.es/validation-00000-of-00001.parquet"}},
}

# Número de candidatos por pregunta en las fuentes de tramo: 1 positivo + negativas.
MAX_CONTEXTO, MAX_ARTICULO, MAX_NEGATIVAS = 4, 3, 11
# NoMIRACL se deja igual que en el v1 (``datos.nomiracl``): hasta 10 pasajes juzgados por pregunta.
MAX_NOMIRACL = 10
MAX_MIRACL_POSITIVOS = 3


def _normal(texto: str) -> str:
    return " ".join(texto.lower().translate(_TILDES).split())


def _sha(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _azar(*partes) -> random.Random:
    return random.Random(int(hashlib.sha256(":".join(map(str, (SEMILLA, *partes))).encode()).hexdigest()[:12], 16))


def _leer(ruta: Path) -> list[dict]:
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def _escribir(ruta: Path, filas) -> str:
    """Siempre con finales LF: en Windows ``write_text`` escribiría CRLF y el SHA-256 no coincidiría entre
    máquinas."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas).encode("utf-8"))
    return _sha(ruta)


def _sha_lf(ruta: Path) -> str:
    """SHA-256 con los finales de línea normalizados a LF (archivos escritos en Windows antes de la corrección)."""
    return hashlib.sha256(ruta.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _resumen(carpeta: Path, datos: dict) -> None:
    """Escribe ``resumen.json``. Si la etapa corrió solo sobre algunos archivos (``--solo``), conserva los demás."""
    carpeta.mkdir(parents=True, exist_ok=True)
    previo = carpeta / "resumen.json"
    if "archivos" in datos and previo.exists():
        anteriores = json.loads(previo.read_text(encoding="utf-8")).get("archivos", {})
        datos["archivos"] = {**anteriores, **datos["archivos"]}
    (carpeta / "resumen.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(datos, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Etapa 1: recolectar
# ---------------------------------------------------------------------------
def recolectar(_args) -> None:
    import urllib.request

    FUENTES_DIR.mkdir(parents=True, exist_ok=True)
    huellas = {}
    for fuente, meta in FUENTES.items():
        for nombre, url in meta["archivos"].items():
            destino = FUENTES_DIR / nombre
            if not destino.exists():
                print(f"descargando {nombre}", file=sys.stderr)
                urllib.request.urlretrieve(url, destino.with_suffix(".parcial"))
                destino.with_suffix(".parcial").rename(destino)
            huellas[nombre] = {"fuente": fuente, "url": url, "sha256": _sha(destino)}
    if huellas["mlqa.zip"]["sha256"] != MLQA_SHA:
        raise SystemExit("MLQA_V1.zip cambió: el sha256 no coincide con el fijado")
    _resumen(FUENTES_DIR, {"etapa": "1-recolectar", "archivos": huellas,
                           "licencias": {f: m["licencia"] for f, m in FUENTES.items()}})


# ---------------------------------------------------------------------------
# Etapa 2: armar candidatos
# ---------------------------------------------------------------------------
def _tsv(ruta: Path) -> list[list[str]]:
    return [l.rstrip("\n").split("\t") for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def _candidato(texto: str, correcto: bool, tipo: str, verificacion: str, documento: str = "") -> dict:
    return {"texto": texto, "correcto": correcto, "tipo": tipo, "verificacion": verificacion, "documento": documento}


def _barajar(pregunta: dict) -> dict:
    """Orden fijo pero arbitrario de los candidatos: así el vecino de lote del int8 no depende de la etiqueta."""
    _azar(pregunta["id"]).shuffle(pregunta["candidatos"])
    return pregunta


def preguntas_nomiracl(split: str) -> list[dict]:
    """Como ``datos.nomiracl`` (v1): solo pasajes juzgados por nativos; hasta 10 por pregunta."""
    corpus = {}
    with gzip.open(FUENTES_DIR / "nomiracl-corpus.jsonl.gz", "rt", encoding="utf-8") as f:
        for linea in f:
            doc = json.loads(linea)
            corpus[doc["docid"]] = (f"{doc['title']}\n{doc['text']}", doc["title"])
    preguntas = {f[0]: f[1] for f in _tsv(FUENTES_DIR / f"nomiracl-topics-{split}.tsv")}
    juicios = defaultdict(dict)
    for qid, _, docid, rel in _tsv(FUENTES_DIR / f"nomiracl-qrels-{split}.tsv"):
        if docid in corpus:
            juicios[qid][docid] = int(rel) > 0
    filas = []
    for qid, texto in sorted(preguntas.items()):
        docs = juicios.get(qid, {})
        pos = sorted(d for d, ok in docs.items() if ok)
        neg = sorted(d for d, ok in docs.items() if not ok)
        if not pos or not neg:
            continue
        elegidos = pos[:MAX_NOMIRACL - 1] + neg[:max(1, MAX_NOMIRACL - len(pos[:MAX_NOMIRACL - 1]))]
        filas.append(_barajar({
            "id": f"nomiracl-{split}-{qid}", "fuente": "nomiracl", "origen_split": split, "query": texto,
            "documento": corpus[pos[0]][1], "respuestas": [],
            "candidatos": [_candidato(corpus[d][0], docs[d], "juzgada" if not docs[d] else "positivo", "humano",
                                      corpus[d][1]) for d in elegidos]}))
    return filas


def preguntas_miracl() -> list[dict]:
    """MIRACL ``train``: todos los pasajes juzgados por nativos (el v1 usaba una sola negativa juzgada)."""
    juicios = defaultdict(dict)
    for qid, _, docid, rel in _tsv(FUENTES_DIR / "miracl-qrels-train.tsv"):
        juicios[qid][docid] = int(rel) > 0
    necesarios = {d for docs in juicios.values() for d in docs}
    corpus = {}
    for k in range(21):
        with gzip.open(FUENTES_DIR / f"miracl-corpus-{k}.jsonl.gz", "rt", encoding="utf-8") as f:
            for linea in f:
                doc = json.loads(linea)
                if doc["docid"] in necesarios:
                    corpus[doc["docid"]] = (f"{doc['title']}\n{doc['text']}", doc["title"])
    preguntas = {f[0]: f[1] for f in _tsv(FUENTES_DIR / "miracl-topics-train.tsv")}
    filas = []
    for qid, texto in sorted(preguntas.items()):
        docs = {d: ok for d, ok in juicios.get(qid, {}).items() if d in corpus}
        pos = sorted(d for d, ok in docs.items() if ok)[:MAX_MIRACL_POSITIVOS]
        neg = sorted(d for d, ok in docs.items() if not ok)
        if not pos or not neg:
            continue
        filas.append({"id": f"miracl-train-{qid}", "fuente": "miracl", "origen_split": "train", "query": texto,
                      "documento": corpus[pos[0]][1], "respuestas": [],
                      "candidatos": [_candidato(corpus[d][0], docs[d], "positivo" if docs[d] else "juzgada",
                                                "humano", corpus[d][1]) for d in pos + neg]})
    _completar_lexicas(filas, MAX_NEGATIVAS, "miracl")
    return [_barajar(f) for f in filas]


def _completar_lexicas(filas: list[dict], max_neg: int, nombre: str) -> None:
    """Completa con pasajes de **otro documento** (otro artículo) parecidos por TF-IDF a la pregunta.

    Su etiqueta «incorrecto» es una regla, no un juicio: un pasaje de otro artículo rara vez responde. En las fuentes
    de tramo, además, se exige que no contenga la respuesta.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    banco, vistos = [], set()
    for f in filas:
        for c in f["candidatos"]:
            if c["texto"] not in vistos:
                vistos.add(c["texto"])
                banco.append((c["texto"], c["documento"]))
    vectorizador = TfidfVectorizer(sublinear_tf=True, min_df=2)
    matriz = vectorizador.fit_transform([t for t, _ in banco])
    consultas = vectorizador.transform([f["query"] for f in filas])
    print(f"[{nombre}] completando negativas léxicas para {len(filas)} preguntas", file=sys.stderr)
    for k, f in enumerate(filas):
        faltan = max_neg - sum(not c["correcto"] for c in f["candidatos"])
        if faltan <= 0:
            continue
        propios = {c["documento"] for c in f["candidatos"]}
        textos = {c["texto"] for c in f["candidatos"]}
        respuestas = [_normal(r) for r in f["respuestas"]]
        fila = (matriz @ consultas[k].T).toarray().ravel()
        for i in fila.argsort()[::-1][:200]:
            texto, documento = banco[int(i)]
            if documento in propios or texto in textos or any(r in _normal(texto) for r in respuestas):
                continue
            f["candidatos"].append(_candidato(texto, False, "otro_documento", "regla_otro_documento", documento))
            textos.add(texto)
            faltan -= 1
            if not faltan:
                break


def _articulos_tramo(fuente: str, split: str) -> list[dict]:
    """Lista de artículos ``{"titulo", "parrafos": [{"contexto", "qas"}]}`` en el formato de SQuAD."""
    if fuente == "sqac":
        datos = json.loads((FUENTES_DIR / f"sqac-{split}.json").read_text(encoding="utf-8"))["data"]
        # En AnCora el «título» es un nombre de archivo (CESS-CAST-…): no aporta contexto (v1, OBS-0012).
        return [{"titulo": "" if a.get("source") == "ancora" else a["title"], "id": f"{a.get('source', '')}:{a['title']}",
                 "parrafos": [{"contexto": p["context"], "qas": p["qas"]} for p in a["paragraphs"]]} for a in datos]
    if fuente == "mlqa":
        with zipfile.ZipFile(FUENTES_DIR / "mlqa.zip") as z:
            datos = json.loads(z.read(f"MLQA_V1/{split}/{split}-context-es-question-es.json"))["data"]
        return [{"titulo": a["title"], "id": a["title"],
                 "parrafos": [{"contexto": p["context"], "qas": p["qas"]} for p in a["paragraphs"]]} for a in datos]
    if fuente == "xquad":
        import pyarrow.parquet as pq

        por_contexto = defaultdict(list)
        for fila in pq.read_table(FUENTES_DIR / "xquad-es.parquet").to_pylist():
            por_contexto[fila["context"]].append({"id": fila["id"], "question": fila["question"], "answers": [
                {"text": t, "answer_start": s} for t, s in zip(fila["answers"]["text"], fila["answers"]["answer_start"],
                                                               strict=True)]})
        # XQuAD no trae título: cada contexto es su propio documento (240 contextos de 48 artículos).
        return [{"titulo": "", "id": f"xquad:{hashlib.sha1(c.encode()).hexdigest()[:10]}",
                 "parrafos": [{"contexto": c, "qas": qas}]} for c, qas in sorted(por_contexto.items())]
    raise ValueError(fuente)


def preguntas_tramo(fuente: str, split: str, limite: int | None = None) -> list[dict]:
    """Fuentes extractivas. Cada contexto se parte en tramos de 2 oraciones con el título como primera línea (igual
    que el v1). Positivo: el tramo que contiene todo el tramo de respuesta. Negativas, en este orden:

    1. ``hermana_contexto``: otro tramo del mismo párrafo (mismo tema, otro aspecto);
    2. ``hermana_articulo``: un tramo de otro párrafo del mismo artículo;
    3. ``otro_documento``: el tramo de otro artículo más parecido a la pregunta (TF-IDF).

    Una negativa nunca contiene el texto normalizado de ninguna de las respuestas aceptadas.
    """
    from ipsis.lenguaje.texto import dividir_oraciones

    articulos = _articulos_tramo(fuente, split)
    filas = []
    for a in articulos:
        cabeza = f"{a['titulo']}\n" if a["titulo"] else ""
        tramos = []  # (parrafo, ini, fin, texto)
        for p, parrafo in enumerate(a["parrafos"]):
            ctx = parrafo["contexto"]
            oraciones = dividir_oraciones(ctx)
            for k in range(0, len(oraciones), 2):
                ini, fin = oraciones[k][0], oraciones[min(k + 1, len(oraciones) - 1)][1]
                tramos.append((p, ini, fin, f"{cabeza}{ctx[ini:fin].strip()}"))
        for p, parrafo in enumerate(a["parrafos"]):
            for qa in parrafo["qas"]:
                if not qa.get("answers"):
                    continue
                r0 = qa["answers"][0]
                ini, fin = r0["answer_start"], r0["answer_start"] + len(r0["text"])
                pos = [t for t in tramos if t[0] == p and t[1] <= ini and fin <= t[2]]
                if not pos:
                    continue  # la respuesta cruza dos tramos
                respuestas = sorted({x["text"] for x in qa["answers"]})
                valido = lambda t: not any(_normal(r) in _normal(t[3]) for r in respuestas)  # noqa: E731
                azar = _azar(fuente, qa["id"])
                contexto = [t for t in tramos if t[0] == p and t != pos[0] and valido(t)]
                articulo = [t for t in tramos if t[0] != p and valido(t)]
                azar.shuffle(contexto)
                azar.shuffle(articulo)
                candidatos = [_candidato(pos[0][3], True, "positivo", "tramo", a["id"])]
                candidatos += [_candidato(t[3], False, "hermana_contexto", "tramo", a["id"])
                               for t in contexto[:MAX_CONTEXTO]]
                candidatos += [_candidato(t[3], False, "hermana_articulo", "tramo", a["id"])
                               for t in articulo[:MAX_ARTICULO]]
                filas.append({"id": f"{fuente}-{split}-{qa['id']}", "fuente": fuente, "origen_split": split,
                              "query": qa["question"], "documento": a["id"], "respuestas": respuestas,
                              "candidatos": candidatos})
    if limite and len(filas) > limite:
        _azar(fuente, split, "muestra").shuffle(filas)
        filas = sorted(filas[:limite], key=lambda f: f["id"])
    _completar_lexicas(filas, MAX_NEGATIVAS, f"{fuente}-{split}")
    return [_barajar(f) for f in filas]


def armar_candidatos(args) -> None:
    destino = RAIZ / "2-candidatos"
    conjuntos = {
        "nomiracl-dev": lambda: preguntas_nomiracl("dev"),
        "nomiracl-test": lambda: preguntas_nomiracl("test"),
        "miracl-train": preguntas_miracl,
        "sqac-train": lambda: preguntas_tramo("sqac", "train", args.limite_sqac),
        "sqac-dev": lambda: preguntas_tramo("sqac", "dev"),
        "sqac-test": lambda: preguntas_tramo("sqac", "test"),
        "mlqa-dev": lambda: preguntas_tramo("mlqa", "dev"),
        "mlqa-test": lambda: preguntas_tramo("mlqa", "test"),
        "xquad-test": lambda: preguntas_tramo("xquad", "test"),
    }
    resumen = {"etapa": "2-armar-candidatos", "semilla": SEMILLA, "archivos": {}}
    for nombre, crear in conjuntos.items():
        if args.solo and nombre not in args.solo:
            continue
        filas = crear()
        sha = _escribir(destino / f"{nombre}.jsonl", filas)
        tipos = Counter(c["tipo"] for f in filas for c in f["candidatos"])
        resumen["archivos"][nombre] = {"preguntas": len(filas), "pares": sum(len(f["candidatos"]) for f in filas),
                                       "tipos": dict(tipos), "sha256": sha}
    _resumen(destino, resumen)


# ---------------------------------------------------------------------------
# Etapa 3: puntuar con el modelo base (bge int8 del motor, lote 2, 256 tokens)
# ---------------------------------------------------------------------------
def _puntuar_archivo(scorer, origen: Path, destino: Path, etiqueta: str, lote: int = 2) -> dict:
    """Agrega ``puntajes`` y ``tokens`` por candidato. Reanudable: salta las preguntas ya puntuadas."""
    hechas = {f["id"] for f in _leer(destino)} if destino.exists() else set()
    filas = [f for f in _leer(origen) if f["id"] not in hechas]
    inicio, n = time.time(), 0
    with destino.open("a", encoding="utf-8") as salida:
        for f in filas:
            textos = [c["texto"] for c in f["candidatos"]]
            puntajes = scorer.puntuar(f["query"], textos, lote=lote)
            for c, s in zip(f["candidatos"], puntajes, strict=True):
                c["base"] = round(float(s), 5)
            salida.write(json.dumps(f, ensure_ascii=False) + "\n")
            n += 1
            if n % 50 == 0:
                ritmo = (time.time() - inicio) / n
                print(f"[{etiqueta}] {n}/{len(filas)}  {ritmo:.2f} s/pregunta  "
                      f"faltan {ritmo * (len(filas) - n) / 60:.0f} min", file=sys.stderr, flush=True)
    return {"nuevas": n, "ya_hechas": len(hechas), "segundos": round(time.time() - inicio, 1)}


EVALUACION = ["nomiracl-test", "nomiracl-dev", "xquad-test", "sqac-test", "sqac-dev"]
ENTRENAMIENTO = ["mlqa-dev", "miracl-train", "mlqa-test", "sqac-train"]


def puntuar_base(args) -> None:
    """Desarrollo y prueba siempre con el int8 del motor en CPU: es la línea base del «antes». Los conjuntos de
    entrenamiento pueden puntuarse en GPU (``--gpu``, PyTorch): ahí el puntaje solo **ordena** negativas y marca la
    dificultad, y queda anotado qué modelo lo produjo."""
    from comun import ScorerOnnx, crear_scorer, entorno

    origen, destino = RAIZ / "2-candidatos", RAIZ / "3-puntuados"
    destino.mkdir(parents=True, exist_ok=True)
    orden = args.solo or EVALUACION + ENTRENAMIENTO
    cpu = ScorerOnnx("int8", hilos=args.hilos)
    gpu = crear_scorer(f"torch-{args.gpu}-cuda", base=cpu) if args.gpu else None
    resumen = {"etapa": "3-puntuar-base", "lote": 2, "max_tokens": cpu.max_tokens, "entorno": entorno(args.hilos),
               "archivos": {}}
    for nombre in orden:
        # El int8 va con lote 2, como el motor (su cuantización dinámica depende del lote). En la GPU (PyTorch, sin
        # cuantización) el lote no cambia los logits: se puntúan todos los candidatos de una pregunta juntos.
        scorer, lote = (gpu, 32) if gpu and nombre in ENTRENAMIENTO else (cpu, 2)
        resumen["archivos"][nombre] = {"modelo": scorer.nombre, "lote": lote, **_puntuar_archivo(
            scorer, origen / f"{nombre}.jsonl", destino / f"{nombre}.jsonl", nombre, lote)}
    _resumen(destino, resumen)


PUNTAJES_VERSIONADOS = Path(__file__).with_name("puntajes_base.json.gz")


def _huella_texto(texto: str) -> str:
    return hashlib.sha1(texto.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:12]


def exportar_puntajes(args) -> None:
    """Guarda en el repo solo los **números** de la etapa 3 (sin textos, que tienen licencias propias): por pregunta,
    la huella (SHA-1 corto) de cada candidato y su puntaje. Otra máquina los importa emparejando por huella."""
    from comun import entorno

    ruta3 = RAIZ / "3-puntuados" / "resumen.json"  # puede faltar si la etapa se cortó antes de escribirlo
    resumen3 = json.loads(ruta3.read_text(encoding="utf-8")) if ruta3.exists() else {"archivos": {}}
    salida = {"etapa": "3-puntuar-base (exportado)", "entorno": entorno(None), "archivos": {}}
    for nombre in args.solo:
        candidatos = RAIZ / "2-candidatos" / f"{nombre}.jsonl"
        filas = _leer(RAIZ / "3-puntuados" / f"{nombre}.jsonl")
        esperadas = sum(1 for _ in candidatos.open(encoding="utf-8"))
        if len(filas) != esperadas:
            raise SystemExit(f"{nombre}: {len(filas)} de {esperadas} preguntas puntuadas; terminar la etapa 3 antes")
        salida["archivos"][nombre] = {
            "sha256_candidatos": _sha_lf(candidatos),
            "modelo": resumen3["archivos"].get(nombre, {}).get("modelo", "onnx-int8"),
            "puntajes": {f["id"]: {_huella_texto(c["texto"]): c["base"] for c in f["candidatos"]} for f in filas},
            "tipos": {f["id"]: {_huella_texto(c["texto"]): c["tipo"] for c in f["candidatos"]} for f in filas}}
    with gzip.open(PUNTAJES_VERSIONADOS, "wt", encoding="utf-8") as f:
        json.dump(salida, f)
    print(f"{', '.join(args.solo)} -> {PUNTAJES_VERSIONADOS.name} ({_sha(PUNTAJES_VERSIONADOS)[:16]})")


def importar_puntajes(args) -> None:
    """Arma ``3-puntuados/<archivo>.jsonl`` desde ``puntajes_base.json.gz``, emparejando cada candidato local con el
    puntuado por la huella de su texto. Si el archivo de candidatos no es idéntico (SHA-256) pero cada pregunta tiene
    el mismo conjunto de textos, solo cambió el orden y se importa igual. Si algún conjunto difiere, informa qué
    tipos de candidato difieren y no escribe nada."""
    with gzip.open(PUNTAJES_VERSIONADOS, "rt", encoding="utf-8") as f:
        datos = json.load(f)
    destino = RAIZ / "3-puntuados"
    resumen = {"etapa": "3-puntuar-base (importado)", "origen": datos["entorno"], "archivos": {}}
    problemas = {}
    for nombre, meta in datos["archivos"].items():
        candidatos = RAIZ / "2-candidatos" / f"{nombre}.jsonl"
        identico = _sha_lf(candidatos) == meta["sha256_candidatos"]
        filas, diferencias = _leer(candidatos), Counter()
        for fila in filas:
            remotos = meta["puntajes"].get(fila["id"])
            if remotos is None:
                diferencias["pregunta_ausente_en_el_origen"] += 1
                continue
            locales = {_huella_texto(c["texto"]): c for c in fila["candidatos"]}
            if set(locales) != set(remotos):
                for h in set(locales) - set(remotos):
                    diferencias[f"solo_local:{locales[h]['tipo']}"] += 1
                for h in set(remotos) - set(locales):
                    diferencias[f"solo_origen:{meta['tipos'][fila['id']][h]}"] += 1
                diferencias["preguntas_distintas"] += 1
                continue
            if [_huella_texto(c["texto"]) for c in fila["candidatos"]] != list(remotos):
                diferencias["solo_cambia_el_orden"] += 1
            # Por candidato, no por huella única: una pregunta puede repetir el mismo texto en dos candidatos
            # (pasajes duplicados del corpus), y el diccionario ``locales`` solo guarda uno de ellos.
            for c in fila["candidatos"]:
                c["base"] = remotos[_huella_texto(c["texto"])]
        diferencias["preguntas_sin_origen"] = len(set(meta["puntajes"]) - {f["id"] for f in filas})
        if diferencias["preguntas_distintas"] or diferencias["pregunta_ausente_en_el_origen"]:
            detalle = {"preguntas": len(filas), **{k: v for k, v in diferencias.items() if v}}
            local = destino / f"{nombre}.jsonl"
            # Con --conservar-locales se usa la puntuación hecha en esta máquina, si está completa.
            if getattr(args, "conservar_locales", False) and local.exists() and \
                    {f["id"] for f in _leer(local)} == {f["id"] for f in filas}:
                resumen["archivos"][nombre] = {"modelo": "puntuado en esta máquina (no importado)",
                                               "candidatos_distintos": detalle, "sha256": _sha(local)}
            else:
                problemas[nombre] = detalle
            continue
        resumen["archivos"][nombre] = {"modelo": f"{meta['modelo']} (importado)", "preguntas": len(filas),
                                       "identico": identico, **{k: v for k, v in diferencias.items() if v},
                                       "sha256": _escribir(destino / f"{nombre}.jsonl", filas)}
    _resumen(destino, resumen)
    if problemas:
        print(json.dumps({"candidatos_distintos": problemas}, ensure_ascii=False, indent=2))
        raise SystemExit("hay preguntas con candidatos distintos entre máquinas: esos archivos no se importaron. "
                         "Puntuarlos aquí (puntuar-base --solo …) y repetir con --conservar-locales")


def probar_gpu(_args) -> None:
    """Diagnóstico: ¿torch ve la GPU, el modelo queda en ella y cuánto tarda por pregunta en GPU y en CPU int8?"""
    import torch

    from comun import ScorerOnnx, crear_scorer

    print(f"torch {torch.__version__}  cuda compilado: {torch.version.cuda}  disponible: {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        raise SystemExit("torch no ve la GPU: reinstalar torch desde el índice cu126 (README de conjunto_v2.md)")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    f = _leer(RAIZ / "2-candidatos" / "miracl-train.jsonl")[0]
    textos = [c["texto"] for c in f["candidatos"]]
    cpu = ScorerOnnx("int8")
    gpu = crear_scorer("torch-fp16-cuda", base=cpu)
    print(f"modelo en: {next(gpu.modelo.parameters()).device}  tipo: {next(gpu.modelo.parameters()).dtype}")
    for nombre, scorer, lote in (("gpu fp16, lote 32", gpu, 32), ("gpu fp16, lote 2", gpu, 2),
                                 ("cpu int8, lote 2", cpu, 2)):
        scorer.puntuar(f["query"], textos, lote=lote)  # calentamiento
        if scorer is gpu:
            torch.cuda.synchronize()
        inicio = time.time()
        for _ in range(3):
            scorer.puntuar(f["query"], textos, lote=lote)
        if scorer is gpu:
            torch.cuda.synchronize()
        print(f"{nombre}: {(time.time() - inicio) / 3:.2f} s por pregunta ({len(textos)} candidatos)")


def rango_mejor_positivo(f: dict, clave: str = "base") -> int:
    orden = sorted(range(len(f["candidatos"])), key=lambda i: (-f["candidatos"][i][clave], i))
    return next(r for r, i in enumerate(orden, 1) if f["candidatos"][i]["correcto"])


# ---------------------------------------------------------------------------
# Etapa 4: descartar negativas dudosas (solo reglas, sin modelo)
# ---------------------------------------------------------------------------
_VACIAS = set("""a al algo ante bajo cada como con contra cual cuales cuando de del desde donde e el ella ellas ellos
en entre era es esa ese eso esta este esto fue ha hay la las le les lo los mas me mi muy no o para pero por que se
sea segun ser si sin sobre su sus tambien te tiene un una uno unos unas y ya""".split())


def _contenido(texto: str) -> list[str]:
    return [t for t in re.findall(r"\w+", _normal(texto)) if t not in _VACIAS and (len(t) >= 3 or t.isdigit())]


def motivo_dudosa(f: dict, c: dict) -> str | None:
    """Por qué una negativa podría responder. Las reglas son conservadoras: ante la duda se descarta."""
    positivos = {x["texto"] for x in f["candidatos"] if x["correcto"]}
    if c["texto"] in positivos:
        return "igual_a_un_positivo"
    if not c["texto"].strip():
        return "vacia"
    if c["verificacion"] == "humano":
        return None  # el juicio humano manda
    for r in f["respuestas"]:
        palabras = _contenido(r)
        if not palabras:
            continue
        propias = set(_contenido(c["texto"]))
        cubiertas = sum(p in propias for p in palabras) / len(palabras)
        # Respuestas de 1 palabra (un número, un nombre): basta que aparezca. De 2 o más: el 80 % de sus palabras.
        if (len(palabras) == 1 and cubiertas == 1) or (len(palabras) >= 2 and cubiertas >= 0.8):
            return "contiene_la_respuesta_parcial"
    return None


def descartar_dudosas(_args) -> None:
    origen, destino = RAIZ / "3-puntuados", RAIZ / "4-filtrados"
    resumen = {"etapa": "4-descartar-dudosas", "archivos": {}}
    for ruta in sorted(origen.glob("*.jsonl")):
        motivos, filas = Counter(), []
        for f in _leer(ruta):
            quedan, vistos = [], set()
            for c in f["candidatos"]:
                m = None if c["correcto"] else motivo_dudosa(f, c)
                if m is None and not c["correcto"] and c["texto"] in vistos:
                    m = "negativa_repetida"  # el mismo pasaje dos veces en la lista (duplicados del corpus)
                vistos.add(c["texto"])
                if m:
                    motivos[m] += 1
                else:
                    quedan.append(c)
            f["candidatos"] = quedan
            if any(c["correcto"] for c in quedan) and any(not c["correcto"] for c in quedan):
                filas.append(f)
            else:
                motivos["pregunta_sin_competencia"] += 1
        resumen["archivos"][ruta.stem] = {"preguntas": len(filas), "descartes": dict(motivos),
                                          "sha256": _escribir(destino / ruta.name, filas)}
    _resumen(destino, resumen)


# ---------------------------------------------------------------------------
# Etapa 5: separar particiones (y elegir los grupos de entrenamiento)
# ---------------------------------------------------------------------------
PARTICIONES = {
    "entrenamiento": ["miracl-train", "sqac-train", "mlqa-dev", "mlqa-test"],
    "desarrollo": ["nomiracl-dev", "sqac-dev"],
    "prueba": ["nomiracl-test", "xquad-test", "sqac-test"],
}
PRUEBA_PRINCIPAL = "nomiracl-test"


def dificil(f: dict) -> bool:
    """bge no pone un correcto primero, o gana por menos de 1 logit a la mejor negativa."""
    mejor_pos = max(c["base"] for c in f["candidatos"] if c["correcto"])
    mejor_neg = max(c["base"] for c in f["candidatos"] if not c["correcto"])
    return mejor_pos - mejor_neg < 1.0


def grupo_entrenamiento(f: dict, negativas: int) -> dict | None:
    """1 positivo (el que bge puntúa peor: el más informativo) y ``negativas`` negativas, primero las que bge pone
    por encima del positivo y después las de mayor puntaje. Mismo esquema que lee ``afinar.py``."""
    pos = min((c for c in f["candidatos"] if c["correcto"]), key=lambda c: c["base"])
    negs = sorted((c for c in f["candidatos"] if not c["correcto"]), key=lambda c: -c["base"])
    if len(negs) < negativas:
        return None
    negs = negs[:negativas]
    return {"id": f["id"], "origen": f["fuente"], "fuente": f["fuente"], "query": f["query"], "pos": [pos["texto"]],
            "neg": [c["texto"] for c in negs], "neg_tipo": [c["tipo"] for c in negs],
            "verificacion": {"pos": pos["verificacion"], "neg": [c["verificacion"] for c in negs]},
            "hermanos": sum(c["tipo"] in ("hermana_contexto", "hermana_articulo", "juzgada") for c in negs),
            "base": {"rango": rango_mejor_positivo(f), "dificil": dificil(f),
                     "margen": round(pos["base"] - negs[0]["base"], 4)},
            "registro": "formal", "documento": f["documento"]}


def separar_particiones(args) -> None:
    origen, destino = RAIZ / "4-filtrados", RAIZ / "5-particiones"
    datos = {n: _leer(origen / f"{n}.jsonl") for ns in PARTICIONES.values() for n in ns
             if (origen / f"{n}.jsonl").exists()}
    faltan = [n for ns in PARTICIONES.values() for n in ns if n not in datos]
    if faltan:
        raise SystemExit(f"faltan conjuntos de la etapa 4: {faltan}")
    # Fugas: nada de desarrollo o prueba (pregunta normalizada, pasaje correcto o documento) entra al entrenamiento.
    evaluacion = [f for p in ("desarrollo", "prueba") for n in PARTICIONES[p] for f in datos[n]]
    preguntas_eval = {_normal(f["query"]) for f in evaluacion}
    positivos_eval = {c["texto"] for f in evaluacion for c in f["candidatos"] if c["correcto"]}
    documentos_eval = {f["documento"] for f in evaluacion if f["fuente"] != "miracl"}
    # NoMIRACL dev/test non_relevant: preguntas que tampoco deben aprenderse (v1, OBS-0012).
    for s in ("dev", "test"):
        preguntas_eval |= {_normal(x[1]) for x in _tsv(FUENTES_DIR / f"nomiracl-topics-{s}-nr.tsv")}
    fugas, grupos = Counter(), []
    for n in PARTICIONES["entrenamiento"]:
        for f in datos[n]:
            if _normal(f["query"]) in preguntas_eval:
                fugas["pregunta"] += 1
            elif any(c["correcto"] and c["texto"] in positivos_eval for c in f["candidatos"]):
                fugas["pasaje_correcto"] += 1
            elif f["documento"] in documentos_eval:
                fugas["documento"] += 1
            elif (g := grupo_entrenamiento(f, args.negativas)) is not None:
                grupos.append(g)
    # Cuota: todos los difíciles y fáciles hasta que los difíciles sean al menos ``--min-dificiles``.
    dificiles = [g for g in grupos if g["base"]["dificil"]]
    faciles = sorted((g for g in grupos if not g["base"]["dificil"]),
                     key=lambda g: hashlib.sha256(f"{SEMILLA}:{g['id']}".encode()).hexdigest())
    cupo = int(len(dificiles) * (1 - args.min_dificiles) / args.min_dificiles)
    entrenamiento = dificiles + faciles[:cupo]
    if args.max_grupos and len(entrenamiento) > args.max_grupos:
        raise SystemExit(f"{len(entrenamiento)} grupos superan --max-grupos; bajar --min-dificiles o subir el tope")
    # Muestra fija para las salidas por capa del experimento 2 (Astra): por hash del id, no por azar en vivo.
    for g in entrenamiento:
        g["muestra_capas"] = int(hashlib.sha256(f"capas:{g['id']}".encode()).hexdigest(), 16) % 100 < args.capas_pct
    entrenamiento.sort(key=lambda g: g["id"])
    resumen = {"etapa": "5-separar-particiones", "negativas": args.negativas, "min_dificiles": args.min_dificiles,
               "fugas_excluidas": dict(fugas), "archivos": {}}
    resumen["archivos"]["entrenamiento"] = {
        "grupos": len(entrenamiento), "dificiles": sum(g["base"]["dificil"] for g in entrenamiento),
        "por_fuente": dict(Counter(g["fuente"] for g in entrenamiento)),
        "muestra_capas": sum(g["muestra_capas"] for g in entrenamiento),
        "sha256": _escribir(destino / "entrenamiento.jsonl", entrenamiento)}
    for particion in ("desarrollo", "prueba"):
        for n in PARTICIONES[particion]:
            for f in datos[n]:
                f["particion"] = particion
            resumen["archivos"][n] = {"preguntas": len(datos[n]), "sha256": _escribir(destino / f"{n}.jsonl", datos[n])}
    _resumen(destino, resumen)


# ---------------------------------------------------------------------------
# Etapa 6: paráfrasis informales (las escriben subagentes; aquí solo se exportan y se validan)
# ---------------------------------------------------------------------------
def exportar_parafrasis(args) -> None:
    """Dos pedidos independientes, cada uno partido en 2 mitades (una por redactor):

    - ``--parte evaluacion``: ``--desarrollo`` preguntas de NoMIRACL dev y ``--prueba`` de NoMIRACL test, sorteadas
      por hash. Sale de la etapa 2, así que puede pedirse mientras corre la etapa 3;
    - ``--parte entrenamiento``: ``--entrenamiento`` grupos de la etapa 5, 60 % difíciles.

    Solo se exporta la pregunta: el redactor no ve pasajes ni respuestas, así no puede copiar la evidencia.
    """
    llave = lambda x: hashlib.sha256(f"parafrasis:{x['id']}".encode()).hexdigest()  # noqa: E731
    destino = RAIZ / "6-parafrasis"
    if args.parte == "evaluacion":
        origen = RAIZ / "2-candidatos"
        elegidos = [("desarrollo", f) for f in sorted(_leer(origen / "nomiracl-dev.jsonl"), key=llave)[:args.desarrollo]]
        elegidos += [("prueba", f) for f in sorted(_leer(origen / "nomiracl-test.jsonl"), key=llave)[:args.prueba]]
    else:
        grupos = sorted(_leer(RAIZ / "5-particiones" / "entrenamiento.jsonl"), key=llave)
        dif = [g for g in grupos if g["base"]["dificil"]]
        fac = [g for g in grupos if not g["base"]["dificil"]]
        n_dif = min(len(dif), int(args.entrenamiento * 0.6))
        elegidos = [("entrenamiento", g) for g in dif[:n_dif] + fac[:args.entrenamiento - n_dif]]
    filas = sorted(({"id": x["id"], "particion": p, "pregunta": x["query"]} for p, x in elegidos),
                   key=lambda f: f["id"])
    mitad = (len(filas) + 1) // 2
    for k, parte in enumerate((filas[:mitad], filas[mitad:]), 1):
        _escribir(destino / f"pedido-{args.parte}-{k}.jsonl", parte)
    _resumen(destino / args.parte, {"etapa": f"6a-exportar-parafrasis ({args.parte})", "preguntas": len(filas),
                                    "por_particion": dict(Counter(p for p, _ in elegidos)), "mitades": 2})


def validar_parafrasis(original: str, nueva: str, respuestas: list[str]) -> str | None:
    """Reglas: castellano, distinta del original, longitud razonable, sin la respuesta y conservando al menos una
    palabra de contenido o un número del original (que no cambie de tema)."""
    if not nueva or not nueva.strip():
        return "vacia"
    n, o = _normal(nueva), _normal(original)
    if n.rstrip("?¿ ") == o.rstrip("?¿ "):
        return "igual_al_original"
    palabras = len(n.split())
    if palabras < 2 or palabras > max(30, 2 * len(o.split())):
        return "longitud"
    if any(_normal(r) in n and _normal(r) not in o for r in respuestas if r):
        return "agrega_la_respuesta"
    if not set(_contenido(original)) & set(_contenido(nueva)):
        return "sin_palabras_del_original"
    if re.search(r"\b(the|what|which|how|where|when)\b", n):
        return "no_es_castellano"
    return None


VERSIONADAS = Path(__file__).parent  # parafrasis_<parte>.jsonl: lo que escribieron los redactores, versionado


def _restaurar_versionadas(carpeta: Path) -> None:
    """Si otra máquina ya redactó una parte, sus pedidos y respuestas viajan en ``parafrasis_<parte>.jsonl``."""
    for ruta in sorted(VERSIONADAS.glob("parafrasis_*.jsonl")):
        parte = ruta.stem.removeprefix("parafrasis_")
        filas = _leer(ruta)
        for k in (1, 2):
            mitad = [f for f in filas if f["mitad"] == k]
            if not (carpeta / f"respuesta-{parte}-{k}.jsonl").exists():
                _escribir(carpeta / f"pedido-{parte}-{k}.jsonl",
                          [{"id": f["id"], "particion": f["particion"], "pregunta": f["pregunta"]} for f in mitad])
                _escribir(carpeta / f"respuesta-{parte}-{k}.jsonl",
                          [{"id": f["id"], "informal": f["informal"], "redactor": f["redactor"]} for f in mitad])


def versionar_parafrasis(args) -> None:
    """Guarda pedidos y respuestas de una parte en ``laboratorio_reranker/parafrasis_<parte>.jsonl`` (texto propio:
    las preguntas originales vienen de NoMIRACL o del entrenamiento, y la reescritura es de los redactores)."""
    carpeta, filas = RAIZ / "6-parafrasis", []
    for k in (1, 2):
        pedidos = {f["id"]: f for f in _leer(carpeta / f"pedido-{args.parte}-{k}.jsonl")}
        for r in _leer(carpeta / f"respuesta-{args.parte}-{k}.jsonl"):
            if r["id"] in pedidos:
                filas.append({**pedidos[r["id"]], "informal": r["informal"], "redactor": r["redactor"], "mitad": k})
    sha = _escribir(VERSIONADAS / f"parafrasis_{args.parte}.jsonl", sorted(filas, key=lambda f: f["id"]))
    print(f"{len(filas)} paráfrasis -> parafrasis_{args.parte}.jsonl ({sha[:16]})")


def importar_parafrasis(_args) -> None:
    carpeta = RAIZ / "6-parafrasis"
    carpeta.mkdir(parents=True, exist_ok=True)
    _restaurar_versionadas(carpeta)
    pedidos = {f["id"]: f for ruta in sorted(carpeta.glob("pedido-*.jsonl")) for f in _leer(ruta)}
    respuestas = {}
    for ruta in sorted((RAIZ / "2-candidatos").glob("*.jsonl")):
        for f in _leer(ruta):
            respuestas[f["id"]] = f.get("respuestas", [])
    validas, motivos, vistas = [], Counter(), set()
    for pedido in sorted(carpeta.glob("pedido-*.jsonl")):
        ruta = pedido.with_name(pedido.name.replace("pedido-", "respuesta-"))
        if not ruta.exists():
            raise SystemExit(f"falta {ruta}")
        for f in _leer(ruta):
            if f["id"] not in pedidos or f["id"] in vistas:
                motivos["id_desconocido_o_repetido"] += 1
                continue
            vistas.add(f["id"])
            m = validar_parafrasis(pedidos[f["id"]]["pregunta"], f.get("informal", ""), respuestas.get(f["id"], []))
            if m:
                motivos[m] += 1
            else:
                validas.append({"id": f["id"], "particion": pedidos[f["id"]]["particion"],
                                "original": pedidos[f["id"]]["pregunta"], "informal": f["informal"].strip(),
                                "redactor": f.get("redactor", "")})
    motivos["sin_respuesta"] = len(set(pedidos) - vistas)
    sha = _escribir(carpeta / "validas.jsonl", sorted(validas, key=lambda f: f["id"]))
    _resumen(carpeta, {"etapa": "6b-importar-parafrasis", "pedidas": len(pedidos), "validas": len(validas),
                       "rechazos": dict(motivos), "por_particion": dict(Counter(v["particion"] for v in validas)),
                       "sha256": sha})


# ---------------------------------------------------------------------------
# Etapa 7: congelar
# ---------------------------------------------------------------------------
def _a_volcado(f: dict, particion: str, conjunto: str, query: str | None = None, sufijo: str = "",
               registro: str = "formal") -> dict:
    """Formato de ``ranking_pasajes.py --volcar-candidatos`` (lo leen ``diagnostico.py`` y ``puntuar_fuera.py``)."""
    return {"id": f["id"] + sufijo, "split": particion, "conjunto": conjunto, "fuente": f["fuente"],
            "registro": registro, "pregunta": query or f["query"],
            "pasajes": [{"texto": c["texto"], "correcto": c["correcto"], "correcto_hijo": c["correcto"],
                         "tipo": c["tipo"], "base": c["base"]} for c in f["candidatos"]]}


def _puntuar_informales(filas: list[dict]) -> None:
    """Reemplaza ``base`` por el puntaje del int8 del motor (lote 2) con la pregunta informal. Reanudable: guarda cada
    pregunta en ``6-parafrasis/base-informal.jsonl``."""
    cache_ruta = RAIZ / "6-parafrasis" / "base-informal.jsonl"
    cache = {f["id"]: f["base"] for f in _leer(cache_ruta)} if cache_ruta.exists() else {}
    faltan = [f for f in filas if f["id"] not in cache]
    if faltan:
        from comun import ScorerOnnx

        scorer, inicio = ScorerOnnx("int8"), time.time()
        with cache_ruta.open("ab") as salida:
            for k, f in enumerate(faltan, 1):
                puntajes = [round(float(x), 5) for x in scorer.puntuar(f["pregunta"], [p["texto"] for p in f["pasajes"]])]
                cache[f["id"]] = puntajes
                salida.write((json.dumps({"id": f["id"], "base": puntajes}) + "\n").encode("utf-8"))
                if k % 50 == 0:
                    print(f"[informales] {k}/{len(faltan)}  {(time.time() - inicio) / k:.2f} s/pregunta",
                          file=sys.stderr, flush=True)
    for f in filas:
        for p, s in zip(f["pasajes"], cache[f["id"]], strict=True):
            p["base"] = s


def congelar(_args) -> None:
    origen, destino = RAIZ / "5-particiones", RAIZ / "7-congelado"
    parafrasis = {}
    ruta_par = RAIZ / "6-parafrasis" / "validas.jsonl"
    if ruta_par.exists():
        parafrasis = {p["id"]: p["informal"] for p in _leer(ruta_par)}
    manifiesto = {"etapa": "7-congelar", "semilla": SEMILLA, "prueba_principal": PRUEBA_PRINCIPAL,
                  "regla_etiquetas": "juicio humano o tramo de respuesta; sin juez externo",
                  "fuentes": json.loads((FUENTES_DIR / "resumen.json").read_text(encoding="utf-8"))["licencias"],
                  "archivos": {}, "linea_base": {}}
    # Entrenamiento: grupos formales + una copia informal de los que tienen paráfrasis (mismos pasajes).
    grupos = _leer(origen / "entrenamiento.jsonl")
    # ``base`` de la copia informal describe la pregunta formal (solo ordenó las negativas al elegirlas).
    informales = [{**g, "id": g["id"] + "#informal", "query": parafrasis[g["id"]], "registro": "informal_redactada",
                   "base": {**g["base"], "medido_con": "pregunta formal"}} for g in grupos if g["id"] in parafrasis]
    entrenamiento = sorted(grupos + informales, key=lambda g: g["id"])
    manifiesto["archivos"]["entrenamiento.jsonl"] = {
        "grupos": len(entrenamiento), "informales": len(informales), "sha256": _escribir(
            destino / "entrenamiento.jsonl", entrenamiento)}
    # Desarrollo y prueba en formato de volcado; la variante informal va en un archivo aparte.
    for particion in ("desarrollo", "prueba"):
        for n in PARTICIONES[particion]:
            filas = _leer(origen / f"{n}.jsonl")
            volcado = [_a_volcado(f, particion, n) for f in filas]
            manifiesto["archivos"][f"{n}.jsonl"] = {"preguntas": len(volcado),
                                                   "sha256": _escribir(destino / f"{n}.jsonl", volcado)}
            manifiesto["linea_base"][n] = medir([r["pasajes"] for r in volcado], "base")
            inf = [_a_volcado(f, particion, f"{n}-informal", parafrasis[f["id"]], "#informal", "informal_redactada")
                   for f in filas if f["id"] in parafrasis]
            if inf:
                _puntuar_informales(inf)  # la línea base informal se mide con la pregunta informal, no la formal
                manifiesto["archivos"][f"{n}-informal.jsonl"] = {
                    "preguntas": len(inf), "sha256": _escribir(destino / f"{n}-informal.jsonl", inf)}
                manifiesto["linea_base"][f"{n}-informal"] = medir([r["pasajes"] for r in inf], "base")
                # La misma pregunta en registro formal, para comparar formal frente a informal sobre los mismos casos.
                ids = {r["id"].removesuffix("#informal") for r in inf}
                manifiesto["linea_base"][f"{n}-formal-pareada"] = medir(
                    [r["pasajes"] for r in volcado if r["id"] in ids], "base")
    (destino / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")
    print(json.dumps(manifiesto, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Evaluar: el mismo código antes y después, para los dos experimentos
# ---------------------------------------------------------------------------
def medir(listas: list[list[dict]], clave: str) -> dict:
    rangos = []
    for pasajes in listas:
        orden = sorted(range(len(pasajes)), key=lambda i: (-pasajes[i][clave], i))
        rangos.append(next(r for r, i in enumerate(orden, 1) if pasajes[i]["correcto"]))
    n = len(rangos)
    return {"n": n, **{f"hit@{k}": round(sum(r <= k for r in rangos) / n, 4) for k in (1, 3)},
            "mrr@10": round(sum(1 / r for r in rangos if r <= 10) / n, 4)} if n else {"n": 0}


def evaluar(args) -> None:
    """Puntúa con ``--modelo`` todos los archivos congelados (y el entrenamiento como listas pos+neg) y compara con la
    línea base guardada. La prueba se evalúa solo con ``--incluir-prueba``: se mide una vez, al final."""
    from comun import Ejecucion, crear_scorer
    from diagnostico import mcnemar_exacto

    carpeta = RAIZ / "7-congelado"
    manifiesto = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    for nombre, meta in manifiesto["archivos"].items():
        if _sha(carpeta / nombre) != meta["sha256"]:
            raise SystemExit(f"{nombre} cambió desde que se congeló: la evaluación no vale")
    scorer = crear_scorer(args.modelo, hilos=args.hilos)
    run = Ejecucion("v2-evaluar", {"modelo": args.modelo, "prueba": args.incluir_prueba}, args.hilos)
    resultado, casos = {}, []
    for nombre in manifiesto["archivos"]:
        if nombre == "entrenamiento.jsonl":
            if not args.incluir_entrenamiento:
                continue
            filas = [{"id": g["id"], "pregunta": g["query"], "split": "entrenamiento", "registro": g["registro"],
                      "fuente": g["fuente"], "pasajes": [{"texto": t, "correcto": True} for t in g["pos"]]
                      + [{"texto": t, "correcto": False} for t in g["neg"]]} for g in _leer(carpeta / nombre)]
            if args.solo_muestra_capas:
                filas = [f for f, g in zip(filas, _leer(carpeta / nombre), strict=True) if g.get("muestra_capas")]
        else:
            filas = _leer(carpeta / nombre)
            if filas and filas[0]["split"] == "prueba" and not args.incluir_prueba:
                continue
        for f in filas:
            puntajes = scorer.puntuar(f["pregunta"], [p["texto"] for p in f["pasajes"]])
            for p, s in zip(f["pasajes"], puntajes, strict=True):
                p["nuevo"] = float(s)
        tiene_base = all("base" in p for f in filas for p in f["pasajes"])
        r = {"modelo": medir([f["pasajes"] for f in filas], "nuevo")}
        if tiene_base:
            r["base"] = medir([f["pasajes"] for f in filas], "base")
            gan = per = 0
            for f in filas:
                a = medir([f["pasajes"]], "base")["hit@1"] == 1
                b = medir([f["pasajes"]], "nuevo")["hit@1"] == 1
                gan += b and not a
                per += a and not b
            r["hit@1_ganados"], r["hit@1_perdidos"] = gan, per
            r["mcnemar_p"] = round(mcnemar_exacto(gan, per), 4)
        resultado[nombre] = r
        casos += [{"archivo": nombre, "id": f["id"], "puntajes": [round(p["nuevo"], 5) for p in f["pasajes"]]}
                  for f in filas]
        print(nombre, json.dumps(r, ensure_ascii=False), file=sys.stderr, flush=True)
    run.guardar("casos.jsonl", casos)
    print(f"-> {run.cerrar(resultado)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="etapa", required=True)
    sub.add_parser("recolectar")
    p = sub.add_parser("armar-candidatos")
    p.add_argument("--solo", nargs="*")
    p.add_argument("--limite-sqac", type=int, default=6000, help="preguntas de SQAC train (CPU de la etapa 3)")
    p = sub.add_parser("puntuar-base")
    p.add_argument("--solo", nargs="*")
    p.add_argument("--gpu", choices=["fp32", "fp16"], default=None,
                   help="puntúa los conjuntos de entrenamiento en la GPU (fp16 en GPU de 4 GB)")
    p.add_argument("--hilos", type=int, default=None)
    sub.add_parser("probar-gpu")
    p = sub.add_parser("exportar-puntajes")
    p.add_argument("--solo", nargs="+", default=ENTRENAMIENTO)
    p = sub.add_parser("importar-puntajes")
    p.add_argument("--conservar-locales", action="store_true",
                   help="para los archivos con candidatos distintos, usar la puntuación completa hecha en esta máquina")
    sub.add_parser("descartar-dudosas")
    p = sub.add_parser("separar-particiones")
    p.add_argument("--negativas", type=int, default=7)
    p.add_argument("--min-dificiles", type=float, default=0.4)
    p.add_argument("--max-grupos", type=int, default=15000)
    p.add_argument("--capas-pct", type=int, default=10, help="%% del entrenamiento con salidas por capa (exp. 2)")
    p = sub.add_parser("exportar-parafrasis")
    p.add_argument("--parte", choices=["evaluacion", "entrenamiento"], required=True)
    p.add_argument("--entrenamiento", type=int, default=1000)
    p.add_argument("--desarrollo", type=int, default=200)
    p.add_argument("--prueba", type=int, default=500)
    sub.add_parser("importar-parafrasis")
    p = sub.add_parser("versionar-parafrasis")
    p.add_argument("--parte", choices=["evaluacion", "entrenamiento"], required=True)
    sub.add_parser("congelar")
    p = sub.add_parser("evaluar")
    p.add_argument("--modelo", required=True, help="onnx-int8 (base), onnx-fp32, torch-fp32 o local:<carpeta>")
    p.add_argument("--incluir-prueba", action="store_true", help="solo en la medición final, una vez")
    p.add_argument("--incluir-entrenamiento", action="store_true")
    p.add_argument("--solo-muestra-capas", action="store_true")
    p.add_argument("--hilos", type=int, default=None)
    args = parser.parse_args()
    {"probar-gpu": probar_gpu, "exportar-puntajes": exportar_puntajes, "importar-puntajes": importar_puntajes, "recolectar": recolectar, "armar-candidatos": armar_candidatos, "puntuar-base": puntuar_base,
     "descartar-dudosas": descartar_dudosas, "separar-particiones": separar_particiones,
     "exportar-parafrasis": exportar_parafrasis, "importar-parafrasis": importar_parafrasis,
     "versionar-parafrasis": versionar_parafrasis, "congelar": congelar, "evaluar": evaluar}[args.etapa](args)


if __name__ == "__main__":
    main()
