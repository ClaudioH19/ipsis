"""Construye el banco de pasajes desde sus fuentes.

Fuentes: ``es/corpus/*.md`` y ``es/casos.yaml`` (generadas por
``generar_fuentes.py``). Derivados versionados: ``es/banco.jsonl`` y
``es/manifiesto.json``, en el formato de ``ipsis.evaluacion.banco``.

La clase sale del id: ``segunda`` (respuesta en la segunda mitad de una sección
larga), ``hermana`` (distingue secciones o documentos parecidos), ``parafrasis``
y ``trampa`` (mismo tema, dato ausente). La partición es 60/40 por posición
dentro de cada clase (3 de cada 5 casos a ``dev``); la trampa va con su par.

    python tests/datos/banco_pasajes/construir.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ipsis.evaluacion.banco import (
    ArchivoCorpus,
    BancoEvaluacion,
    CasoEvaluacion,
    CategoriaPregunta,
    CorpusBanco,
    EvidenciaEsperada,
    ManifiestoBanco,
    hash_archivos_corpus,
)
from ipsis.evaluacion.golden import oracion_de, ubicar_respuesta
from ipsis.ingesta.parsear import parsear_documento

RAIZ = Path(__file__).resolve().parent
IDIOMAS = ("es",)
VERSION = "1.0.0"
CATEGORIAS = {
    "segunda": CategoriaPregunta.EXACTA,
    "hermana": CategoriaPregunta.EXACTA,
    "parafrasis": CategoriaPregunta.PARAFRASIS,
    "trampa": CategoriaPregunta.SIN_RESPUESTA,
}


def doc_id(archivo: str) -> str:
    return Path(archivo).stem.replace("_", "-")


def construir(idioma: str, raiz: Path = RAIZ) -> tuple[str, str]:
    carpeta = raiz / idioma
    archivos = [ArchivoCorpus(ruta=p.name, doc_id=doc_id(p.name)) for p in sorted((carpeta / "corpus").glob("*.md"))]
    textos = {a.doc_id: parsear_documento(str(carpeta / "corpus" / a.ruta), doc_id=a.doc_id, doc_titulo=a.doc_id,
                                          version="1").texto_completo for a in archivos}
    fuentes = yaml.safe_load((carpeta / "casos.yaml").read_text(encoding="utf-8"))
    split_de: dict[str, str] = {}
    vistos: dict[str, int] = {}
    casos = []
    for fuente in fuentes:
        clase = fuente["id"].split("-")[1]
        if "par" in fuente:
            split = split_de[fuente["par"]]
        else:
            posicion = vistos.get(clase, 0)
            vistos[clase] = posicion + 1
            split = "dev" if posicion % 5 < 3 else "test"
        split_de[fuente["id"]] = split
        comunes = dict(dataset_version=VERSION, id=fuente["id"], split=split, categoria=CATEGORIAS[clase],
                       pregunta=fuente["pregunta"])
        if clase == "trampa":
            casos.append(CasoEvaluacion(**comunes, estado_esperado="sin_respuesta", respondible=False,
                                        par=fuente["par"], subtipo="trampa_mismo_tema",
                                        notas=f"documento: {fuente['documento']}"))
            continue
        ubicacion, _ = ubicar_respuesta(fuente["respuesta"], textos, doc_id(fuente["documento"]))
        texto = textos[ubicacion.doc_id]
        ini, fin = oracion_de(texto, ubicacion.inicio, ubicacion.fin)
        casos.append(CasoEvaluacion(
            **comunes, estado_esperado="respuesta_directa", respondible=True,
            respuesta_literal=ubicacion.texto,
            evidencias=[EvidenciaEsperada(doc_id=ubicacion.doc_id, offset_inicio=ini, offset_fin=fin,
                                          texto=texto[ini:fin])],
            notas=f"seccion: {fuente['seccion']}"))
    manifiesto = ManifiestoBanco(
        dataset_id=f"pasajes_{idioma}", dataset_version=VERSION, tipo="sintetico", estado="estable",
        casos="banco.jsonl",
        corpus=CorpusBanco(directorio="corpus", archivos=archivos,
                           sha256=hash_archivos_corpus(carpeta / "corpus", archivos)),
        categorias_requeridas=sorted({c.categoria for c in casos}, key=lambda c: c.value),
        uso="regresion", idioma=idioma,
    )
    banco = BancoEvaluacion(manifiesto=manifiesto, casos=casos)
    return (banco.manifiesto.model_dump_json(indent=2, exclude_none=True) + "\n",
            "\n".join(c.model_dump_json(exclude_none=True) for c in banco.casos) + "\n")


def escribir() -> None:
    for idioma in IDIOMAS:
        manifiesto, casos = construir(idioma)
        (RAIZ / idioma / "manifiesto.json").write_bytes(manifiesto.encode("utf-8"))
        (RAIZ / idioma / "banco.jsonl").write_bytes(casos.encode("utf-8"))


if __name__ == "__main__":
    escribir()
