"""Etapas 0–1: línea base y controles por caso. Hoy: C1, ¿la cuantización int8 cambia el orden?

C1 separa tres efectos con los mismos ids de token (los del tokenizador del motor, 256 tokens):

* **exportación**: PyTorch fp32 (``BAAI/bge-reranker-v2-m3``) frente a ONNX fp32;
* **cuantización**: ONNX fp32 frente a ONNX int8 (el archivo que usa el motor);
* **lote**: int8 con el lote del motor (2) frente a 1 y 10. La cuantización de onnx-community es dinámica: la
  escala de las activaciones se calcula sobre el lote entero, así que el puntaje de un pasaje podría depender de
  con quién comparte lote.

    python laboratorio_reranker/diagnostico.py cuantizacion .cache/laboratorio-reranker/datos/nomiracl-es-dev.jsonl
    python laboratorio_reranker/diagnostico.py cuantizacion candidatos_reales.jsonl --hilos 4

Entrada: uno o más volcados en el formato de ``ranking_pasajes.py --volcar-candidatos``. Salida en
``.cache/laboratorio-reranker/<run_id>/``: ``run.json`` (resumen) y ``casos.jsonl`` (logits por caso y condición).
"""
from __future__ import annotations

import argparse
import math
import statistics
import time
from itertools import combinations

from comun import (MAX_TOKENS_MOTOR, Ejecucion, cargar_candidatos, crear_scorer, es_informal, huella,
                   metricas, rango_de)

REFERENCIA = "torch-fp32@2"
COMPARACIONES = {  # nombre: (condición, contra qué se compara)
    "exportacion": ("onnx-fp32@2", "torch-fp32@2"),
    "cuantizacion": ("onnx-int8@2", "onnx-fp32@2"),
    "motor_vs_original": ("onnx-int8@2", "torch-fp32@2"),
    "lote_1": ("onnx-int8@1", "onnx-int8@2"),
    "lote_10": ("onnx-int8@10", "onnx-int8@2"),
}


# ---------------------------------------------------------------------------
# Núcleo puro
# ---------------------------------------------------------------------------
def kendall(a: list[float], b: list[float]) -> float:
    """Tau-a entre dos listas de puntajes del mismo conjunto de pasajes."""
    pares = list(combinations(range(len(a)), 2))
    if not pares:
        return 1.0
    s = sum(math.copysign(1, (a[i] - a[j]) * (b[i] - b[j])) if (a[i] - a[j]) * (b[i] - b[j]) else 0 for i, j in pares)
    return s / len(pares)


def mcnemar_exacto(ganados: int, perdidos: int) -> float:
    """p bilateral exacto sobre los discordantes (binomial con p = 0,5)."""
    n = ganados + perdidos
    if n == 0:
        return 1.0
    cola = sum(math.comb(n, k) for k in range(min(ganados, perdidos) + 1)) / 2 ** n
    return min(1.0, 2 * cola)


def percentil(valores: list[float], q: float) -> float:
    ordenados = sorted(valores)
    if not ordenados:
        return 0.0
    pos = (len(ordenados) - 1) * q
    abajo, arriba = int(pos), min(int(pos) + 1, len(ordenados) - 1)
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * (pos - abajo)


