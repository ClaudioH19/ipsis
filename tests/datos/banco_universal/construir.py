"""Construye el banco universal de cada idioma desde sus fuentes.

Fuentes (se editan a mano): ``<idioma>/corpus/*.md`` y ``<idioma>/casos.yaml``.
Derivados (versionados): ``<idioma>/banco.jsonl`` y ``<idioma>/manifiesto.json``,
en el formato del banco interno (``ipsis.evaluacion.banco``).

La categoría la fija el autor por el id (``exacta``, ``parafrasis``, ``trampa``,
``premisa``, ``ambigua``, ``fuera``), no ``s_cov``: una paráfrasis real cuenta
como paráfrasis aunque al sistema le cueste. Las evidencias y offsets salen de
los mismos ayudantes que ``ipsis golden importar``.

Regenerar tras editar una fuente::

    python tests/datos/banco_universal/construir.py

``tests/evaluacion/test_banco_universal.py`` falla si los derivados no
coinciden con lo que este script produce.
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
IDIOMAS = ("es", "en", "pt")
VERSION = "1.0.0"
CATEGORIAS = {
    "exacta": (CategoriaPregunta.EXACTA, "respuesta_directa"),
    "parafrasis": (CategoriaPregunta.PARAFRASIS, "respuesta_directa"),
    "trampa": (CategoriaPregunta.SIN_RESPUESTA, "sin_respuesta"),
    "premisa": (CategoriaPregunta.PREMISA_FALSA, "sin_respuesta"),
    "ambigua": (CategoriaPregunta.AMBIGUA, "necesita_aclaracion"),
    "fuera": (CategoriaPregunta.SIN_RESPUESTA, "fuera_dominio"),
}


def doc_id(archivo: str) -> str:
    return Path(archivo).stem.replace("_", "-")


def construir(idioma: str) -> tuple[str, str]:
    """``(manifiesto.json, banco.jsonl)`` del idioma, como texto."""
    carpeta = RAIZ / idioma
    archivos = [ArchivoCorpus(ruta=p.name, doc_id=doc_id(p.name)) for p in sorted((carpeta / "corpus").glob("*.md"))]
    textos = {a.doc_id: parsear_documento(str(carpeta / "corpus" / a.ruta), doc_id=a.doc_id, doc_titulo=a.doc_id,
                                          version="1").texto_completo for a in archivos}
    fuentes = yaml.safe_load((carpeta / "casos.yaml").read_text(encoding="utf-8"))
    split_de: dict[str, str] = {}
    vistos: dict[str, int] = {}
    casos = []
    for fuente in fuentes:
        clase = fuente["id"].split("-")[1]
        categoria, estado = CATEGORIAS[clase]
        if "par" in fuente:  # la trampa va en el mismo split que su par
            split = split_de[fuente["par"]]
        else:
            vistos[clase] = vistos.get(clase, 0) + 1
            split = "dev" if vistos[clase] % 2 else "test"
        split_de[fuente["id"]] = split
        comunes = dict(dataset_version=VERSION, id=fuente["id"], split=split, categoria=categoria,
                       pregunta=fuente["pregunta"], estado_esperado=estado)
        if "respuesta" in fuente:
            ubicacion, _ = ubicar_respuesta(fuente["respuesta"], textos, doc_id(fuente["documento"]))
            texto = textos[ubicacion.doc_id]
            ini, fin = oracion_de(texto, ubicacion.inicio, ubicacion.fin)
            casos.append(CasoEvaluacion(
                **comunes, respondible=True, respuesta_literal=ubicacion.texto,
                evidencias=[EvidenciaEsperada(doc_id=ubicacion.doc_id, offset_inicio=ini, offset_fin=fin,
                                              texto=texto[ini:fin])],
                notas=f"capacidad: {fuente['capacidad']}"))
        else:
            casos.append(CasoEvaluacion(
                **comunes, respondible=False, par=fuente.get("par"),
                subtipo="trampa_mismo_tema" if clase == "trampa" else None))
    manifiesto = ManifiestoBanco(
        dataset_id=f"universal_{idioma}", dataset_version=VERSION, tipo="sintetico", estado="estable",
        casos="banco.jsonl",
        corpus=CorpusBanco(directorio="corpus", archivos=archivos,
                           sha256=hash_archivos_corpus(carpeta / "corpus", archivos)),
        categorias_requeridas=sorted({c.categoria for c in casos}, key=lambda c: c.value),
        uso="regresion",
        idioma=idioma,
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
