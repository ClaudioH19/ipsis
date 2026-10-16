"""Umbral del carril multimedia (plan multimedia, M2.2): ¿desde qué coseno conviene mostrar una ficha?

Crea un proyecto temporal con el corpus del banco de términos y las fichas del banco multimedia, lo indexa con el modelo real
y, por pregunta, registra el mejor candidato del carril (``BuscadorMedia.candidatos_agrupados``: ficha, capítulo y coseno
denso). Con eso calcula, por umbral:

* **ficha mostrada sin corresponder**: sobre las preguntas que no deben mostrar ficha (``mismo_tema`` y ``fuera``), cuántas
  recibirían una (con el límite superior de Wilson al 95 %: con pocas preguntas el punto engaña);
* **cobertura**: sobre las ``ficha``, cuántas muestran la ficha esperada; **ficha equivocada**, cuántas muestran otra;
* **capítulo correcto**, aparte: entre las que esperan un capítulo y muestran la ficha esperada.

Se informan dos umbrales, ambos elegidos mirando solo ``dev`` y con su resultado en ``test`` sin volver a elegir: el menor
que deja la tasa de fichas mostradas sin corresponder por debajo del objetivo (0,05 por defecto), que cae justo en el borde
de un puntaje y por eso suele fallar en ``test``; y el menor con **cero** fichas sin corresponder en ``dev`` (redondeado
hacia arriba a tres decimales), que es el recomendado. El carril no usa reranker y ``light`` y
``medium`` comparten el modelo denso, así que se mide una sola vez.

    python herramientas/evaluacion/carril_multimedia.py --salida /tmp/mm/carril --objetivo 0.05

El banco es sintético (``tests/datos/banco_multimedia/es/README.md``): las cifras son optimistas.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

BANCO = RAIZ / "tests" / "datos" / "banco_multimedia" / "es"
CORPUS = RAIZ / "tests" / "datos" / "banco_terminos" / "validacion" / "es" / "corpus"
NEGATIVOS = ("mismo_tema", "fuera")


def wilson_superior(errores: int, n: int, z: float = 1.96) -> float:
    """Límite superior del intervalo de Wilson para una proporción (1 si no hay datos)."""
    if n == 0:
        return 1.0
    p = errores / n
    centro = p + z * z / (2 * n)
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, (centro + margen) / (1 + z * z / n))


def _muestra(fila: dict, tau: float) -> bool:
    return fila["media_id_top"] is not None and fila["score_top"] is not None and fila["score_top"] >= tau


def evaluar(filas: list[dict], tau: float) -> dict:
    """Las métricas de un conjunto de filas con el umbral ``tau``."""
    negativas = [f for f in filas if f["tipo"] in NEGATIVOS]
    positivas = [f for f in filas if f["tipo"] == "ficha"]
    falsas = [f for f in negativas if _muestra(f, tau)]
    correctas = [f for f in positivas if _muestra(f, tau) and f["media_id_top"] == f["media_id"]]
    equivocadas = [f for f in positivas if _muestra(f, tau) and f["media_id_top"] != f["media_id"]]
    con_capitulo = [f for f in correctas if f["capitulo_segundos"] is not None]
    capitulo_ok = [f for f in con_capitulo if f["inicio_top"] == f["capitulo_segundos"]]
    return {
        "tau": round(tau, 4),
        "falsas": len(falsas), "negativas": len(negativas),
        "tasa_falsas": round(len(falsas) / len(negativas), 4) if negativas else None,
        "falsas_wilson_superior": round(wilson_superior(len(falsas), len(negativas)), 4),
        "falsas_mismo_tema": sum(f["tipo"] == "mismo_tema" for f in falsas),
        "falsas_fuera": sum(f["tipo"] == "fuera" for f in falsas),
        "cobertura": round(len(correctas) / len(positivas), 4) if positivas else None,
        "correctas": len(correctas), "positivas": len(positivas),
        "equivocadas": len(equivocadas),
        "capitulo_correcto": f"{len(capitulo_ok)}/{len(con_capitulo)}",
    }


def curva(filas: list[dict], umbrales: list[float]) -> list[dict]:
    return [evaluar(filas, tau) for tau in umbrales]


def candidatos_de_umbral(dev: list[dict]) -> list[float]:
    """Los cosenos observados en ``dev`` (cada uno puede ser un umbral distinto), de menor a mayor."""
    return sorted({f["score_top"] for f in dev if f["score_top"] is not None})


def recomendar(dev: list[dict], objetivo: float) -> float | None:
    """El menor umbral con tasa de fichas mostradas sin corresponder ≤ ``objetivo`` en ``dev`` (``None`` si ninguno)."""
    for tau in candidatos_de_umbral(dev):
        punto = evaluar(dev, tau)
        if punto["tasa_falsas"] is not None and punto["tasa_falsas"] <= objetivo:
            return tau
    return None


def sin_falsas(dev: list[dict]) -> float | None:
    """El menor umbral, redondeado hacia arriba a tres decimales, con cero fichas sin corresponder en ``dev``."""
    tau = recomendar(dev, 0.0)
    return None if tau is None else math.ceil(tau * 1000) / 1000


def _sin_duplicar_cercanos(valores: list[float], maximo: int = 30) -> list[float]:
    if len(valores) <= maximo:
        return valores
    return sorted({valores[round(i * (len(valores) - 1) / (maximo - 1))] for i in range(maximo)})


def _con_resultado(dev: list[dict], test: list[dict], todas: list[dict], tau: float | None) -> dict | None:
    if tau is None:
        return None
    return {"tau": round(tau, 4), "dev": evaluar(dev, tau), "test": evaluar(test, tau),
            "informales": evaluar([f for f in todas if f["informal"]], tau),
            "sin_informales": evaluar([f for f in todas if not f["informal"]], tau)}


def analizar(filas: list[dict], objetivo: float = 0.05) -> dict:
    dev = [f for f in filas if f["particion"] == "dev"]
    test = [f for f in filas if f["particion"] == "test"]
    return {"objetivo": objetivo, "preguntas": {"dev": len(dev), "test": len(test), "total": len(filas)},
            "por_objetivo": _con_resultado(dev, test, filas, recomendar(dev, objetivo)),
            "sin_falsas_en_dev": _con_resultado(dev, test, filas, sin_falsas(dev)),
            "curva_dev": curva(dev, _sin_duplicar_cercanos(candidatos_de_umbral(dev)))}


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:.1%}"


def _tabla(r: dict) -> list[str]:
    lineas = ["| Conjunto | Fichas sin corresponder | Wilson 95 % sup. | Cobertura | Ficha equivocada | Capítulo correcto |",
              "|---|---|---|---|---|---|"]
    for nombre, clave in (("dev", "dev"), ("test", "test"), ("informales", "informales"), ("sin informales", "sin_informales")):
        p = r[clave]
        lineas.append(f"| {nombre} | {p['falsas']}/{p['negativas']} ({_pct(p['tasa_falsas'])}; "
                      f"{p['falsas_mismo_tema']} mismo tema, {p['falsas_fuera']} fuera) | {p['falsas_wilson_superior']:.1%} | "
                      f"{p['correctas']}/{p['positivas']} ({_pct(p['cobertura'])}) | {p['equivocadas']} | {p['capitulo_correcto']} |")
    return lineas


def a_markdown(informe: dict, latencia: dict | None = None) -> str:
    lineas = ["# Umbral del carril multimedia", "",
              f"Objetivo: fichas mostradas sin corresponder ≤ {informe['objetivo']:.0%} ({informe['preguntas']['dev']} preguntas "
              f"en `dev`, {informe['preguntas']['test']} en `test`; coseno denso `intfloat/multilingual-e5-small`).", ""]
    if informe["sin_falsas_en_dev"] is None:
        lineas += ["**Ningún umbral deja cero fichas sin corresponder en `dev`: el carril debe quedar sin `min_score` "
                   "(no muestra nada).**", ""]
    else:
        r = informe["sin_falsas_en_dev"]
        lineas += [f"## Recomendado: `min_score` {r['tau']} (cero fichas sin corresponder en `dev`)", ""] + _tabla(r) + [""]
    if informe["por_objetivo"] is not None:
        r = informe["por_objetivo"]
        lineas += [f"## Menor umbral que cumple el objetivo en `dev`: {r['tau']}", ""] + _tabla(r) + [""]
    lineas += ["## Curva en `dev`", "", "| τ | Sin corresponder | Cobertura | Equivocada |", "|---|---|---|---|"]
    for p in informe["curva_dev"]:
        lineas.append(f"| {p['tau']} | {p['falsas']}/{p['negativas']} ({_pct(p['tasa_falsas'])}) | "
                      f"{p['correctas']}/{p['positivas']} ({_pct(p['cobertura'])}) | {p['equivocadas']} |")
    if latencia:
        lineas += ["", f"Latencia de la búsqueda del carril: p50 {latencia['p50_ms']} ms, p95 {latencia['p95_ms']} ms "
                       f"({latencia['n']} consultas, modelo ya cargado)."]
    return "\n".join(lineas) + "\n"


def _percentil(valores: list[float], q: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, math.ceil(q * len(ordenados)) - 1)]


def medir(banco: Path = BANCO, corpus: Path = CORPUS) -> tuple[list[dict], dict]:
    """Indexa el banco en un proyecto temporal y devuelve (filas, latencia). Necesita el modelo denso descargado."""
    import os
    import shutil

    from ipsis.cli import main as ipsis

    casos = [json.loads(linea) for linea in (banco / "casos.jsonl").read_text(encoding="utf-8").splitlines() if linea.strip()]
    anterior = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        proyecto = Path(tmp) / "proyecto"
        proyecto.mkdir()
        os.chdir(proyecto)
        try:
            for paso in (["init", "--profile", "light", "--language", "es"], ["load", str(corpus)]):
                if ipsis(paso) != 0:
                    raise SystemExit(f"ipsis {' '.join(paso)} falló")
            shutil.copytree(banco / "fichas", proyecto / "media")
            if ipsis(["index"]) != 0:
                raise SystemExit("ipsis index falló")
            from ipsis.aplicacion.consulta import construir_motor
            from ipsis.configuracion import rutas
            from ipsis.configuracion.archivos import escribir, leer
            from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto

            cfg = leer(rutas.MOTOR, "motor")
            cfg["media"] = {"activo": True, "puntaje_minimo": -1.0, "max_resultados": 5}
            escribir(rutas.MOTOR, cfg, "motor")
            motor = construir_motor(cargar_proyecto(), cfg_dominio=cargar_dominio())
            try:
                motor.calentar()
                buscador = motor.buscador_media
                if buscador is None:
                    raise SystemExit("el carril no tiene colección: ¿se indexaron las fichas?")
                buscador.candidatos_agrupados([casos[0]["pregunta"]])  # calienta el modelo
                filas, tiempos = [], []
                for caso in casos:
                    inicio = time.perf_counter()
                    candidatos = buscador.candidatos_agrupados([caso["pregunta"]])
                    tiempos.append((time.perf_counter() - inicio) * 1000)
                    top = candidatos[0] if candidatos else None
                    esperada = [c["media_id"] for c in candidatos].index(caso["media_id"]) + 1 \
                        if caso["tipo"] == "ficha" and any(c["media_id"] == caso["media_id"] for c in candidatos) else None
                    filas.append({**caso, "capitulo_segundos": caso.get("capitulo_segundos"),
                                  "media_id_top": top["media_id"] if top else None,
                                  "score_top": top["score"] if top else None,
                                  "inicio_top": top["start_seconds"] if top else None,
                                  "rango_ficha_esperada": esperada})
            finally:
                motor.cerrar()
        finally:
            os.chdir(anterior)
    latencia = {"n": len(tiempos), "p50_ms": round(statistics.median(tiempos), 1),
                "p95_ms": round(_percentil(tiempos, 0.95), 1)}
    return filas, latencia


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--banco", type=Path, default=BANCO, help="carpeta con fichas/ y casos.jsonl")
    p.add_argument("--corpus", type=Path, default=CORPUS, help="documentos del proyecto temporal")
    p.add_argument("--objetivo", type=float, default=0.05, help="tasa máxima de fichas mostradas sin corresponder en dev")
    p.add_argument("--salida", type=Path, help="prefijo de salida: escribe <salida>.json y <salida>.md")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    filas, latencia = medir(args.banco, args.corpus)
    informe = analizar(filas, args.objetivo)
    informe["latencia"] = latencia
    texto = a_markdown(informe, latencia)
    print(texto)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.with_suffix(".json").write_text(json.dumps({"informe": informe, "filas": filas}, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
        args.salida.with_suffix(".md").write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
