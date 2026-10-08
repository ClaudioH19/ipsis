"""Mide el banco de alternativas (ADR 0008) y calibra pesos y umbral.

    python tests/datos/banco_alternativas/medir.py <salida.json> [light,medium] [es,en,pt] [casos|validacion]
    python tests/datos/banco_alternativas/medir.py --resumir <salida.json> [umbral] [pesos.json]
    python tests/datos/banco_alternativas/medir.py --calibrar <salida.json> [<salida2.json>…]

Cada idioma se indexa en un proyecto temporal con el corpus del banco de
consultas, el catálogo y el inventario de ``<idioma>/corpus`` y el
``config/domain.yaml`` de ``<idioma>/dominio.yaml``. Por caso guarda el
estado, la regla, lo que se ofreció y **todos** los párrafos elegibles con
sus señales: ``--resumir`` y ``--calibrar`` re-deciden con otros pesos y
umbral sin volver a correr el motor (la misma regla de
``ipsis.consulta.alternativas``).

Métricas (``resumir``):

- **fuera_dominio_con_alternativas:** casos fuera de dominio con alguna
  alternativa (meta dura: 0);
- **precision:** alternativas ofrecidas que contienen un texto de
  «aceptables» de su caso; en ``sin_vecino`` y ``fuera_dominio`` toda
  alternativa es errónea (meta dura: ≥ 0,9);
- **cobertura:** casos ``vecino`` con al menos una alternativa correcta,
  sobre los ``vecino`` que terminaron en ``sin_respuesta``;
- **vecino_visible:** casos ``vecino`` donde la persona ve algo aceptable,
  por una alternativa o por los pasajes de una respuesta ``relacionado``.
"""
from __future__ import annotations

import contextlib
import io
import itertools
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent
CONSULTAS = RAIZ.parent / "banco_consultas"
IDIOMAS = ("es", "en", "pt")
SENALES = ("familia", "medida", "terminos", "seccion", "keywords", "categoria", "similitud")


def cargar(idioma: str, archivo: str = "casos") -> list[dict]:
    """``casos`` (dev y test) o ``validacion`` (apartada: se mide una vez con la regla congelada)."""
    return yaml.safe_load((RAIZ / idioma / f"{archivo}.yaml").read_text(encoding="utf-8"))