def comparar(casos: list[dict], cond: str, ref: str) -> dict:
    """Cuánto se aparta ``cond`` de ``ref``: orden, primer puesto, acierto y logits."""
    taus, deltas, top1_igual, invertidos, total_pares = [], [], 0, 0, 0
    ganados, perdidos, margenes = [], [], []
    for caso in casos:
        a, b = caso["logits"][cond], caso["logits"][ref]
        taus.append(kendall(a, b))
        deltas.extend(abs(x - y) for x, y in zip(a, b, strict=True))
        top1_igual += max(range(len(a)), key=a.__getitem__) == max(range(len(b)), key=b.__getitem__)
        for i, j in combinations(range(len(a)), 2):
            total_pares += 1
            invertidos += (a[i] - a[j]) * (b[i] - b[j]) < 0
        ok_a, ok_b = caso["rangos"][cond] == 1, caso["rangos"][ref] == 1
        if ok_a != ok_b:
            # margen en ``ref`` entre su primero y el segundo: ¿la diferencia era casi un empate?
            orden = sorted(b, reverse=True)
            margenes.append(round(orden[0] - orden[1], 4) if len(orden) > 1 else None)
            (ganados if ok_a else perdidos).append(caso["id"])
    return {
        "condicion": cond, "referencia": ref, "n": len(casos),
        "top1_igual": round(top1_igual / len(casos), 4) if casos else None,
        "kendall_media": round(statistics.fmean(taus), 4) if taus else None,
        "pares_invertidos": round(invertidos / total_pares, 4) if total_pares else None,
        "delta_logit": {"p50": round(percentil(deltas, 0.5), 4), "p95": round(percentil(deltas, 0.95), 4),
                        "max": round(max(deltas, default=0.0), 4)},
        "hit1_ganados": ganados, "hit1_perdidos": perdidos,
        "mcnemar_p": round(mcnemar_exacto(len(ganados), len(perdidos)), 4),
        "margen_ref_en_discordantes": margenes,
    }


def resumen_metricas(casos: list[dict], cond: str) -> dict:
    rangos = {c["id"]: c["rangos"][cond] for c in casos}
    formal = [r for i, r in rangos.items() if not es_informal(i)]
    informal = [r for i, r in rangos.items() if es_informal(i)]
    salida = {"todo": metricas(list(rangos.values()))}
    if informal:
        salida |= {"formal": metricas(formal), "informal": metricas(informal)}
    return salida


# ---------------------------------------------------------------------------
# C1
# ---------------------------------------------------------------------------
def cuantizacion(args) -> None:
    filas = [f for ruta in args.candidatos for f in cargar_candidatos(ruta, args.split, args.limite)]
    filas = [f for f in filas if any(p["correcto"] for p in f["pasajes"][:args.max_candidatos])]
    condiciones = [(c.split("@")[0], int(c.split("@")[1])) for c in args.condiciones.split(",")]
    ejecucion = Ejecucion("c1-cuantizacion", {
        "candidatos": {str(r): huella(r) for r in args.candidatos}, "split": args.split, "limite": args.limite,
        "max_candidatos": args.max_candidatos, "max_tokens": args.max_tokens,
        "condiciones": [f"{n}@{lote}" for n, lote in condiciones]}, args.hilos)

    scorers = {"onnx-int8": crear_scorer("onnx-int8", args.max_tokens, args.hilos)}  # también tokeniza
    for nombre in dict.fromkeys(n for n, _ in condiciones):
        if nombre not in scorers:
            scorers[nombre] = crear_scorer(nombre, args.max_tokens, args.hilos, base=scorers["onnx-int8"])
    for s in scorers.values():  # calentamiento fuera de la medición
        s.puntuar("calentamiento", ["calentamiento del modelo"], lote=1)

    casos, tiempos = [], {f"{n}@{lote}": 0.0 for n, lote in condiciones}
    for k, fila in enumerate(filas, start=1):
        pasajes = fila["pasajes"][:args.max_candidatos]
        textos, correctos = [p["texto"] for p in pasajes], [bool(p["correcto"]) for p in pasajes]
        caso = {"id": fila["id"], "split": fila.get("split"), "n_pasajes": len(pasajes), "correctos": correctos,
                "tokens": [scorers["onnx-int8"].tokens(fila["pregunta"], t) for t in textos],
                "logits": {}, "rangos": {}}
        for nombre, lote in condiciones:
            clave = f"{nombre}@{lote}"
            inicio = time.perf_counter()
            logits = scorers[nombre].puntuar(fila["pregunta"], textos, lote=lote)
            tiempos[clave] += time.perf_counter() - inicio
            caso["logits"][clave] = [round(x, 5) for x in logits]
            caso["rangos"][clave] = rango_de(logits, correctos)
        casos.append(caso)
        if k % 25 == 0 or k == len(filas):
            print(f"  {k}/{len(filas)}", flush=True)

    pares = sum(c["n_pasajes"] for c in casos)
    truncados = sum(t["truncado"] for c in casos for t in c["tokens"])
    resumen = {
        "preguntas": len(casos), "pares": pares, "pares_truncados": truncados,
        "metricas": {clave: resumen_metricas(casos, clave) for clave in tiempos},
        "comparaciones": {n: comparar(casos, c, r) for n, (c, r) in COMPARACIONES.items()
                          if c in tiempos and r in tiempos},
        "ms_por_par": {clave: round(1000 * t / pares, 1) for clave, t in tiempos.items()},
    }
    ejecucion.guardar("casos.jsonl", casos)
    ruta = ejecucion.cerrar(resumen)
    imprimir(resumen, ruta)


