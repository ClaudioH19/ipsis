"""Casos de uso de ``ipsis golden``: plantilla, importar, validar y exportar.

Orquesta el proyecto activo (catálogo, documentos, idioma) y delega en
``ipsis.evaluacion.golden``. No usa modelos ni red: el golden solo mide.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ipsis.configuracion import rutas
from ipsis.evaluacion.golden import ErrorGolden

FORMATOS_EXPORTACION = {"squad2": "exportado.squad2.json", "csv": "exportado.csv"}


@dataclass
class ResumenBanco:
    manifiesto: Path
    por_tipo: dict[str, int]
    por_split: dict[str, int]
    avisos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Corpus:
    documentos: list  # DocumentoParseado
    textos: dict[str, str]
    alias: dict[str, str]
    banco: object  # CorpusBanco


def _paquete():
    from ipsis.configuracion.carga import cargar_dominio
    from ipsis.lenguaje.paquete import cargar_paquete

    return cargar_paquete(cargar_dominio().get("idioma", "es"), proyecto=Path.cwd())


def _corpus() -> _Corpus:
    """Documentos del catálogo, ya parseados, y su descripción para el manifiesto."""
    from ipsis.evaluacion.banco import ArchivoCorpus, CorpusBanco, hash_archivos_corpus
    from ipsis.ingesta.catalogo import entradas_vigentes
    from ipsis.ingesta.ingesta import parsear_corpus

    catalogo = entradas_vigentes(rutas.CATALOGO)
    if not catalogo:
        raise ErrorGolden(["no hay documentos en el catálogo: agrégalos con 'ipsis cargar <archivo|carpeta>'"])
    documentos = parsear_corpus(rutas.DOCUMENTOS)
    alias: dict[str, str] = {}
    for entrada in catalogo:
        for nombre in (entrada.get("doc_titulo"), entrada["archivo"], Path(entrada["archivo"]).stem):
            if nombre:
                alias.setdefault(str(nombre), entrada["doc_id"])
    archivos = [ArchivoCorpus(ruta=e["archivo"], doc_id=e["doc_id"]) for e in catalogo]
    # El manifiesto vive en golden/banco/: el corpus se declara relativo a él.
    directorio = "/".join([".."] * len(Path(rutas.GOLDEN_BANCO).parts) + [rutas.DOCUMENTOS])
    banco = CorpusBanco(directorio=directorio, archivos=archivos,
                        sha256=hash_archivos_corpus(Path(rutas.DOCUMENTOS), archivos))
    return _Corpus(documentos, {d.doc_id: d.texto_completo for d in documentos}, alias, banco)


def generar_plantilla_golden(n: int = 40, forzar: bool = False) -> tuple[Path, Path, list[str]]:
    """Escribe ``golden/golden.csv`` y ``golden/LEEME.txt``.

    No reemplaza un ``golden.csv`` existente sin ``forzar``: puede tener
    preguntas que el cliente ya escribió.
    """
    from ipsis.evaluacion.golden import escribir_plantilla, generar_plantilla

    destino = Path(rutas.GOLDEN) / "golden.csv"
    if destino.exists() and not forzar:
        raise FileExistsError(destino)
    plantilla = generar_plantilla(_corpus().documentos, _paquete(), n=n)
    ruta_csv, ruta_leeme = escribir_plantilla(plantilla, rutas.GOLDEN)
    return ruta_csv, ruta_leeme, plantilla.avisos


def _resumen(banco, manifiesto: Path, avisos: list[str]) -> ResumenBanco:
    from ipsis.evaluacion.golden import TIPO_PUBLICO

    return ResumenBanco(
        manifiesto=manifiesto,
        por_tipo=dict(Counter(TIPO_PUBLICO[c.categoria] for c in banco.casos)),
        por_split=dict(Counter(c.split for c in banco.casos)),
        avisos=avisos,
    )


def importar_golden(ruta: str | Path) -> ResumenBanco:
    """Lee el golden (CSV, JSONL o SQuAD 2.0), lo valida contra el corpus y
    escribe ``golden/banco/``. Si hay errores no escribe nada."""
    from ipsis.evaluacion.golden import a_banco, escribir_banco, leer_golden, secciones_de
    from ipsis.indice.estadisticas import EstadisticasLexicas

    ruta = Path(ruta)
    filas = leer_golden(ruta)
    corpus = _corpus()
    paquete = _paquete()
    # El IDF de s_cov (exacta/parafrasis) sale de las secciones del corpus, igual
    # que en la plantilla: no depende de que el índice exista.
    estadisticas = EstadisticasLexicas.construir(
        [s.texto for d in corpus.documentos for s in secciones_de(d)], paquete)
    formato = {".csv": "csv", ".jsonl": "jsonl", ".json": "squad2"}[ruta.suffix.lower()]
    resultado = a_banco(filas, corpus.textos, corpus.banco, estadisticas=estadisticas, paquete=paquete,
                        alias=corpus.alias, procedencia={"formato": formato, "archivo": ruta.name})
    manifiesto = escribir_banco(resultado.banco, rutas.GOLDEN_BANCO)
    return _resumen(resultado.banco, manifiesto, resultado.avisos)


def _cargar_banco_vigente():
    """El banco importado, solo si sigue siendo válido para el corpus actual."""
    from ipsis.evaluacion.banco import cargar_banco, validar_evidencias_contra_corpus

    manifiesto = Path(rutas.GOLDEN_MANIFIESTO)
    if not manifiesto.is_file():
        raise ErrorGolden(["no hay un banco golden importado. Genera la plantilla con 'ipsis golden plantilla', "
                           "complétala e impórtala con 'ipsis golden importar golden/golden.csv'"])
    try:
        banco = cargar_banco(manifiesto)
    except FileNotFoundError as e:
        raise ErrorGolden([f"falta un documento del banco en el corpus ({Path(e.filename).name}). "
                           "Vuelve a importar el golden con el corpus actual"]) from e
    except ValueError as e:
        if "hash del corpus" in str(e):
            raise ErrorGolden(["el corpus cambió desde que se importó el golden: los offsets pueden no ser "
                               "válidos. Vuelve a importarlo ('ipsis golden importar <archivo>') o revísalo"]) from e
        raise ErrorGolden([f"banco inválido: {e}"]) from e
    from ipsis.ingesta.parsear import parsear_documento

    textos = {}
    directorio = (manifiesto.parent / banco.manifiesto.corpus.directorio).resolve()
    for archivo in banco.manifiesto.corpus.archivos:
        documento = parsear_documento(str(directorio / archivo.ruta), doc_id=archivo.doc_id,
                                      doc_titulo=archivo.doc_id, version="1")
        textos[archivo.doc_id] = documento.texto_completo
    try:
        validar_evidencias_contra_corpus(banco, textos)
    except ValueError as e:
        raise ErrorGolden(str(e).splitlines()) from e
    return banco, textos, manifiesto


def validar_golden() -> ResumenBanco:
    """Solo lectura: el banco existe, su manifiesto es válido, el corpus no
    cambió y cada evidencia sigue en sus offsets. No repara nada."""
    banco, _textos, manifiesto = _cargar_banco_vigente()
    return _resumen(banco, manifiesto, [])


def exportar_golden(formato: str, salida: str | Path | None = None) -> tuple[Path, list[str]]:
    """Exporta el banco vigente a SQuAD 2.0 o a CSV (sin pisar ``golden.csv``)."""
    import json

    from ipsis.evaluacion.golden import (
        COLUMNAS_EXPORTADAS,
        escribir_atomico,
        escribir_csv,
        exportar_filas_csv,
        exportar_squad2,
    )

    if formato not in FORMATOS_EXPORTACION:
        raise ValueError(f"formato desconocido: {formato!r}; usa {', '.join(FORMATOS_EXPORTACION)}")
    banco, textos, _ = _cargar_banco_vigente()
    destino = Path(salida) if salida else Path(rutas.GOLDEN) / FORMATOS_EXPORTACION[formato]
    if formato == "csv":
        escribir_csv(exportar_filas_csv(banco), destino, COLUMNAS_EXPORTADAS)
        return destino, []
    datos, avisos = exportar_squad2(banco, textos)
    escribir_atomico(destino, json.dumps(datos, ensure_ascii=False, indent=2) + "\n")
    return destino, avisos


__all__ = [
    "ErrorGolden",
    "FORMATOS_EXPORTACION", "ResumenBanco", "exportar_golden", "generar_plantilla_golden", "importar_golden",
    "validar_golden",
]