def medir_idioma(idioma: str, perfil: str, archivo: str = "casos") -> dict:
    from ipsis.aplicacion.consulta import construir_motor_del_proyecto
    from ipsis.cli import main
    from ipsis.lenguaje.entidades import configurar_idioma, configurar_perfil, idioma_activo, perfil_activo

    previo = (idioma_activo(), perfil_activo())
    anterior = Path.cwd()
    casos = []
    with tempfile.TemporaryDirectory(prefix=f"alternativas_{idioma}_{perfil}_", ignore_cleanup_errors=True) as tmp:
        try:
            os.chdir(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(["init", "--profile", perfil, "--language", idioma]) == 0
                shutil.copyfile(RAIZ / idioma / "dominio.yaml", Path("config") / "domain.yaml")
                assert main(["load", str(CONSULTAS / idioma / "corpus")]) == 0
                assert main(["load", str(RAIZ / idioma / "corpus")]) == 0
                assert main(["index"]) == 0
            motor = construir_motor_del_proyecto()
            motor.calentar()
            # Se registra todo lo elegible: la decisión se rehace fuera con otros pesos y umbral.
            motor.registrar_alternativas = True
            motor.alternativas.umbral = 0.0
            motor.alternativas.max_alternativas = 3
            for caso in cargar(idioma, archivo):
                marca = time.perf_counter()
                r = motor.consultar(caso["pregunta"], f"alternativas:{caso['id']}")
                ms = (time.perf_counter() - marca) * 1000
                contrato = r.diagnostico.get("contrato_http") or {}
                alternativas = r.diagnostico.get("alternativas") or {}
                casos.append({
                    **caso, "estado": r.estado.value, "motivo": r.motivo, "regla": r.diagnostico.get("regla"),
                    "mensaje": r.mensaje_usuario, "latencia_ms": round(ms, 1),
                    "etapa_politica_ms": (r.diagnostico.get("etapas") or {}).get("politica_ms"),
                    "relacionados": [f["texto"] for f in contrato.get("fragmentos") or []]
                    if r.estado.value == "relacionado" else [],
                    "unidades": [*(alternativas.get("ofrecidas") or []), *(alternativas.get("descartadas") or [])],
                })
        finally:
            os.chdir(anterior)
            configurar_idioma(previo[0])
            configurar_perfil(previo[1])
    return {"casos": casos}


# --- re-decisión y métricas ----------------------------------------------------------------------
def afinidad(senales: dict, pesos: dict) -> float:
    total = sum(max(0.0, pesos.get(s, 0.0)) for s in SENALES)
    return sum(max(0.0, pesos.get(s, 0.0)) * senales.get(s, 0.0) for s in SENALES) / total if total else 0.0


def ofrecidas(caso: dict, umbral: float, pesos: dict, maximo: int = 3) -> list[dict]:
    """Lo que el motor ofrecería con estos pesos y umbral (misma regla que ``buscar_alternativas``)."""
    if caso["estado"] != "sin_respuesta":
        return []
    elegibles = [u for u in caso["unidades"]
                 if any(u["senales"].get(s, 0) > 0 for s in ("familia", "medida", "terminos"))]
    hay_familia = any(u["senales"].get("familia", 0) > 0 for u in elegibles)
    puntuadas = sorted(((afinidad(u["senales"], pesos), u) for u in elegibles), key=lambda par: -par[0])
    salida, vistos = [], set()
    for valor, unidad in puntuadas:
        clave = " ".join(unidad["texto"].split())
        if clave in vistos:
            continue
        vistos.add(clave)
        if valor >= umbral and (unidad["senales"].get("familia", 0) > 0 or not hay_familia) and len(salida) < maximo:
            salida.append(unidad)
    return salida


def aceptable(caso: dict, texto: str) -> bool:
    return caso["tipo"] in ("vecino", "exacta") and any(a in texto for a in caso.get("aceptables") or [])


def resumir(casos: list[dict], umbral: float, pesos: dict, maximo: int = 3) -> dict:
    total = correctas = fuera = 0
    vecinos = [c for c in casos if c["tipo"] == "vecino"]
    vecinos_abst = [c for c in vecinos if c["estado"] == "sin_respuesta"]
    cubiertos = visibles = 0
    for caso in casos:
        dadas = ofrecidas(caso, umbral, pesos, maximo)
        buenas = [u for u in dadas if aceptable(caso, u["texto"])]
        total += len(dadas)
        correctas += len(buenas)
        if caso["tipo"] == "fuera_dominio" and dadas:
            fuera += 1
        if caso["tipo"] == "vecino":
            cubiertos += bool(buenas)
            visibles += bool(buenas) or any(aceptable(caso, t) for t in caso["relacionados"])
    return {
        "alternativas": total, "correctas": correctas,
        "precision": round(correctas / total, 4) if total else None,
        "fuera_dominio_con_alternativas": fuera,
        "cobertura": round(cubiertos / len(vecinos_abst), 4) if vecinos_abst else None,
        "vecinos_en_abstencion": len(vecinos_abst), "vecinos_cubiertos": cubiertos,
        "vecino_visible": f"{visibles}/{len(vecinos)}",
        "casos_con_alternativas": sum(bool(ofrecidas(c, umbral, pesos, maximo)) for c in casos),
    }


def _casos(datos: dict, particion: str | None = None, perfil: str | None = None) -> list[dict]:
    return [c for p, idiomas in datos.items() if perfil in (None, p) for d in idiomas.values() for c in d["casos"]
            if particion in (None, c["particion"])]


def _preparar(casos: list[dict]) -> list[dict]:
    """Por caso, las líneas elegibles agrupadas por texto, como matrices: la
    calibración prueba miles de combinaciones de pesos sin rehacer el orden."""
    import numpy as np

    preparados = []
    for caso in casos:
        if caso["estado"] != "sin_respuesta":
            continue
        elegibles = [u for u in caso["unidades"]
                     if any(u["senales"].get(s, 0) > 0 for s in ("familia", "medida", "terminos"))]
        if not elegibles:
            continue
        if any(u["senales"].get("familia", 0) > 0 for u in elegibles):
            elegibles = [u for u in elegibles if u["senales"].get("familia", 0) > 0]
        grupos: dict[str, list[dict]] = {}
        for u in elegibles:
            grupos.setdefault(" ".join(u["texto"].split()), []).append(u)
        filas, grupo, buenas = [], [], []
        for g, (clave, unidades) in enumerate(grupos.items()):
            buenas.append(aceptable(caso, clave))
            for u in unidades:
                filas.append([u["senales"].get(s, 0.0) for s in SENALES])
                grupo.append(g)
        preparados.append({"tipo": caso["tipo"], "senales": np.asarray(filas), "grupo": np.asarray(grupo),
                           "n": len(grupos), "buenas": np.asarray(buenas)})
    return preparados


def _tabla(preparados: list[dict], pesos, umbrales, maximo: int = 3) -> dict:
    """Por umbral: alternativas, correctas, casos fuera de dominio con alguna y
    vecinos cubiertos; lo mismo que ``resumir`` con esos pesos."""
    import numpy as np

    w = np.asarray(pesos, dtype=float)
    total = w.sum()
    u = np.asarray(umbrales)
    ofrecidas = np.zeros(len(u))
    correctas = np.zeros(len(u))
    fuera = np.zeros(len(u))
    cubiertos = np.zeros(len(u))
    for caso in preparados:
        afinidad_unidad = caso["senales"] @ w / total
        mejor = np.full(caso["n"], -1.0)
        np.maximum.at(mejor, caso["grupo"], afinidad_unidad)
        orden = np.argsort(-mejor, kind="stable")[:maximo]
        valores, buenas = mejor[orden], caso["buenas"][orden]
        dadas = (valores[None, :] >= u[:, None])  # umbral × posición (valores ya en orden)
        n_dadas = dadas.sum(axis=1)
        n_buenas = (dadas & buenas[None, :]).sum(axis=1)
        ofrecidas += n_dadas
        correctas += n_buenas
        if caso["tipo"] == "fuera_dominio":
            fuera += n_dadas > 0
        if caso["tipo"] == "vecino":
            cubiertos += n_buenas > 0
    return {"ofrecidas": ofrecidas, "correctas": correctas, "fuera": fuera, "cubiertos": cubiertos}


def calibrar(datos: dict, *, precision_minima: float = 0.9, tolerancia: float = 0.9) -> dict:
    """Pesos (una sola combinación) y umbral por perfil, elegidos con los casos
    de desarrollo (dev y test de ``casos.yaml``: test se mira durante el
    desarrollo, así que no es una validación intacta; la validación apartada
    es ``validacion.yaml``, que se mide una vez con lo elegido aquí).

    Un umbral es válido si deja la precisión ≥ ``precision_minima`` y ningún
    caso fuera de dominio con alternativas. La mejor cobertura alcanzable
    (sobre todas las combinaciones) fija un piso: ``tolerancia`` de ella.
    Entre las combinaciones que lo alcanzan en todos los perfiles gana la del
    **margen** más ancho: el tramo contiguo de umbrales válidos que lo
    alcanzan. El umbral es el centro del tramo. Con cobertura máxima, todas
    las combinaciones quedaban al borde (tramos de 0,05): un umbral así deja
    pasar lo que el desarrollo no mostró."""
    import numpy as np

    perfiles = sorted(datos)
    umbrales = np.round(np.arange(101) * 0.01, 2)
    preparados = {perfil: _preparar(_casos(datos, None, perfil)) for perfil in perfiles}
    tablas = {}
    for combinacion in itertools.product((0.0, 1.0, 2.0), repeat=len(SENALES)):
        if not any(combinacion):
            continue
        tabla = {}
        for perfil in perfiles:
            t = _tabla(preparados[perfil], combinacion, umbrales)
            with np.errstate(divide="ignore", invalid="ignore"):
                precision = np.where(t["ofrecidas"] > 0, t["correctas"] / t["ofrecidas"], 1.0)
            tabla[perfil] = ((precision >= precision_minima) & (t["fuera"] == 0), t["cubiertos"])
        tablas[combinacion] = tabla
    mejor_cobertura = {perfil: max((float(c[v].max()) for t in tablas.values() for v, c in [t[perfil]] if v.any()),
                                   default=0.0) for perfil in perfiles}
    mejor = None
    for combinacion, tabla in tablas.items():
        por_perfil, margen = {}, 0.0
        for perfil in perfiles:
            validos, cubiertos = tabla[perfil]
            ok = validos & (cubiertos >= tolerancia * mejor_cobertura[perfil])
            tramo, actual = (0, -1), None
            for i, bien in enumerate(ok):
                if bien:
                    actual = (actual[0], i) if actual else (i, i)
                    if actual[1] - actual[0] > tramo[1] - tramo[0]:
                        tramo = actual
                else:
                    actual = None
            if tramo[1] < tramo[0]:
                break
            bajo, alto = float(umbrales[tramo[0]]), float(umbrales[tramo[1]])
            por_perfil[perfil] = {"umbral": round((bajo + alto) / 2, 2), "tramo": [bajo, alto]}
            margen += alto - bajo
        else:
            clave = (round(margen, 4), -sum(combinacion))
            if mejor is None or clave > mejor[0]:
                mejor = (clave, dict(zip(SENALES, combinacion)), por_perfil)
    if mejor is None:
        return {"pesos": None, "mejor_cobertura": mejor_cobertura, "perfiles": {}}
    _, pesos, por_perfil = mejor
    for perfil, valores in por_perfil.items():
        for nombre, particion in (("desarrollo", None), ("dev", "dev"), ("test", "test")):
            valores[nombre] = resumir(_casos(datos, particion, perfil), valores["umbral"], pesos)
    return {"pesos": pesos, "mejor_cobertura": mejor_cobertura, "perfiles": por_perfil}


def _unir(rutas: list[str]) -> dict:
    datos: dict = {}
    for ruta in rutas:
        for perfil, idiomas in json.loads(Path(ruta).read_text(encoding="utf-8")).items():
            datos.setdefault(perfil, {}).update(idiomas)
    return datos


def main_cli(argv: list[str]) -> None:
    if argv and argv[0] == "--calibrar":
        print(json.dumps(calibrar(_unir(argv[1:])), ensure_ascii=False, indent=1))
        return
    if argv and argv[0] == "--resumir":
        datos = _unir([argv[1]])
        umbral = float(argv[2]) if len(argv) > 2 else 0.0
        pesos = json.loads(Path(argv[3]).read_text(encoding="utf-8")) if len(argv) > 3 else dict.fromkeys(SENALES, 1.0)
        for perfil, idiomas in datos.items():
            for idioma, d in idiomas.items():
                print(perfil, idioma, json.dumps(resumir(d["casos"], umbral, pesos), ensure_ascii=False))
        return
    salida = Path(argv[0])
    perfiles = (argv[1] if len(argv) > 1 else "light,medium").split(",")
    idiomas = (argv[2] if len(argv) > 2 else ",".join(IDIOMAS)).split(",")
    archivo = argv[3] if len(argv) > 3 else "casos"
    resultado: dict = {}
    for perfil in perfiles:
        for idioma in idiomas:
            medido = medir_idioma(idioma, perfil, archivo)
            resultado.setdefault(perfil, {})[idioma] = medido
            estados: dict[str, int] = {}
            for c in medido["casos"]:
                estados[c["estado"]] = estados.get(c["estado"], 0) + 1
            print(perfil, idioma, estados, flush=True)
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main_cli(sys.argv[1:])