# ---------------------------------------------------------------------------
# C2–C5 sobre los errores de orden
# ---------------------------------------------------------------------------
def _norm(texto: str) -> str:
    return " ".join(texto.split())


def ubicar(texto: str, fragmento: str) -> tuple[int, int] | None:
    """Rango de ``fragmento`` en ``texto`` sin distinguir espacios ni saltos de línea."""
    plano, mapa = [], []
    for i, ch in enumerate(texto):
        if ch.isspace():
            if plano and plano[-1] != " ":
                plano.append(" ")
                mapa.append(i)
        else:
            plano.append(ch)
            mapa.append(i)
    pos = "".join(plano).find(_norm(fragmento))
    if pos < 0:
        return None
    return mapa[pos], mapa[pos + len(_norm(fragmento)) - 1] + 1


def raiz_comun(textos: list[str]) -> str | None:
    """Primera línea repetida en todos los candidatos (p. ej. el primer título del documento tomado como raíz)."""
    primeras = {t.split("\n", 1)[0] for t in textos}
    return primeras.pop() if len(primeras) == 1 and len(textos) > 1 else None


def variantes(caso: dict, pregunta_par: str | None, evidencias: list[str]):
    """``(nombre, pregunta, textos, max_tokens)`` por control; cada una cambia una sola variable respecto de la base.

    C3 es asimétrica a propósito: solo el pasaje correcto se reduce a la oración que responde (oráculo).
    C4 quita a **todos** los candidatos la raíz repetida o la línea de rasgos distintivos.
    """
    pregunta, textos, correctos = caso["pregunta"], caso["textos"], caso["correctos"]
    yield "base", pregunta, textos, MAX_TOKENS_MOTOR
    yield "C2_512", pregunta, textos, 512
    yield "C2_2048", pregunta, textos, 2048
    oraculo, cambiados = list(textos), 0
    for k, (texto, ok) in enumerate(zip(textos, correctos, strict=True)):
        if ok:
            frases = [texto[r[0]:r[1]] for e in evidencias if (r := ubicar(texto, e))]
            if frases:
                oraculo[k], cambiados = " ".join(frases), cambiados + 1
    if cambiados:
        yield "C3_oraculo", pregunta, oraculo, MAX_TOKENS_MOTOR
    if raiz := raiz_comun(textos):
        yield "C4_sin_raiz", pregunta, [t.split("\n", 1)[1] if "\n" in t else t for t in textos], MAX_TOKENS_MOTOR
    if any("Se distingue por:" in t for t in textos):
        yield "C4_sin_rasgos", pregunta, ["\n".join(l for l in t.split("\n") if not l.strip().startswith(
            "Se distingue por:")) for t in textos], MAX_TOKENS_MOTOR
    if pregunta_par:
        yield "C5_registro", pregunta_par, textos, MAX_TOKENS_MOTOR


