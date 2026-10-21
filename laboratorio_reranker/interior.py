"""Etapa 2: ¿qué mueve la decisión del reranker y en qué capa se separa el pasaje correcto del competidor?

**Oclusión** (``oclusion``): para cada caso, el pasaje correcto mejor puntuado (c) y el competidor que gana (w).
Se quita una palabra de la pregunta, o una línea de un pasaje, y se mide el cambio en la diferencia
``s(q, c) − s(q, w)``. Una palabra con importancia positiva empuja hacia el correcto; una negativa, hacia el
competidor. Se usa el int8 del motor, con lote 1.

**Sondas por capa** (``sondas``): con PyTorch fp32 y los mismos ids del motor, se toma el vector ``<s>`` (el que lee
la cabeza de clasificación) de las 25 salidas (embeddings y 24 capas) para (q, c) y (q, w). En cada capa se ajusta
una regresión logística sobre ``h(q, c) − h(q, w)`` (y su opuesto, para equilibrar) con validación cruzada agrupada
por pregunta. La pregunta clave es el **rescate**: entre las preguntas en que bge se equivoca, qué fracción ordena
bien la sonda de cada capa (fuera de su pliegue de entrenamiento). Un rescate alto en capas medias que cae al final
indica que la información existe y las últimas capas la pierden.

    python laboratorio_reranker/interior.py oclusion <candidatos.jsonl> --puntajes <run>/casos.jsonl --casos real-004i,...
    python laboratorio_reranker/interior.py sondas real=<cand.jsonl>:<run>/casos.jsonl nomiracl=<...>:<...>

Las salidas van a ``.cache/laboratorio-reranker/<run_id>/``. Pueden contener texto de los documentos: no se versionan.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from comun import MAX_TOKENS_MOTOR, Ejecucion, cargar_candidatos, crear_scorer, es_informal, huella


def cargar_puntajes(ruta: str | Path, condicion: str = "onnx-int8@2") -> dict[str, list[float]]:
    """Logits por caso de una corrida de ``diagnostico.py`` (``cuantizacion`` o ``controles``)."""
    salida = {}
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        caso = json.loads(linea)
        if "variantes" in caso:
            salida[caso["id"]] = caso["variantes"]["base"]["logits"]
        elif "logits" in caso:
            salida[caso["id"]] = caso["logits"].get(condicion) or next(iter(caso["logits"].values()))
    return salida


def par_dificil(fila: dict, logits: list[float], max_candidatos: int = 10) -> tuple[int, int] | None:
    """Índices del correcto mejor puntuado y del incorrecto mejor puntuado."""
    pasajes = fila["pasajes"][:max_candidatos][:len(logits)]
    correctos = [k for k, p in enumerate(pasajes) if p["correcto"]]
    incorrectos = [k for k, p in enumerate(pasajes) if not p["correcto"]]
    if not correctos or not incorrectos:
        return None
    return max(correctos, key=logits.__getitem__), max(incorrectos, key=logits.__getitem__)


# ---------------------------------------------------------------------------
# Oclusión
# ---------------------------------------------------------------------------
def palabras(texto: str) -> list[str]:
    return re.findall(r"\S+", texto)


def oclusion(args) -> None:
    filas = {f["id"]: f for f in cargar_candidatos(args.candidatos)}
    puntajes = cargar_puntajes(args.puntajes)
    ids = args.casos.split(",") if args.casos else sorted(filas)
    ejecucion = Ejecucion("e2-oclusion", {"candidatos": huella(args.candidatos), "puntajes": huella(args.puntajes),
                                          "casos": ids}, args.hilos)
    scorer = crear_scorer("onnx-int8", MAX_TOKENS_MOTOR, args.hilos)

    def s(q, p):
        return scorer.puntuar(q, [p], lote=1)[0]

    resultados = []
    for caso_id in ids:
        fila = filas[caso_id]
        indices = par_dificil(fila, puntajes[caso_id], args.max_candidatos)
        if indices is None:
            continue
        c, w = (fila["pasajes"][k]["texto"] for k in indices)
        q = fila["pregunta"]
        base = s(q, c) - s(q, w)
        # Palabras de la pregunta: quitar una a la vez.
        terminos = palabras(q)
        en_pregunta = []
        for i, termino in enumerate(terminos):
            q2 = " ".join(terminos[:i] + terminos[i + 1:])
            en_pregunta.append({"palabra": termino, "importancia": round(base - (s(q2, c) - s(q2, w)), 3)})

        # Líneas de cada pasaje: quitar una a la vez (solo cambia el puntaje de ese pasaje).
        def lineas(pasaje, signo):
            partes = [l for l in pasaje.split("\n")]
            completo = s(q, pasaje)
            salida = []
            for i, linea in enumerate(partes):
                if not linea.strip():
                    continue
                sin = "\n".join(partes[:i] + partes[i + 1:])
                salida.append({"linea": i, "texto": linea[:160], "aporte": round(signo * (completo - s(q, sin)), 3)})
            return salida

        resultados.append({"id": caso_id, "informal": es_informal(caso_id), "diferencia_base": round(base, 3),
                           "pregunta": en_pregunta, "lineas_correcto": lineas(c, +1),
                           "lineas_competidor": lineas(w, -1)})
        mas = sorted(en_pregunta, key=lambda x: -x["importancia"])[:3]
        menos = sorted(en_pregunta, key=lambda x: x["importancia"])[:3]
        print(f"{caso_id}  c−w = {base:+.2f}\n   hacia el correcto: {[(x['palabra'], x['importancia']) for x in mas]}"
              f"\n   hacia el competidor: {[(x['palabra'], x['importancia']) for x in menos]}", flush=True)
    ejecucion.guardar("oclusion.jsonl", resultados)
    print(f"-> {ejecucion.cerrar({'casos': len(resultados)})}")


# ---------------------------------------------------------------------------
# Sondas por capa
# ---------------------------------------------------------------------------
def extraer(scorer_torch, pregunta: str, textos: list[str]):
    """``<s>`` de cada salida oculta para cada texto: arreglo (n_textos, n_capas, dim) en float32."""
    import numpy as np

    torch = scorer_torch.torch
    cod = scorer_torch.motor.codificar(pregunta, textos)
    ids = torch.tensor([x.ids for x in cod], dtype=torch.long)
    mascara = torch.tensor([x.attention_mask for x in cod], dtype=torch.long)
    with torch.inference_mode():
        salida = scorer_torch.modelo(input_ids=ids, attention_mask=mascara, output_hidden_states=True)
    capas = torch.stack([h[:, 0, :] for h in salida.hidden_states], dim=1)  # (n, capas, dim)
    return capas.float().numpy().astype(np.float32), [float(x) for x in salida.logits[:, 0]]


def sondas(args) -> None:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    fuentes = {}
    for definicion in args.fuentes:
        nombre, rutas = definicion.split("=", 1)
        candidatos, puntajes = rutas.rsplit(":", 1)  # la segunda ruta, relativa (sin «C:»)
        fuentes[nombre] = (candidatos, puntajes)
    ejecucion = Ejecucion("e2-sondas", {"fuentes": {n: [huella(c), huella(p)] for n, (c, p) in fuentes.items()},
                                        "limite": args.limite, "pliegues": args.pliegues}, args.hilos)
    base = crear_scorer("onnx-int8", MAX_TOKENS_MOTOR, args.hilos)
    torch_scorer = crear_scorer("torch-fp32", MAX_TOKENS_MOTOR, args.hilos, base=base)

    vectores, meta = [], []
    for nombre, (ruta_c, ruta_p) in fuentes.items():
        puntajes = cargar_puntajes(ruta_p)
        filas = [f for f in cargar_candidatos(ruta_c) if f["id"] in puntajes]
        if args.limite:
            filas = filas[:args.limite]
        for k, fila in enumerate(filas, 1):
            indices = par_dificil(fila, puntajes[fila["id"]])
            if indices is None:
                continue
            textos = [fila["pasajes"][i]["texto"] for i in indices]
            h, logits = extraer(torch_scorer, fila["pregunta"], textos)
            vectores.append(h[0] - h[1])  # (capas, dim)
            meta.append({"fuente": nombre, "id": fila["id"], "informal": es_informal(fila["id"]),
                         "bge_acierta": logits[0] > logits[1], "margen": round(logits[0] - logits[1], 4)})
            if k % 50 == 0:
                print(f"  {nombre}: {k}/{len(filas)}", flush=True)
    diferencias = np.stack(vectores)  # (n, capas, dim)
    np.save(ejecucion.carpeta / "diferencias.npy", diferencias.astype(np.float16))
    ejecucion.guardar("pares.jsonl", meta)

    n, n_capas, _ = diferencias.shape
    grupos = np.arange(n)
    pliegues = GroupKFold(n_splits=args.pliegues)
    curvas = []
    for capa in range(n_capas):
        x = diferencias[:, capa, :]
        acierto = np.zeros(n, dtype=bool)
        for entrenar, probar in pliegues.split(x, groups=grupos):
            # Cada par aparece con su opuesto para que la sonda no aprenda un sesgo de clase.
            xe = np.concatenate([x[entrenar], -x[entrenar]])
            ye = np.concatenate([np.ones(len(entrenar)), np.zeros(len(entrenar))])
            sonda = make_pipeline(StandardScaler(), LogisticRegression(C=args.c, max_iter=3000))
            sonda.fit(xe, ye)
            acierto[probar] = sonda.decision_function(x[probar]) > 0
        fila = {"capa": capa, "acierto": round(float(acierto.mean()), 4)}
        for etiqueta, filtro in (("bge_acierta", lambda m: m["bge_acierta"]),
                                 ("rescate", lambda m: not m["bge_acierta"])):
            sel = np.array([filtro(m) for m in meta])
            fila[etiqueta] = round(float(acierto[sel].mean()), 4) if sel.any() else None
        for nombre in fuentes:
            sel = np.array([m["fuente"] == nombre and not m["bge_acierta"] for m in meta])
            fila[f"rescate_{nombre}"] = round(float(acierto[sel].mean()), 4) if sel.any() else None
        if args.casos:
            fila["casos"] = {m["id"]: bool(a) for m, a in zip(meta, acierto, strict=True) if m["id"] in args.casos}
        curvas.append(fila)
        print(f"  capa {capa:2d}: acierto {fila['acierto']:.3f}  rescate {fila['rescate']}", flush=True)

    resumen = {"pares": n, "bge_errores": int(sum(not m["bge_acierta"] for m in meta)),
               "por_fuente": {f: sum(m["fuente"] == f for m in meta) for f in fuentes}, "curvas": curvas}
    print(f"-> {ejecucion.cerrar(resumen)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="medicion", required=True)
    p = sub.add_parser("oclusion")
    p.add_argument("candidatos")
    p.add_argument("--puntajes", required=True, help="casos.jsonl de una corrida de diagnostico.py")
    p.add_argument("--casos", help="ids separados por comas (por defecto, todos)")
    p.add_argument("--max-candidatos", type=int, default=10)
    p.add_argument("--hilos", type=int, default=None)
    p = sub.add_parser("sondas")
    p.add_argument("fuentes", nargs="+", help="nombre=candidatos.jsonl:casos.jsonl")
    p.add_argument("--limite", type=int, default=None, help="preguntas por fuente")
    p.add_argument("--pliegues", type=int, default=5)
    p.add_argument("--c", type=float, default=0.1, help="regularización de la regresión logística")
    p.add_argument("--casos", type=lambda s: set(s.split(",")), default=None,
                   help="ids cuyo acierto por capa se reporta uno por uno")
    p.add_argument("--hilos", type=int, default=None)
    args = parser.parse_args()
    {"oclusion": oclusion, "sondas": sondas}[args.medicion](args)


if __name__ == "__main__":
    main()
