"""Golden set del cliente: lectura (CSV, JSONL, SQuAD 2.0) y conversión al banco.

El cliente escribe preguntas y copia la respuesta tal cual del documento; aquí
se ubica ese texto en el corpus, se calculan los offsets y se arma el banco
versionado (``rag.evaluacion.banco``). Ver docs/plan/comandos-y-golden.md §3.

Nada de esto entrena: el golden solo mide y, en ``rag calibrar``, elige umbrales.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rag.evaluacion.banco import (
    BancoEvaluacion,
    CasoEvaluacion,
    CategoriaPregunta,
    CorpusBanco,
    EvidenciaEsperada,
    ManifiestoBanco,
)

TIPOS = ("respondible", "sin_respuesta", "premisa_falsa", "ambigua", "conversacional")
SUBTIPOS = ("trampa_mismo_tema",)
COLUMNAS = ("id", "pregunta", "tipo", "respuesta_literal", "documento", "subtipo", "par", "notas",
            "fragmento_sugerido", "terminos_clave")
MINIMO_FILAS = 30
PROPORCION_MINIMA_SIN_RESPUESTA = 0.30
# Con 0 errores, la cota de Clopper-Pearson al 95% baja de 5% recién con 59
# respuestas aceptadas (comandos-y-golden.md §4.1).
ACEPTADAS_PARA_CERTIFICAR = 59
UMBRAL_EXACTA = 0.6  # s_cov(pregunta, evidencia) ≥ 0,6 → exacta; si no, parafrasis

_CATEGORIA_Y_ESTADO = {
    "sin_respuesta": (CategoriaPregunta.SIN_RESPUESTA, "sin_respuesta"),
    "premisa_falsa": (CategoriaPregunta.PREMISA_FALSA, "sin_respuesta"),
    "ambigua": (CategoriaPregunta.AMBIGUA, "necesita_aclaracion"),
    "conversacional": (CategoriaPregunta.CONVERSACIONAL, "conversacional"),
}
_RE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_RE_ESPACIOS = re.compile(r"\s+")


class ErrorGolden(ValueError):
    """El golden no se puede importar; ``errores`` dice qué fila corregir."""

    def __init__(self, errores: list[str]) -> None:
        super().__init__("\n".join(errores))
        self.errores = errores


@dataclass
class FilaGolden:
    pregunta: str
    tipo: str
    id: str | None = None
    respuesta_literal: str | None = None
    documento: str | None = None
    subtipo: str | None = None
    par: str | None = None
    notas: str | None = None
    origen: str = ""  # «golden.csv:12», para los mensajes


@dataclass(frozen=True)
class Ubicacion:
    doc_id: str
    inicio: int
    fin: int
    texto: str


@dataclass
class ResultadoImportacion:
    banco: BancoEvaluacion
    avisos: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------
def _limpio(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _fila(datos: dict, origen: str) -> FilaGolden:
    return FilaGolden(
        pregunta=_limpio(datos.get("pregunta")) or "",
        tipo=(_limpio(datos.get("tipo")) or "").lower(),
        id=_limpio(datos.get("id")),
        respuesta_literal=_limpio(datos.get("respuesta_literal")),
        documento=_limpio(datos.get("documento")),
        subtipo=_limpio(datos.get("subtipo")),
        par=_limpio(datos.get("par")),
        notas=_limpio(datos.get("notas")),
        origen=origen,
    )


def leer_csv(ruta: str | Path) -> list[FilaGolden]:
    """CSV en UTF-8 (con o sin BOM), separado por coma o por punto y coma.

    Excel en configuración regional española guarda con «;»: se detecta por la
    cabecera. Las filas sin pregunta (plantilla sin completar) se ignoran.
    """
    ruta = Path(ruta)
    texto = ruta.read_text(encoding="utf-8-sig")
    cabecera = texto.splitlines()[0] if texto else ""
    separador = ";" if cabecera.count(";") > cabecera.count(",") else ","
    lector = csv.DictReader(texto.splitlines(), delimiter=separador)
    faltantes = {"pregunta", "tipo"} - set(lector.fieldnames or [])
    if faltantes:
        raise ErrorGolden([f"{ruta.name}: faltan las columnas {sorted(faltantes)}"])
    filas = [_fila(datos, f"{ruta.name}:{n}") for n, datos in enumerate(lector, start=2)]
    return [f for f in filas if f.pregunta]


def leer_jsonl(ruta: str | Path) -> list[FilaGolden]:
    ruta = Path(ruta)
    filas = []
    for n, linea in enumerate(ruta.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if linea.strip():
            filas.append(_fila(json.loads(linea), f"{ruta.name}:{n}"))
    return filas


def leer_squad2(ruta: str | Path) -> list[FilaGolden]:
    """SQuAD 2.0 como formato de intercambio: ``is_impossible`` → sin_respuesta.

    El ``title`` de cada artículo se usa como ``documento``; la respuesta se
    vuelve a ubicar en el corpus del proyecto (el ``context`` no se usa).
    """
    ruta = Path(ruta)
    datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
    filas = []
    for articulo in datos.get("data", []):
        for parrafo in articulo.get("paragraphs", []):
            for qa in parrafo.get("qas", []):
                imposible = qa.get("is_impossible", False) or not qa.get("answers")
                fila = _fila({
                    "id": qa.get("id"),
                    "pregunta": qa.get("question"),
                    "tipo": "sin_respuesta" if imposible else "respondible",
                    "respuesta_literal": None if imposible else qa["answers"][0]["text"],
                    "documento": articulo.get("title"),
                }, f"{ruta.name}:{qa.get('id', '?')}")
                # Extensión propia (la escribe exportar) para conservar el tipo.
                if qa.get("rag_tipo") in TIPOS:
                    fila.tipo = qa["rag_tipo"]
                fila.subtipo = _limpio(qa.get("rag_subtipo"))
                fila.par = _limpio(qa.get("rag_par"))
                filas.append(fila)
    return filas


def leer_golden(ruta: str | Path) -> list[FilaGolden]:
    """Elige el lector por la extensión (``.json`` se lee como SQuAD 2.0)."""
    sufijo = Path(ruta).suffix.lower()
    lectores = {".csv": leer_csv, ".jsonl": leer_jsonl, ".json": leer_squad2}
    if sufijo not in lectores:
        raise ErrorGolden([f"formato no soportado: {sufijo or '(sin extensión)'}; usa .csv, .jsonl o .json (SQuAD 2.0)"])
    return lectores[sufijo](ruta)


# ---------------------------------------------------------------------------
# Ubicación de la respuesta y evidencia
# ---------------------------------------------------------------------------
def _colapsar(texto: str) -> tuple[str, list[int]]:
    """Texto con los espacios colapsados y, por carácter, su índice original."""
    salida: list[str] = []
    mapa: list[int] = []
    for m in re.finditer(r"\s+|\S", texto):
        salida.append(" " if m.group(0).isspace() else m.group(0))
        mapa.append(m.start())
    return "".join(salida), mapa


def _ocurrencias(respuesta: str, texto: str) -> list[tuple[int, int]]:
    exactas = [(m.start(), m.start() + len(respuesta)) for m in re.finditer(re.escape(respuesta), texto)]
    if exactas:
        return exactas
    colapsado, mapa = _colapsar(texto)
    buscada = _RE_ESPACIOS.sub(" ", respuesta.strip())
    # ``buscada`` no empieza ni termina en espacio: sus extremos son caracteres
    # reales del texto original.
    return [(mapa[m.start()], mapa[m.end() - 1] + 1) for m in re.finditer(re.escape(buscada), colapsado)]


def ubicar_respuesta(
    respuesta: str,
    documentos: dict[str, str],
    documento: str | None = None,
    alias: dict[str, str] | None = None,
) -> tuple[Ubicacion, list[str]]:
    """Ubica ``respuesta`` en el corpus: primero literal y después con los
    espacios colapsados (saltos de línea, dobles espacios), mapeando a los
    offsets originales. ``documento`` acepta un ``doc_id`` o un alias (título
    o nombre de archivo). Devuelve la ubicación y los avisos."""
    candidatos = documentos
    if documento:
        doc_id = documento if documento in documentos else (alias or {}).get(documento)
        if doc_id is None:
            raise ValueError(f"documento desconocido: {documento!r}")
        candidatos = {doc_id: documentos[doc_id]}
    encontrados = [(doc_id, ini, fin) for doc_id, texto in candidatos.items()
                   for ini, fin in _ocurrencias(respuesta, texto)]
    if not encontrados:
        raise ValueError(f"la respuesta no aparece en los documentos: {respuesta!r}")
    avisos = []
    if len(encontrados) > 1 and not documento:
        docs = sorted({d for d, _, _ in encontrados})
        avisos.append(f"la respuesta aparece {len(encontrados)} veces ({', '.join(docs)}); se usa la primera. "
                      "Indica la columna 'documento' para elegir")
    doc_id, ini, fin = encontrados[0]
    return Ubicacion(doc_id, ini, fin, documentos[doc_id][ini:fin]), avisos


def oracion_de(texto: str, inicio: int, fin: int) -> tuple[int, int]:
    """Oraciones de la línea de ``texto`` que cubren ``[inicio, fin)``.

    Se corta primero por línea: un título («Garantía») no es parte de la
    oración siguiente.
    """
    from rag.lenguaje.texto import dividir_oraciones

    linea_ini = texto.rfind("\n", 0, inicio) + 1
    salto = texto.find("\n", fin)
    linea_fin = len(texto) if salto == -1 else salto
    linea = texto[linea_ini:linea_fin]
    rangos = [(a + linea_ini, b + linea_ini) for a, b in dividir_oraciones(linea)
              if a + linea_ini < fin and b + linea_ini > inicio]
    if not rangos:
        return inicio, fin
    return min(inicio, rangos[0][0]), max(fin, rangos[-1][1])


# ---------------------------------------------------------------------------
# Separación y conversión al banco
# ---------------------------------------------------------------------------
def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def asignar_ids(filas: list[FilaGolden]) -> list[str]:
    """Valida los ``id`` dados y genera los faltantes (``tipo_<hash>``)."""
    errores = []
    for fila in filas:
        if fila.id is None:
            fila.id = f"{fila.tipo or 'fila'}_{_hash(fila.pregunta)[:8]}"
        elif not _RE_ID.match(fila.id):
            errores.append(f"{fila.origen}: id {fila.id!r} inválido (minúsculas, dígitos, '_' o '-')")
    vistos: dict[str, str] = {}
    for fila in filas:
        if fila.id in vistos:
            errores.append(f"{fila.origen}: id {fila.id!r} repetido (también en {vistos[fila.id]})")
        vistos.setdefault(fila.id, fila.origen)
    return errores


def separar_dev_test(filas: list[FilaGolden]) -> dict[str, str]:
    """``id → split``: 50/50 estratificado por tipo, determinista por hash del id.

    Dentro de cada tipo se ordena por hash y se alterna dev/test: reimportar el
    mismo archivo da la misma separación.
    """
    split: dict[str, str] = {}
    for tipo in TIPOS:
        grupo = sorted((f.id for f in filas if f.tipo == tipo), key=_hash)
        for i, id_ in enumerate(grupo):
            split[id_] = "dev" if i % 2 == 0 else "test"
    return split


def avisos_de_tamano(filas: list[FilaGolden], minimo: int = MINIMO_FILAS) -> tuple[list[str], list[str]]:
    """Errores (menos de ``minimo`` filas) y avisos de balance y de certificación."""
    errores, avisos = [], []
    if len(filas) < minimo:
        errores.append(f"el golden tiene {len(filas)} filas; hacen falta al menos {minimo}")
    sin = sum(f.tipo in {"sin_respuesta", "premisa_falsa"} for f in filas)
    if filas and sin / len(filas) < PROPORCION_MINIMA_SIN_RESPUESTA:
        avisos.append(f"solo {sin} de {len(filas)} filas son sin_respuesta o premisa_falsa "
                      f"(menos de {PROPORCION_MINIMA_SIN_RESPUESTA:.0%}): no se puede medir bien el riesgo de falsos ok")
    if not any(f.subtipo == "trampa_mismo_tema" for f in filas):
        avisos.append("no hay filas 'trampa_mismo_tema': agrega preguntas sin respuesta sobre los mismos temas "
                      "que las respondibles (p. ej. «¿Qué incluye la garantía?» junto a «¿Cuándo vence?»)")
    respondibles_test = sum(f.tipo == "respondible" for f in filas) // 2
    if respondibles_test < ACEPTADAS_PARA_CERTIFICAR:
        avisos.append(f"sirve para ajuste práctico, no para certificar: con 0 errores hacen falta al menos "
                      f"{ACEPTADAS_PARA_CERTIFICAR} respuestas aceptadas en test para afirmar α=0,05 al 95% "
                      f"(hay ~{respondibles_test} respondibles en test)")
    return errores, avisos


def _validar_fila(fila: FilaGolden, ids_respondibles: set[str]) -> list[str]:
    errores = []
    if fila.tipo not in TIPOS:
        errores.append(f"{fila.origen}: tipo {fila.tipo!r} inválido; usa {', '.join(TIPOS)}")
    if fila.tipo == "respondible" and not fila.respuesta_literal:
        errores.append(f"{fila.origen}: una fila respondible necesita respuesta_literal copiada del documento")
    if fila.tipo != "respondible" and fila.respuesta_literal:
        errores.append(f"{fila.origen}: solo las filas respondibles llevan respuesta_literal")
    if fila.subtipo is not None:
        if fila.subtipo not in SUBTIPOS:
            errores.append(f"{fila.origen}: subtipo {fila.subtipo!r} inválido; usa {', '.join(SUBTIPOS)}")
        elif fila.tipo not in {"sin_respuesta", "premisa_falsa"}:
            errores.append(f"{fila.origen}: 'trampa_mismo_tema' solo aplica a sin_respuesta o premisa_falsa")
    if fila.par is not None and fila.par not in ids_respondibles:
        errores.append(f"{fila.origen}: par {fila.par!r} no es el id de una fila respondible")
    return errores


def a_banco(
    filas: list[FilaGolden],
    documentos: dict[str, str],
    corpus: CorpusBanco,
    *,
    estadisticas,
    paquete=None,
    alias: dict[str, str] | None = None,
    dataset_id: str = "golden",
    dataset_version: str = "1.0.0",
    minimo: int = MINIMO_FILAS,
) -> ResultadoImportacion:
    """Convierte las filas en un banco versionado. Junta todos los errores
    antes de fallar, para que el cliente corrija el archivo de una vez."""
    from rag.lenguaje.lexico import s_cov, terminos_pregunta
    from rag.lenguaje.texto import terminos

    errores = asignar_ids(filas)
    errores_tamano, avisos = avisos_de_tamano(filas, minimo)
    errores += errores_tamano
    ids_respondibles = {f.id for f in filas if f.tipo == "respondible"}
    for fila in filas:
        errores += _validar_fila(fila, ids_respondibles)
    if errores:
        raise ErrorGolden(errores)

    split = separar_dev_test(filas)
    casos = []
    for fila in filas:
        comunes = dict(schema_version=1, dataset_version=dataset_version, id=fila.id, split=split[fila.id],
                       pregunta=fila.pregunta, notas=fila.notas, subtipo=fila.subtipo, par=fila.par)
        if fila.tipo == "respondible":
            try:
                ubicacion, avisos_fila = ubicar_respuesta(fila.respuesta_literal, documentos, fila.documento, alias)
            except ValueError as e:
                errores.append(f"{fila.origen}: {e}")
                continue
            avisos += [f"{fila.origen}: {a}" for a in avisos_fila]
            texto = documentos[ubicacion.doc_id]
            ini, fin = oracion_de(texto, ubicacion.inicio, ubicacion.fin)
            evidencia = EvidenciaEsperada(doc_id=ubicacion.doc_id, offset_inicio=ini, offset_fin=fin,
                                          texto=texto[ini:fin])
            cobertura = s_cov(terminos_pregunta(fila.pregunta, paquete), terminos(evidencia.texto, paquete),
                              estadisticas)
            categoria = CategoriaPregunta.EXACTA if cobertura >= UMBRAL_EXACTA else CategoriaPregunta.PARAFRASIS
            casos.append(CasoEvaluacion(**comunes, categoria=categoria, estado_esperado="respuesta_directa",
                                        respondible=True, respuesta_literal=ubicacion.texto,
                                        evidencias=[evidencia]))
        else:
            categoria, estado = _CATEGORIA_Y_ESTADO[fila.tipo]
            casos.append(CasoEvaluacion(**comunes, categoria=categoria, estado_esperado=estado, respondible=False))
    if errores:
        raise ErrorGolden(errores)

    manifiesto = ManifiestoBanco(
        dataset_id=dataset_id, dataset_version=dataset_version, tipo="manual",
        estado="estable" if {c.split for c in casos} == {"dev", "test"} else "borrador",
        casos="golden.jsonl", corpus=corpus,
        categorias_requeridas=sorted({c.categoria for c in casos}, key=lambda c: c.value),
    )
    return ResultadoImportacion(BancoEvaluacion(manifiesto=manifiesto, casos=casos), avisos)


__all__ = [
    "ACEPTADAS_PARA_CERTIFICAR", "COLUMNAS", "ErrorGolden", "FilaGolden", "MINIMO_FILAS", "ResultadoImportacion",
    "SUBTIPOS", "TIPOS", "Ubicacion", "a_banco", "asignar_ids", "avisos_de_tamano", "leer_csv", "leer_golden",
    "leer_jsonl", "leer_squad2", "oracion_de", "separar_dev_test", "ubicar_respuesta",
]