ORDEN_CAUSAS = [("C2_512", "B"), ("C2_2048", "B"), ("C3_oraculo", "B"), ("C4_sin_raiz", "C"),
                ("C4_sin_rasgos", "C"), ("C5_registro", "D")]


def controles(args) -> None:
    import json
    from pathlib import Path

    filas = [f for f in cargar_candidatos(args.candidatos) if any(p["correcto"] for p in f["pasajes"][:args.max_candidatos])]
    banco = {c["id"]: c for c in map(json.loads, Path(args.banco).read_text(encoding="utf-8").splitlines())}
    preguntas = {i: c["pregunta"] for i, c in banco.items()}
    ejecucion = Ejecucion("c2c5-controles", {"candidatos": huella(args.candidatos), "banco": huella(args.banco),
                                             "scorer": args.scorer, "max_candidatos": args.max_candidatos,
                                             "controles_correctos": args.controles_correctos}, args.hilos)
    scorer = crear_scorer(args.scorer, MAX_TOKENS_MOTOR, args.hilos)
    scorer.puntuar("calentamiento", ["calentamiento del modelo"], lote=1)

    def medir(pregunta, textos, correctos, max_tokens):
        scorer.ventana(max_tokens)
        logits = scorer.puntuar(pregunta, textos, lote=1)
        mejor_ok = max(l for l, ok in zip(logits, correctos, strict=True) if ok)
        mejor_mal = max((l for l, ok in zip(logits, correctos, strict=True) if not ok), default=float("-inf"))
        return {"rango": rango_de(logits, correctos), "margen": round(mejor_mal - mejor_ok, 4),
                "logits": [round(x, 4) for x in logits]}

    # Base para todos; los controles, para los errores y para los primeros N aciertos (grupo de control).
    casos, aciertos = [], 0
    for fila in filas:
        pasajes = fila["pasajes"][:args.max_candidatos]
        caso = {"id": fila["id"], "pregunta": fila["pregunta"], "textos": [p["texto"] for p in pasajes],
                "correctos": [bool(p["correcto"]) for p in pasajes]}
        base = medir(caso["pregunta"], caso["textos"], caso["correctos"], MAX_TOKENS_MOTOR)
        if base["rango"] == 1:
            aciertos += 1
            if aciertos > args.controles_correctos:
                casos.append({"id": caso["id"], "grupo": "acierto_sin_controles", "variantes": {"base": base}})
                continue
        par = fila["id"][:-1] + ("i" if fila["id"].endswith("f") else "f")
        evidencias = [e["texto"] for e in banco.get(fila["id"], {}).get("evidencias", [])]
        registro = {"id": caso["id"], "grupo": "error" if base["rango"] != 1 else "control", "variantes": {}}
        # ¿La evidencia queda fuera de la ventana de 256 en algún pasaje correcto?
        registro["evidencia_fuera_de_ventana"] = any(
            (r := ubicar(t, e)) and scorer.tokens(caso["pregunta"], t[:r[1]])["tokens_sin_limite"] > MAX_TOKENS_MOTOR
            for t, ok in zip(caso["textos"], caso["correctos"], strict=True) if ok for e in evidencias)
        for nombre, pregunta, textos, max_tokens in variantes(caso, preguntas.get(par), evidencias):
            registro["variantes"][nombre] = base if nombre == "base" else medir(pregunta, textos, caso["correctos"],
                                                                                max_tokens)
        arregla = [n for n, _ in ORDEN_CAUSAS if registro["variantes"].get(n, {}).get("rango") == 1]
        registro["arreglan"] = arregla
        registro["causa"] = (next(c for n, c in ORDEN_CAUSAS if n in arregla) if arregla else "E") \
            if registro["grupo"] == "error" else None
        registro["rompen"] = [n for n, v in registro["variantes"].items() if v["rango"] != 1] \
            if registro["grupo"] == "control" else None
        casos.append(registro)
        print(f"  {caso['id']}: base {base['rango']} -> " + ", ".join(
            f"{n} {v['rango']}" for n, v in registro["variantes"].items() if n != "base"), flush=True)

    errores = [c for c in casos if c["grupo"] == "error"]
    resumen = {
        "preguntas": len(casos), "errores": len(errores),
        "hit1_base": round(sum(c["variantes"]["base"]["rango"] == 1 for c in casos) / len(casos), 4),
        "causas": {k: sorted(c["id"] for c in errores if c["causa"] == k) for k in "BCDE"},
        "arreglan_por_control": {n: sum(n in c["arreglan"] for c in errores) for n, _ in ORDEN_CAUSAS},
        "rompen_en_controles": {n: sum(n in (c["rompen"] or []) for c in casos if c["grupo"] == "control")
                                for n, _ in ORDEN_CAUSAS},
        "controles_correctos": sum(c["grupo"] == "control" for c in casos),
    }
    ejecucion.guardar("casos.jsonl", casos)
    ruta = ejecucion.cerrar(resumen)
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    print(f"-> {ruta}")


