"""Forma de las páginas de resultados y separación de puntajes (plan de presentación, P0.2).

Responde: ¿existe una separación entre la primera y la segunda fuente con la que la primera casi nunca se equivoca? Esa
separación decide si el widget puede decir «Esto dice…» (forma ``clara``) sin parecer que se equivoca cuando la
fuente correcta era la segunda. Lee los volcados de ``ranking_pasajes.py --volcar-publicados`` (sin texto de pasajes ni de
preguntas: sirve para bancos privados) y usa las mismas definiciones que el motor (``ipsis/consulta/v2/forma.py``).

    python herramientas/evaluacion/ranking_pasajes.py <banco>/manifiesto.json --perfil light --perfil medium \\
        --particion todas --volcar-publicados /tmp/pub/publicados.jsonl --salida /tmp/pub/ranking
    python herramientas/evaluacion/forma_resultados.py /tmp/pub/publicados-light.jsonl /tmp/pub/publicados-medium.jsonl \\
        --salida /tmp/pub/forma --precision-objetivo 0.98

Por perfil, porque la escala del puntaje de ``light`` (recuperación, normalizado a la primera fuente) y la de ``medium``
(logit del reranker) no se comparan:

1. por relación entre las dos primeras fuentes (``documentos``, ``variantes``, ``otra``): preguntas, hit@1 y hit@3;
2. por umbral τ del margen (primera menos segunda): cobertura (qué fracción de las preguntas lo alcanza) y precisión del
   primer resultado entre ellas, con el límite inferior de Wilson al 95 % (con pocas preguntas el punto medio engaña);
3. la recomendación: el menor τ que cumple la precisión objetivo **en dev** y la cobertura mínima, con su resultado en
   **test**; si ninguno cumple, la forma ``clara`` queda desactivada. Los umbrales se eligen mirando solo ``dev``.

Es un análisis offline: no carga modelos ni toca ``.ipsis/``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from ipsis.consulta.v2.forma import forma_de_pagina, margen, relacion  # noqa: E402

PARTICIONES = ("dev", "test")
ERRORES_MINIMOS = 10  # con menos errores de primer resultado en dev, la curva no puede mostrar dónde falla el margen
RELACIONES = ("documentos", "variantes", "otra")


def wilson_inferior(aciertos: int, n: int, z: float = 1.96) -> float:
    """Límite inferior del intervalo de Wilson para una proporción (0 si no hay datos)."""
    if n == 0:
        return 0.0
    p = aciertos / n
    centro = p + z * z / (2 * n)
    margen_ = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centro - margen_) / (1 + z * z / n))


def leer_filas(rutas: list[str]) -> dict[str, list[dict]]:
    """Las filas de los volcados, agrupadas por perfil (el campo ``perfil`` de cada fila)."""
    perfiles: dict[str, list[dict]] = {}
    for ruta in rutas:
        for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
            if linea.strip():
                fila = json.loads(linea)
                perfiles.setdefault(fila["perfil"], []).append(fila)
    return perfiles


def _acierta(fila: dict, corte: int) -> bool:
    rango = fila.get("rango_final")
    return rango is not None and rango <= corte


def _fuentes(fila: dict) -> list[dict]:
    return fila["publicadas"]


def _resumen(filas: list[dict]) -> dict:
    n = len(filas)
    return {"n": n, "hit@1": round(sum(_acierta(f, 1) for f in filas) / n, 4) if n else None,
            "hit@3": round(sum(_acierta(f, 3) for f in filas) / n, 4) if n else None}


def por_relacion(filas: list[dict]) -> dict:
    """hit@1 y hit@3 según la relación entre las dos primeras fuentes; ``una_fuente`` si hay menos de dos."""
    grupos: dict[str, list[dict]] = {r: [] for r in RELACIONES}
    grupos["una_fuente"] = []
    for fila in filas:
        grupos[relacion(_fuentes(fila)) or "una_fuente"].append(fila)
    return {nombre: _resumen(grupo) for nombre, grupo in grupos.items()}


def curva(filas: list[dict], umbrales: list[float]) -> list[dict]:
    """Por umbral τ: cobertura (sobre las preguntas con margen) y precisión del primer resultado entre las que lo alcanzan."""
    con_margen = [(margen(_fuentes(f)), f) for f in filas]
    con_margen = [(m, f) for m, f in con_margen if m is not None]
    puntos = []
    for tau in umbrales:
        alcanzan = [f for m, f in con_margen if m >= tau]
        aciertos = sum(_acierta(f, 1) for f in alcanzan)
        puntos.append({"tau": tau, "n": len(alcanzan),
                       "cobertura": round(len(alcanzan) / len(con_margen), 4) if con_margen else 0.0,
                       "precision": round(aciertos / len(alcanzan), 4) if alcanzan else None,
                       "precision_wilson_inferior": round(wilson_inferior(aciertos, len(alcanzan)), 4)})
    return puntos


def recomendar(dev: list[dict], precision_objetivo: float, cobertura_minima: float) -> dict:
    """El menor τ (por margen observado en ``dev``) con precisión ≥ objetivo y cobertura ≥ mínima; ``None`` si ninguno."""
    margenes = sorted({m for m in (margen(_fuentes(f)) for f in dev) if m is not None})
    for punto in curva(dev, margenes):
        if punto["precision"] is not None and punto["precision"] >= precision_objetivo \
                and punto["cobertura"] >= cobertura_minima:
            return {"tau": punto["tau"], "dev": punto}
    return {"tau": None, "dev": None}


def _formas(filas: list[dict], tau: float | None) -> dict:
    cuenta = {"clara": 0, "variantes": 0, "documentos": 0, "neutral": 0}
    for fila in filas:
        cuenta[forma_de_pagina(_fuentes(fila), activo=True, margen_claro=tau)] += 1
    return cuenta


def _sin_duplicar_cercanos(margenes: list[float], maximo: int = 25) -> list[float]:
    """Hasta ``maximo`` umbrales repartidos por cuantiles, para que la tabla de la curva sea legible."""
    if len(margenes) <= maximo:
        return margenes
    pasos = [margenes[round(i * (len(margenes) - 1) / (maximo - 1))] for i in range(maximo)]
    return sorted(set(pasos))


def analizar_perfil(filas: list[dict], precision_objetivo: float = 0.98, cobertura_minima: float = 0.30) -> dict:
    """El análisis completo de un perfil (ver el docstring del módulo)."""
    dev = [f for f in filas if f.get("split") == "dev"]
    test = [f for f in filas if f.get("split") == "test"]
    recomendacion = recomendar(dev, precision_objetivo, cobertura_minima)
    tau = recomendacion["tau"]
    margenes_dev = sorted({m for m in (margen(_fuentes(f)) for f in dev) if m is not None})
    errores_dev = sum(not _acierta(f, 1) for f in dev)
    informe = {
        "advertencias": ([] if errores_dev >= ERRORES_MINIMOS else [
            f"Solo hay {errores_dev} errores de primer resultado en dev (se piden al menos {ERRORES_MINIMOS}): cualquier umbral "
            "«cumple» porque casi nada falla, así que esta recomendación no es evidencia de que el margen separe aciertos de "
            "errores. Usa un banco con errores reales (por ejemplo, documentos reales con preguntas adversarias)."]),
        "preguntas": {"dev": len(dev), "test": len(test), "total": len(filas)},
        "global": {"dev": _resumen(dev), "test": _resumen(test)},
        "por_relacion": {"dev": por_relacion(dev), "test": por_relacion(test)},
        "curva_dev": curva(dev, _sin_duplicar_cercanos(margenes_dev)),
        "objetivo": {"precision": precision_objetivo, "cobertura_minima": cobertura_minima},
        "recomendacion": {"tau": tau, "dev": recomendacion["dev"],
                          "test": curva(test, [tau])[0] if tau is not None and test else None},
        "formas": {"dev": _formas(dev, tau), "test": _formas(test, tau)},
    }
    return informe


def a_markdown(informe: dict) -> str:
    objetivo = next(iter(informe["perfiles"].values()))["objetivo"] if informe["perfiles"] else {}
    lineas = ["# Forma de los resultados y separación de puntajes", "",
              f"Objetivo: precisión del primer resultado ≥ {objetivo.get('precision')} con cobertura ≥ "
              f"{objetivo.get('cobertura_minima')}, elegido en `dev` e informado en `test`.", ""]
    for perfil, p in informe["perfiles"].items():
        n = p["preguntas"]
        lineas += [f"## Perfil `{perfil}`", "", f"Preguntas: {n['total']} (dev {n['dev']}, test {n['test']}). "
                   f"hit@1 dev {p['global']['dev']['hit@1']}, test {p['global']['test']['hit@1']}.", "",
                   "### Por relación entre las dos primeras fuentes", "",
                   "| Relación | dev n | dev hit@1 | dev hit@3 | test n | test hit@1 | test hit@3 |", "|---|---|---|---|---|---|---|"]
        for nombre in (*RELACIONES, "una_fuente"):
            d, t = p["por_relacion"]["dev"][nombre], p["por_relacion"]["test"][nombre]
            lineas.append(f"| {nombre} | {d['n']} | {d['hit@1']} | {d['hit@3']} | {t['n']} | {t['hit@1']} | {t['hit@3']} |")
        lineas += ["", "### Curva por margen τ (`dev`)", "", "| τ | preguntas | cobertura | precisión | Wilson inf. |",
                   "|---|---|---|---|---|"]
        for punto in p["curva_dev"]:
            lineas.append(f"| {punto['tau']:.4g} | {punto['n']} | {punto['cobertura']} | {punto['precision']} | "
                          f"{punto['precision_wilson_inferior']} |")
        r = p["recomendacion"]
        lineas += ["", "### Recomendación", ""]
        lineas += [f"> ⚠ {aviso}" for aviso in p["advertencias"]] + ([""] if p["advertencias"] else [])
        if r["tau"] is None:
            lineas.append("**Ningún τ cumple el objetivo en `dev`: la forma `clara` queda desactivada** "
                          "(`v2.presentation.clear_margin` sin definir).")
        else:
            d, t = r["dev"], r["test"]
            lineas.append(f"**τ = {r['tau']:.4g}** para `{perfil}`. En `dev`: cobertura {d['cobertura']}, precisión {d['precision']} "
                          f"(Wilson inf. {d['precision_wilson_inferior']}, n = {d['n']}).")
            if t:
                lineas.append(f"En `test`: cobertura {t['cobertura']}, precisión {t['precision']} "
                              f"(Wilson inf. {t['precision_wilson_inferior']}, n = {t['n']}).")
        lineas += ["", f"Formas resultantes con ese τ: dev {p['formas']['dev']}, test {p['formas']['test']}.", ""]
    return "\n".join(lineas)


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("publicados", nargs="+", help="JSONL de ranking_pasajes.py --volcar-publicados (uno por perfil)")
    p.add_argument("--precision-objetivo", type=float, default=0.98, help="precisión mínima del primer resultado")
    p.add_argument("--cobertura-minima", type=float, default=0.30,
                   help="fracción mínima de preguntas que debe alcanzar el umbral para que valga la pena")
    p.add_argument("--salida", required=True, help="carpeta de salida (fuera del repo)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    perfiles = leer_filas(args.publicados)
    informe = {"perfiles": {nombre: analizar_perfil(filas, args.precision_objetivo, args.cobertura_minima)
                            for nombre, filas in sorted(perfiles.items())}}
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "forma.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = a_markdown(informe)
    (salida / "forma.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
