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
SENALES = ("familia", "terminos", "seccion", "keywords", "categoria", "similitud")


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
                 if u["senales"].get("familia", 0) > 0 or u["senales"].get("terminos", 0) > 0]
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


def calibrar(datos: dict, *, precision_minima: float = 0.9, tolerancia: float = 0.9) -> dict:
    """Pesos (una sola combinación) y umbral por perfil, elegidos con los casos
    de desarrollo (dev y test de ``casos.yaml``: test se usó durante el
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
    perfiles = sorted(datos)
    umbrales = [round(0.01 * i, 2) for i in range(101)]
    casos = {perfil: _casos(datos, None, perfil) for perfil in perfiles}
    tablas = {}
    for combinacion in itertools.product((0.0, 1.0, 2.0), repeat=len(SENALES)):
        if not any(combinacion):
            continue
        pesos = dict(zip(SENALES, combinacion))
        tabla = {}
        for perfil in perfiles:
            filas = []
            for umbral in umbrales:
                r = resumir(casos[perfil], umbral, pesos)
                ok = not r["fuera_dominio_con_alternativas"] and (r["precision"] is None or r["precision"] >= precision_minima)
                filas.append((umbral, ok, r))
            tabla[perfil] = filas
        tablas[combinacion] = tabla
    mejor_cobertura = {perfil: max((r["vecinos_cubiertos"] for t in tablas.values() for _, ok, r in t[perfil] if ok),
                                   default=0) for perfil in perfiles}
    mejor = None
    for combinacion, tabla in tablas.items():
        por_perfil, margen = {}, 0.0
        for perfil in perfiles:
            piso = tolerancia * mejor_cobertura[perfil]
            tramo, actual = [], []
            for umbral, ok, r in tabla[perfil]:
                actual = [*actual, umbral] if ok and r["vecinos_cubiertos"] >= piso else []
                if len(actual) > len(tramo):
                    tramo = actual
            if not tramo:
                break
            centro = round((tramo[0] + tramo[-1]) / 2, 2)
            por_perfil[perfil] = {"umbral": centro, "tramo": [tramo[0], tramo[-1]]}
            margen += tramo[-1] - tramo[0]
        else:
            clave = (round(margen, 4), -sum(combinacion))
            if mejor is None or clave > mejor[0]:
                mejor = (clave, dict(zip(SENALES, combinacion)), por_perfil)
    if mejor is None:
        return {"pesos": None, "perfiles": {}}
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