def imprimir(resumen: dict, ruta) -> None:
    print(f"\n{resumen['preguntas']} preguntas, {resumen['pares']} pares ({resumen['pares_truncados']} truncados)\n")
    print("| Condición | hit@1 | hit@3 | MRR | ms/par |\n|---|---|---|---|---|")
    for clave, m in resumen["metricas"].items():
        t = m["todo"]
        print(f"| {clave} | {t['hit@1']} | {t['hit@3']} | {t['mrr']} | {resumen['ms_por_par'][clave]} |")
    print("\n| Comparación | top-1 igual | Kendall | pares invertidos | dlogit p50/p95/max | hit@1 +/− | p |")
    print("|---|---|---|---|---|---|---|")
    for nombre, c in resumen["comparaciones"].items():
        d = c["delta_logit"]
        print(f"| {nombre} | {c['top1_igual']} | {c['kendall_media']} | {c['pares_invertidos']} | "
              f"{d['p50']}/{d['p95']}/{d['max']} | {len(c['hit1_ganados'])}/{len(c['hit1_perdidos'])} | "
              f"{c['mcnemar_p']} |")
    print(f"\n-> {ruta}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="control", required=True)
    p = sub.add_parser("cuantizacion", help="C1: exportación, cuantización y lote")
    p.add_argument("candidatos", nargs="+")
    p.add_argument("--split", default=None, help="solo esta partición del volcado")
    p.add_argument("--limite", type=int, default=None, help="primeras N preguntas de cada volcado")
    p.add_argument("--max-candidatos", type=int, default=10, help="los que puntúa el motor en español")
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS_MOTOR)
    p.add_argument("--condiciones", default="onnx-int8@2,onnx-int8@1,onnx-int8@10,onnx-fp32@2,torch-fp32@2",
                   help="scorer@lote separados por comas; el lote del motor es 2")
    p.add_argument("--hilos", type=int, default=None)
    p = sub.add_parser("controles", help="C2–C5 sobre los errores de orden (una variable por vez)")
    p.add_argument("candidatos")
    p.add_argument("--banco", required=True, help="banco.jsonl con las evidencias y las preguntas pareadas f/i")
    p.add_argument("--scorer", default="onnx-int8", help="onnx-int8 (pesos del motor) u onnx-fp32; siempre lote 1")
    p.add_argument("--max-candidatos", type=int, default=10)
    p.add_argument("--controles-correctos", type=int, default=12,
                   help="cuántos aciertos reciben los mismos controles (¿el control rompe lo que estaba bien?)")
    p.add_argument("--hilos", type=int, default=None)
    args = parser.parse_args()
    {"cuantizacion": cuantizacion, "controles": controles}[args.control](args)


if __name__ == "__main__":
    main()
