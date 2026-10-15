"""Genera las fuentes del banco de pasajes (``<idioma>/corpus/*.md`` y ``<idioma>/casos.yaml``).

El banco mide el orden de pasajes dentro de documentos largos y entre secciones
«hermanas» (mismo tema, distinto actor, producto o cifra). Cada documento tiene
una sección por elemento; todas siguen el mismo esqueleto:

    3 párrafos generales -> hechos tempranos -> 2 generales -> hechos tardíos -> 2 generales

Así los hechos tardíos caen en la segunda mitad de una sección de más de 300
palabras. Las frases de hecho son paralelas entre hermanas y solo cambian el
actor y la cifra, que es lo que la recuperación debe distinguir.

El contenido de cada idioma vive en ``contenido_<idioma>.py`` (es, en, pt): mismos documentos,
hechos y cifras, redactados en ese idioma, con preguntas formales e informales (como las escribe
quien chatea). Es determinista: la misma ejecución produce los mismos archivos.

    python tests/datos/banco_pasajes/generar_fuentes.py [es en pt]
    python tests/datos/banco_pasajes/construir.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent
IDIOMAS = ("es", "en", "pt")


def cargar_contenido(idioma: str):
    spec = importlib.util.spec_from_file_location(f"contenido_{idioma}", RAIZ / f"contenido_{idioma}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _seccion(h2, S, pre_idx, pool, tema, tempranos, tardios, vals, extra_unidad=None):
    """Compone una sección: 3 generales, hechos tempranos, 2 generales, hechos tardíos, 2 generales."""
    fmt = dict(vals)
    fmt["S"] = S
    fmt["H"] = h2
    fmt["t"] = tema
    if extra_unidad:
        fmt["U"] = extra_unidad
    n = len(pool)
    gen = [pool[(pre_idx * 3 + k) % n].format(**fmt) for k in range(7)]
    parrafos = [gen[0], gen[1], gen[2]]
    parrafos.append(" ".join(f["sent"].format(**fmt) for f in tempranos))
    parrafos += [gen[3], gen[4]]
    parrafos.append(" ".join(f["sent"].format(**fmt) for f in tardios))
    parrafos += [gen[5], gen[6]]
    return "## " + h2 + "\n\n" + "\n\n".join(parrafos) + "\n"


def _normalizar_hechos(hechos):
    return [dict(fase=fase, sent=sent, resp=resp, q=q, p=p) for fase, sent, resp, q, p in hechos]


def construir_documento(titulo, intro, tema, secciones, pool, propios, unidad=None):
    """secciones: lista de (h2, S, hechos_normalizados, vals)."""
    partes = ["# " + titulo + "\n", intro + "\n"]
    for i, (h2, S, hechos, vals) in enumerate(secciones):
        tem = [h for h in hechos if h["fase"] == "temprano"]
        tar = [h for h in hechos if h["fase"] == "tardio"]
        # Los párrafos propios del documento se mezclan con los generales.
        grupo = list(propios) + pool
        partes.append(_seccion(h2, S, i, grupo, tema, tem, tar, vals, unidad))
    return "\n".join(partes)


def _dar_formato(plantilla, S, vals, U):
    fmt = dict(vals)
    fmt["S"] = S
    if U:
        fmt["U"] = U
    return plantilla.format(**fmt)


def generar_casos(c, casos_spec) -> list[dict]:
    """Elige las preguntas de forma determinista a partir de los hechos."""
    por_doc: dict[str, list] = {}
    for archivo, h2, S, hechos, vals, U in casos_spec:
        por_doc.setdefault(archivo, []).append((h2, S, hechos, vals, U))
    principales = [d["archivo"] for d in c.DOCS]
    gemelos = [a for a in por_doc if a not in principales]
    usados: set = set()
    casos: list[dict] = []

    def agregar(clase, archivo, item, idx, variante):
        h2, S, hechos, vals, U = por_doc[archivo][item]
        h = hechos[idx]
        usados.add((archivo, item, idx))
        casos.append(dict(
            clase=clase, documento=archivo, seccion=h2,
            pregunta=_dar_formato(h[variante], S, vals, U),
            respuesta=_dar_formato(h["resp"], S, vals, U),
            fase=h["fase"],
        ))

    # 42 de la segunda mitad: hechos tardíos de los 6 documentos principales.
    for archivo in principales:
        for k in range(7):
            item = k % 6
            tardios = [i for i, h in enumerate(por_doc[archivo][item][2]) if h["fase"] == "tardio"]
            agregar("segunda", archivo, item, tardios[(k + k // 6) % len(tardios)], "q")
    # 36 hermanas en los principales (hechos tempranos) y 16 en los gemelos.
    for archivo in principales:
        for k in range(6):
            tempranos = [i for i, h in enumerate(por_doc[archivo][k][2]) if h["fase"] == "temprano"]
            agregar("hermana", archivo, k, tempranos[k % len(tempranos)], "q")
    for archivo in gemelos:
        for k in range(5):
            if k == 1:
                continue
            fases = [i for i, h in enumerate(por_doc[archivo][k][2])]
            agregar("hermana", archivo, k, fases[(k + len(archivo)) % len(fases)], "q")
    # 22 paráfrasis informales: hechos que aún no tienen pregunta.
    for archivo in principales:
        quedan = [(it, i) for it in range(6) for i in range(len(por_doc[archivo][it][2]))
                  if (archivo, it, i) not in usados]
        for it, i in quedan[::7][:3]:
            agregar("parafrasis", archivo, it, i, "p")
    for archivo in gemelos:
        quedan = [(it, i) for it in range(5) for i in range(2) if (archivo, it, i) not in usados]
        agregar("parafrasis", archivo, *quedan[0], "p")

    n = {}
    for caso in casos:
        n[caso["clase"]] = n.get(caso["clase"], 0) + 1
        caso["id"] = f"{c.IDIOMA}-{caso['clase']}-{n[caso['clase']]:03d}"
    hermanas = {}
    for caso in casos:
        if caso["clase"] == "hermana":
            hermanas.setdefault(caso["documento"], caso["id"])
    for j, (archivo, pregunta) in enumerate(c.TRAMPAS, 1):
        casos.append(dict(id=f"{c.IDIOMA}-trampa-{j:03d}", clase="trampa", documento=archivo,
                          par=hermanas[archivo], pregunta=pregunta))
    return casos


def generar(idioma: str) -> None:
    c = cargar_contenido(idioma)
    salida = RAIZ / idioma
    corpus = salida / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    casos_spec = []

    for d in c.DOCS:
        hechos = _normalizar_hechos(d["hechos"])
        secciones = [(h2, S, hechos, vals) for h2, S, vals in d["items"]]
        texto = construir_documento(d["titulo"], d["intro"], d["tema"], secciones, c.GENERALES, d["propios"])
        (corpus / d["archivo"]).write_text(texto, encoding="utf-8")
        for h2, S, vals in d["items"]:
            casos_spec.append((d["archivo"], h2, S, hechos, vals, None))

    for clave, g in c.GEM.items():
        for unidad in c.UNIDADES:
            archivo = g["archivos"][unidad]
            secciones = []
            for (h2, S, hs), vals in zip(g["secciones"], g["valores"][unidad]):
                secciones.append((h2, S, _normalizar_hechos(hs), vals))
            texto = construir_documento(g["titulo"].format(U=unidad), g["intro"].format(U=unidad), g["tema"],
                                        secciones, c.GENERALES, [], unidad)
            (corpus / archivo).write_text(texto, encoding="utf-8")
            for h2, S, hechos, vals in secciones:
                casos_spec.append((archivo, h2, S, hechos, vals, unidad))

    casos = generar_casos(c, casos_spec)
    cabecera = (f"# Banco de pasajes, {idioma} (fuente generada por generar_fuentes.py). La clase sale del id: segunda,\n"
                "# hermana, parafrasis y trampa. construir.py calcula evidencias, offsets y particiones.\n")
    cuerpo = yaml.safe_dump([{k: v for k, v in caso.items() if k != "fase"} for caso in casos],
                            allow_unicode=True, sort_keys=False, width=1000)
    (salida / "casos.yaml").write_text(cabecera + cuerpo, encoding="utf-8")


def main(argv: list[str]) -> None:
    for idioma in argv or [i for i in IDIOMAS if (RAIZ / f"contenido_{i}.py").is_file()]:
        generar(idioma)


if __name__ == "__main__":
    main(sys.argv[1:])
