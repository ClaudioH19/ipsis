"""Datos del laboratorio en el formato de ``ranking_pasajes.py --volcar-candidatos``.

Una fila por pregunta: ``{"id", "split", "pregunta", "pasajes": [{"doc_id", "texto", "correcto", ...}]}``. Así
el mismo código mide el volcado del motor (banco real o sintético) y los conjuntos públicos.

**NoMIRACL (es)** — Apache-2.0 en la ficha; textos de Wikipedia (CC BY-SA). Cada pregunta trae los pasajes que
hablantes nativos juzgaron relevantes (1) o no relevantes (0) entre los recuperados para ella: los 0 están
relacionados con la pregunta pero no la responden, justo la distinción que interesa.

    python laboratorio_reranker/datos.py nomiracl --split dev

**Banco sintético** (``banco_sintetico.yaml``, README § 5.2) — se materializa como un banco del formato de
``banco_pasajes`` (corpus Markdown, ``banco.jsonl``, ``manifiesto.json``) para pasarlo por el motor completo con
``ranking_pasajes.py --volcar-candidatos``:

    python laboratorio_reranker/datos.py sintetico
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from comun import REPO as REPO_RAIZ
from comun import SALIDA

NOMIRACL_ID, NOMIRACL_REV = "miracl/nomiracl", "ecd08778d0426a5ca28ac99763b0c9ddc2c78e68"


def _bajar(archivo: str) -> Path:
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(NOMIRACL_ID, f"data/spanish/{archivo}", repo_type="dataset",
                                revision=NOMIRACL_REV, cache_dir=str(SALIDA / "hf-datos")))


def _tsv(ruta: Path) -> list[list[str]]:
    return [linea.rstrip("\n").split("\t") for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]


def nomiracl(split: str = "dev", max_candidatos: int = 10, semilla: int = 0) -> list[dict]:
    """Preguntas del subconjunto ``relevant`` (al menos un pasaje que responde) con sus pasajes juzgados.

    El orden de los pasajes se baraja con una semilla derivada del id: no hay orden híbrido, y así el lote en que
    cae cada pasaje es arbitrario pero fijo. Si una pregunta tiene más de ``max_candidatos`` juicios se conservan
    todos sus relevantes y se completan con no relevantes.
    """
    corpus = {}
    with gzip.open(_bajar("corpus.jsonl.gz"), "rt", encoding="utf-8") as archivo:
        for linea in archivo:
            doc = json.loads(linea)
            corpus[doc["docid"]] = f"{doc['title']}\n{doc['text']}"
    preguntas = {fila[0]: fila[1] for fila in _tsv(_bajar(f"topics/{split}.relevant.tsv"))}
    juicios = defaultdict(dict)
    for qid, _, docid, rel in _tsv(_bajar(f"qrels/{split}.relevant.tsv")):
        if docid in corpus:
            juicios[qid][docid] = int(rel) > 0
    filas = []
    for qid, pregunta in sorted(preguntas.items()):
        docs = juicios.get(qid, {})
        positivos = sorted(d for d, ok in docs.items() if ok)
        negativos = sorted(d for d, ok in docs.items() if not ok)
        if not positivos or not negativos:
            continue  # sin competencia no hay orden que medir
        azar = random.Random(int(hashlib.sha256(f"{semilla}:{qid}".encode()).hexdigest()[:8], 16))
        elegidos = positivos[:max_candidatos - 1] + negativos[:max(1, max_candidatos - len(positivos))]
        azar.shuffle(elegidos)
        filas.append({"id": f"nomiracl-es-{qid}", "split": split, "pregunta": pregunta, "pasajes": [
            {"doc_id": d, "texto": corpus[d], "correcto": docs[d], "correcto_hijo": docs[d]} for d in elegidos]})
    return filas


FUENTE_SINTETICA = Path(__file__).with_name("banco_sintetico.yaml")


def _secciones(markdown: str, texto: str) -> dict[str, tuple[int, int]]:
    """Rango de cada sección (de su encabezado al siguiente) en el texto que produce el parser."""
    titulos = [linea.lstrip("#").strip() for linea in markdown.splitlines() if linea.startswith("#")]
    lineas, pos = [], 0
    for linea in texto.split("\n"):
        lineas.append((pos, linea.strip()))
        pos += len(linea) + 1
    inicios, k = [], 0
    for titulo in titulos:  # en orden: cada encabezado se busca después del anterior
        while k < len(lineas) and lineas[k][1] != titulo:
            k += 1
        if k == len(lineas):
            raise ValueError(f"encabezado no encontrado en el texto parseado: {titulo!r}")
        inicios.append(lineas[k][0])
        k += 1
    finales = inicios[1:] + [len(texto)]
    return dict(zip(titulos, zip(inicios, finales, strict=True), strict=True))


def sintetico(fuente: Path = FUENTE_SINTETICA, destino: Path = SALIDA / "banco-sintetico") -> Path:
    """Escribe corpus, ``banco.jsonl`` y ``manifiesto.json``; devuelve la ruta del manifiesto.

    Una pregunta formal (``…f``, categoría ``exacta``) y otra informal (``…i``, ``parafrasis``) por objetivo; la
    evidencia es la línea-oración que contiene ``respuesta`` dentro de su sección. Falla si la respuesta no está,
    o está más de una vez, en esa sección.
    """
    import yaml

    from ipsis.evaluacion.banco import ArchivoCorpus, CasoEvaluacion, CategoriaPregunta, EvidenciaEsperada
    from ipsis.evaluacion.golden import oracion_de
    from ipsis.ingesta.parsear import parsear_documento

    datos = yaml.safe_load(fuente.read_text(encoding="utf-8"))
    corpus = destino / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    archivos, textos, secciones, particion = [], {}, {}, {}
    for doc in datos["documentos"]:
        doc_id = Path(doc["archivo"]).stem.replace("_", "-")
        (corpus / doc["archivo"]).write_text(doc["texto"], encoding="utf-8")
        archivos.append(ArchivoCorpus(ruta=doc["archivo"], doc_id=doc_id))
        textos[doc["archivo"]] = parsear_documento(str(corpus / doc["archivo"]), doc_id=doc_id, doc_titulo=doc_id,
                                                   version="1").texto_completo
        secciones[doc["archivo"]] = _secciones(doc["texto"], textos[doc["archivo"]])
        particion[doc["archivo"]] = doc["particion"]
    casos = []
    for caso in datos["casos"]:
        texto = textos[caso["documento"]]
        ini_sec, fin_sec = secciones[caso["documento"]][caso["seccion"]]
        apariciones = texto.count(caso["respuesta"], ini_sec, fin_sec)
        if apariciones != 1:
            raise ValueError(f"{caso['objetivo']}: la respuesta aparece {apariciones} veces en su sección")
        inicio = texto.index(caso["respuesta"], ini_sec, fin_sec)
        ini, fin = oracion_de(texto, inicio, inicio + len(caso["respuesta"]))
        doc_id = Path(caso["documento"]).stem.replace("_", "-")
        for sufijo, registro, categoria in (("f", "formal", CategoriaPregunta.EXACTA),
                                            ("i", "informal", CategoriaPregunta.PARAFRASIS)):
            casos.append(CasoEvaluacion(
                # El esquema del banco solo admite dev/test: los documentos de entrenamiento van como «dev» y su
                # partición real queda en las notas (``grupos_volcado`` filtra por ella).
                dataset_version="0.1.0", id=f"{caso['objetivo']}{sufijo}",
                split=particion[caso["documento"]] if particion[caso["documento"]] in ("dev", "test") else "dev",
                categoria=categoria, pregunta=caso[registro], estado_esperado="respuesta_directa", respondible=True,
                respuesta_literal=caso["respuesta"],
                evidencias=[EvidenciaEsperada(doc_id=doc_id, offset_inicio=ini, offset_fin=fin, texto=texto[ini:fin])],
                notas=f"seccion: {caso['seccion']}; dificultad: {caso['dificultad']}; registro: {registro}; "
                      f"particion: {particion[caso['documento']]}"))
    return _escribir_banco(destino, archivos, casos, f"laboratorio_reranker_{fuente.stem}", "sintetico")


def _escribir_banco(destino: Path, archivos, casos, dataset_id: str, tipo: str) -> Path:
    from ipsis.evaluacion.banco import BancoEvaluacion, CorpusBanco, ManifiestoBanco, cargar_banco, hash_archivos_corpus

    manifiesto = ManifiestoBanco(
        dataset_id=dataset_id, dataset_version="0.1.0", tipo=tipo, estado="borrador", casos="banco.jsonl",
        corpus=CorpusBanco(directorio="corpus", archivos=archivos,
                           sha256=hash_archivos_corpus(destino / "corpus", archivos)),
        categorias_requeridas=sorted({c.categoria for c in casos}, key=lambda c: c.value), uso="evaluacion",
        idioma="es")
    banco = BancoEvaluacion(manifiesto=manifiesto, casos=casos)
    (destino / "manifiesto.json").write_text(banco.manifiesto.model_dump_json(indent=2, exclude_none=True) + "\n",
                                             encoding="utf-8")
    (destino / "banco.jsonl").write_text("".join(c.model_dump_json(exclude_none=True) + "\n" for c in casos),
                                         encoding="utf-8")
    cargar_banco(destino / "manifiesto.json")  # valida el hash del corpus y el esquema
    return destino / "manifiesto.json"


def real(documentos: Path, fuente: Path, destino: Path) -> Path:
    """Banco sobre documentos reales **privados**: todo queda en ``destino`` (dentro de ``.cache/``, ignorado por git).

    ``fuente`` (YAML, también fuera del repo) lista ``documentos`` (``archivo``, ``doc_id``) y ``casos`` con
    ``objetivo``, ``dificultad``, ``formal``, ``informal`` y una o más ``evidencias``: ``doc``, ``ancla`` (textos
    que se buscan en orden; la respuesta se busca después del último) y ``respuesta`` (literal). Varias evidencias
    cuando la misma respuesta está en más de un lugar (un artículo y un anexo, o dos versiones de un documento).
    """
    import shutil

    import yaml

    from ipsis.evaluacion.banco import ArchivoCorpus, CasoEvaluacion, CategoriaPregunta, EvidenciaEsperada
    from ipsis.evaluacion.golden import oracion_de
    from ipsis.ingesta.parsear import parsear_documento

    if REPO_RAIZ in destino.resolve().parents and ".cache" not in destino.resolve().parts:
        raise ValueError("los documentos reales solo se copian dentro de .cache/ (ignorada por git)")
    datos = yaml.safe_load(fuente.read_text(encoding="utf-8"))
    corpus = destino / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    from ipsis.ingesta.catalogo import _slug

    archivos, textos, ids = [], {}, {}
    for doc in datos["documentos"]:
        # ``ipsis load`` nombra cada documento con el slug de su archivo; el ``doc_id`` del YAML es solo un alias.
        ids[doc["doc_id"]] = _slug(Path(doc["archivo"]).stem)
        shutil.copy2(documentos / doc["archivo"], corpus / doc["archivo"])
        archivos.append(ArchivoCorpus(ruta=doc["archivo"], doc_id=ids[doc["doc_id"]]))
        textos[doc["doc_id"]] = parsear_documento(str(corpus / doc["archivo"]), doc_id=ids[doc["doc_id"]],
                                                  doc_titulo=doc["doc_id"], version="1").texto_completo
    casos = []
    for caso in datos["casos"]:
        evidencias = []
        for ev in caso["evidencias"]:
            texto, desde = textos[ev["doc"]], 0
            for ancla in ev.get("ancla") or []:
                pos = texto.find(ancla, desde)
                if pos < 0:
                    raise ValueError(f"{caso['objetivo']}: ancla no encontrada: {ancla!r}")
                desde = pos + len(ancla)
            inicio = texto.find(ev["respuesta"], desde)
            if inicio < 0:
                raise ValueError(f"{caso['objetivo']}: respuesta no encontrada tras sus anclas: {ev['respuesta']!r}")
            ini, fin = oracion_de(texto, inicio, inicio + len(ev["respuesta"]))
            evidencias.append(EvidenciaEsperada(doc_id=ids[ev["doc"]], offset_inicio=ini, offset_fin=fin,
                                                texto=texto[ini:fin]))
        for sufijo, registro, categoria in (("f", "formal", CategoriaPregunta.EXACTA),
                                            ("i", "informal", CategoriaPregunta.PARAFRASIS)):
            casos.append(CasoEvaluacion(
                dataset_version="0.1.0", id=f"{caso['objetivo']}{sufijo}", split="dev", categoria=categoria,
                pregunta=caso[registro], estado_esperado="respuesta_directa", respondible=True,
                respuesta_literal=caso["evidencias"][0]["respuesta"], evidencias=evidencias,
                notas=f"dificultad: {caso['dificultad']}; registro: {registro}"))
    return _escribir_banco(destino, archivos, casos, "laboratorio_reranker_real_es", "manual")


# ---------------------------------------------------------------------------
# Etapa 3: conjunto de afinado (grupos de 1 positivo y N negativos, formato FlagEmbedding)
# ---------------------------------------------------------------------------
PUBLICOS = SALIDA / "datos-publicos"
# Grupos del banco sintético de entrenamiento ya armados desde el volcado del motor (texto propio, sin licencias de
# terceros ni datos del cliente): permiten regenerar el conjunto en otra máquina sin ipsis ni modelos ONNX.
GRUPOS_SINTETICOS = Path(__file__).with_name("grupos_sinteticos.jsonl")
SQAC_REV = "f9928e8819596a601b8887cc5f8598b15d589a82"
MIRACL_ST_REV = "07e2b629250bf4185f4c87f640fac15949b8aa73"
_TILDES = str.maketrans("áéíóúÁÉÍÓÚüÜ", "aeiouAEIOUuU")
_ABREVIATURAS = [(r"\bque\b", "q"), (r"\bpara\b", "pa"), (r"\bporque\b", "xq"), (r"\bpor qué\b", "xq"),
                 (r"\bestá\b", "esta"), (r"\bcuánto\b", "cuanto"), (r"\bdónde\b", "donde"), (r"\bcuándo\b", "cuando")]


def informalizar(pregunta: str, azar: random.Random) -> str:
    """Registro de chat por reglas: minúsculas, sin «¿» ni tildes, abreviaturas comunes, a veces sin «?».

    Solo cubre lo ortográfico; las paráfrasis con brecha léxica las escribe Claude en el banco sintético.
    """
    import re

    texto = pregunta.lower()
    for patron, cambio in _ABREVIATURAS:
        if azar.random() < 0.7:
            texto = re.sub(patron, cambio, texto)
    texto = texto.translate(_TILDES).replace("¿", "").replace("¡", "")
    if azar.random() < 0.6:
        texto = texto.rstrip("?").rstrip()
    return texto


def _normal(texto: str) -> str:
    return " ".join(texto.lower().translate(_TILDES).split())


def _bajar_publico(url: str, nombre: str) -> Path:
    import urllib.request

    destino = PUBLICOS / nombre
    if not destino.exists():
        PUBLICOS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, destino)
    return destino


def grupos_sqac(split: str, n: int | None, negativos: int, semilla: int) -> list[dict]:
    """SQAC (CC BY-SA 4.0): cada contexto se parte en tramos de 2 oraciones con el título como primera línea.

    Positivo: el tramo que contiene el tramo de respuesta. Negativos: los otros tramos del mismo contexto (mismo
    tema, otro aspecto) y, para completar, los tramos de otros contextos más parecidos a la pregunta por TF-IDF.
    Ningún negativo contiene el texto de la respuesta.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    from ipsis.lenguaje.texto import dividir_oraciones

    ruta = _bajar_publico(f"https://huggingface.co/datasets/PlanTL-GOB-ES/SQAC/resolve/{SQAC_REV}/{split}.json",
                          f"sqac-{split}.json")
    articulos = json.loads(ruta.read_text(encoding="utf-8"))["data"]
    tramos, preguntas = [], []  # tramos: (contexto_id, inicio, fin, texto con título)
    for a, articulo in enumerate(articulos):
        # En AnCora el «título» es un nombre de archivo (CESS-CAST-…): no aporta contexto, es ruido.
        titulo = "" if articulo.get("source") == "ancora" else f"{articulo['title']}\n"
        for p, parrafo in enumerate(articulo["paragraphs"]):
            contexto = parrafo["context"]
            oraciones = dividir_oraciones(contexto)
            propios = []
            for k in range(0, len(oraciones), 2):
                ini, fin = oraciones[k][0], oraciones[min(k + 1, len(oraciones) - 1)][1]
                propios.append(len(tramos))
                tramos.append((f"{a}-{p}", ini, fin, f"{titulo}{contexto[ini:fin].strip()}"))
            for qa in parrafo["qas"]:
                respuesta = qa["answers"][0]
                preguntas.append({"id": qa["id"], "pregunta": qa["question"], "contexto": f"{a}-{p}",
                                  "inicio": respuesta["answer_start"],
                                  "fin": respuesta["answer_start"] + len(respuesta["text"]),
                                  "respuesta": respuesta["text"], "propios": propios})
    azar = random.Random(semilla)
    azar.shuffle(preguntas)
    vectorizador = TfidfVectorizer(sublinear_tf=True, min_df=2)
    matriz = vectorizador.fit_transform([t[3] for t in tramos])
    grupos = []
    for q in preguntas:
        if n and len(grupos) >= n:
            break
        positivos = [i for i in q["propios"] if tramos[i][1] <= q["inicio"] and q["fin"] <= tramos[i][2]]
        if not positivos:
            continue  # la respuesta cruza dos tramos
        respuesta = _normal(q["respuesta"])
        valido = lambda i: respuesta not in _normal(tramos[i][3])  # noqa: E731
        hermanos = [i for i in q["propios"] if i != positivos[0] and valido(i)]
        parecidos = (matriz @ vectorizador.transform([q["pregunta"]]).T).toarray().ravel().argsort()[::-1]
        externos = [int(i) for i in parecidos[:60] if tramos[int(i)][0] != q["contexto"] and valido(int(i))]
        negs = (hermanos[:negativos // 2 + 1] + externos)[:negativos]
        if len(negs) < negativos:
            continue
        grupos.append({"id": f"sqac-{q['id']}", "origen": "sqac", "query": q["pregunta"],
                       "pos": [tramos[positivos[0]][3]], "neg": [tramos[i][3] for i in negs],
                       "hermanos": min(len(hermanos), negativos // 2 + 1)})
    return grupos


def grupos_miracl(negativos: int, semilla: int, excluir: set[str]) -> list[dict]:
    """MIRACL es ``train`` (Apache-2.0) en la versión de sentence-transformers: una negativa difícil por pregunta,
    completada con positivos de otras preguntas (fáciles). ``excluir``: preguntas normalizadas que no deben entrar
    (las de NoMIRACL dev/test)."""
    import pyarrow.parquet as pq

    ruta = _bajar_publico("https://huggingface.co/datasets/sentence-transformers/miracl/resolve/"
                          f"{MIRACL_ST_REV}/es-triplet/train-00000-of-00001.parquet", "miracl-es-triplet.parquet")
    filas = pq.read_table(ruta).to_pylist()
    azar = random.Random(semilla)
    grupos = []
    for k, fila in enumerate(filas):
        if _normal(fila["anchor"]) in excluir:
            continue
        otros = [filas[j]["positive"] for j in azar.sample(range(len(filas)), negativos + 2) if j != k]
        grupos.append({"id": f"miracl-{k}", "origen": "miracl", "query": fila["anchor"], "pos": [fila["positive"]],
                       "neg": [fila["negative"], *otros][:negativos], "hermanos": 1})
    return grupos


def grupos_volcado(candidatos: Path, banco: Path, negativos: int, particion: str = "entrenamiento") -> list[dict]:
    """Grupos desde un volcado del motor (``ranking_pasajes.py --volcar-candidatos``): las vistas que ve bge.

    Positivo: un candidato correcto cuya vista contiene la evidencia. Negativos: candidatos en el orden híbrido que
    no contienen la evidencia (evita los errores de etiqueta de OBS-0009). Solo casos de la ``particion`` pedida.
    """
    from diagnostico import ubicar

    casos = {c["id"]: c for c in map(json.loads, banco.read_text(encoding="utf-8").splitlines())}
    grupos = []
    for linea in candidatos.read_text(encoding="utf-8").splitlines():
        fila = json.loads(linea)
        caso = casos.get(fila["id"])
        if caso is None or f"particion: {particion}" not in caso.get("notas", ""):
            continue
        evidencias = [e["texto"] for e in caso["evidencias"]]
        ve = [any(ubicar(p["texto"], e) for e in evidencias) for p in fila["pasajes"]]
        positivos = [p["texto"] for p, v in zip(fila["pasajes"], ve, strict=True) if p["correcto"] and v]
        negs = [p["texto"] for p, v in zip(fila["pasajes"], ve, strict=True) if not p["correcto"] and not v]
        if positivos and len(negs) >= 3:
            grupos.append({"id": fila["id"], "origen": "sintetico", "query": fila["pregunta"], "pos": positivos[:1],
                           "neg": negs[:negativos], "hermanos": len(negs[:negativos])})
    return grupos


def entrenamiento(args) -> Path:
    """Arma ``grupos-entrenamiento.jsonl`` y ``grupos-desarrollo.jsonl`` en ``.cache/laboratorio-reranker/afinado/``."""
    azar = random.Random(args.semilla)
    excluir = set()
    for split in ("dev", "test"):  # sin fuga hacia la prueba pública
        excluir |= {_normal(f[1]) for f in _tsv(_bajar(f"topics/{split}.relevant.tsv"))}
        excluir |= {_normal(f[1]) for f in _tsv(_bajar(f"topics/{split}.non_relevant.tsv"))}
    entrenar = grupos_sqac("train", args.sqac, args.negativos, args.semilla)
    entrenar += grupos_miracl(args.negativos, args.semilla, excluir)[:args.miracl]
    desarrollo = grupos_sqac("dev", args.sqac_dev, args.negativos, args.semilla)
    if args.volcado and args.banco:
        sinteticos = grupos_volcado(Path(args.volcado), Path(args.banco), args.negativos)
        GRUPOS_SINTETICOS.write_text("".join(json.dumps(g, ensure_ascii=False) + "\n" for g in sinteticos),
                                     encoding="utf-8")  # versionado: así otra máquina no necesita el motor
    else:
        sinteticos = [json.loads(l) for l in Path(args.sinteticos).read_text(encoding="utf-8").splitlines() if l]
    entrenar += [g for g in sinteticos for _ in range(args.repetir_sintetico)]  # sobre-muestreo del dominio
    # Registro informal: una fracción de las preguntas formales se reescribe por reglas (no las sintéticas, que ya
    # traen su par informal escrito a mano).
    for g in entrenar + desarrollo:
        g["registro"] = "formal"
        if g["origen"] != "sintetico" and azar.random() < args.informal:
            g["query"], g["registro"] = informalizar(g["query"], azar), "informal_reglas"
        elif g["origen"] == "sintetico":
            g["registro"] = "informal" if g["id"].endswith("i") else "formal"
    azar.shuffle(entrenar)
    destino = Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, grupos in (("entrenamiento", entrenar), ("desarrollo", desarrollo)):
        (destino / f"grupos-{nombre}.jsonl").write_text(
            "".join(json.dumps(g, ensure_ascii=False) + "\n" for g in grupos), encoding="utf-8")
    from collections import Counter

    sha = {n: hashlib.sha256((destino / f"grupos-{n}.jsonl").read_bytes()).hexdigest()
           for n in ("entrenamiento", "desarrollo")}
    resumen = {"sha256": sha, "entrenamiento": dict(Counter(g["origen"] for g in entrenar)),
               "desarrollo": dict(Counter(g["origen"] for g in desarrollo)),
               "registro": dict(Counter(g["registro"] for g in entrenar)), "negativos": args.negativos,
               "excluidas_por_nomiracl": len(excluir), "semilla": args.semilla}
    (destino / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="fuente", required=True)
    p = sub.add_parser("nomiracl")
    p.add_argument("--split", default="dev", choices=["dev", "test"])
    p.add_argument("--max-candidatos", type=int, default=10)
    p = sub.add_parser("sintetico")
    p.add_argument("--yaml", type=Path, default=FUENTE_SINTETICA, help="banco_sintetico.yaml o sintetico_entrenamiento.yaml")
    p.add_argument("--destino", type=Path, default=None, help="por defecto .cache/laboratorio-reranker/<nombre>")
    p = sub.add_parser("entrenamiento", help="etapa 3: grupos de afinado")
    p.add_argument("--sqac", type=int, default=1200)
    p.add_argument("--sqac-dev", type=int, default=200)
    p.add_argument("--miracl", type=int, default=400, help="400: se bajó de 800 por ruido (bitácora, OBS-0012)")
    p.add_argument("--volcado", help="volcado del motor sobre el banco sintético de entrenamiento (rearma "
                                     "grupos_sinteticos.jsonl); sin él se usan los grupos versionados")
    p.add_argument("--banco", help="banco.jsonl de ese banco (evidencias y partición)")
    p.add_argument("--sinteticos", default=str(GRUPOS_SINTETICOS))
    p.add_argument("--destino", default=str(SALIDA / "afinado"))
    p.add_argument("--repetir-sintetico", type=int, default=2)
    p.add_argument("--negativos", type=int, default=7)
    p.add_argument("--informal", type=float, default=0.3, help="fracción de preguntas públicas informalizadas")
    p.add_argument("--semilla", type=int, default=13)
    p = sub.add_parser("real", help="banco privado sobre documentos reales (todo en .cache/)")
    p.add_argument("documentos", type=Path, help="carpeta con los documentos (fuera del repo)")
    p.add_argument("--casos", type=Path, default=SALIDA / "banco-real" / "casos.yaml")
    p.add_argument("--destino", type=Path, default=SALIDA / "banco-real")
    args = parser.parse_args()
    if args.fuente == "sintetico":
        print(f"-> {sintetico(args.yaml, args.destino or SALIDA / args.yaml.stem.replace('_', '-'))}")
        return
    if args.fuente == "entrenamiento":
        print(f"-> {entrenamiento(args)}")
        return
    if args.fuente == "real":
        print(f"-> {real(args.documentos, args.casos, args.destino)}")
        return
    filas = nomiracl(args.split, args.max_candidatos)
    destino = SALIDA / "datos" / f"nomiracl-es-{args.split}.jsonl"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")
    pares = sum(len(f["pasajes"]) for f in filas)
    print(f"{len(filas)} preguntas, {pares} pares -> {destino}")


if __name__ == "__main__":
    main()
