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


def _validar_fila(fila: FilaGolden, ids_respondibles: set[str], ids: set[str]) -> list[str]:
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
    if fila.par is not None and fila.par in ids and fila.par not in ids_respondibles:
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
    ids = {f.id for f in filas}
    for fila in filas:
        errores += _validar_fila(fila, ids_respondibles, ids)
        if fila.par is not None and fila.par not in ids:
            avisos.append(f"{fila.origen}: su par {fila.par!r} quedó sin completar; se mide sin par")
            fila.par = None
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


# ---------------------------------------------------------------------------
# Plantilla para el cliente (``rag golden plantilla``)
# ---------------------------------------------------------------------------
PROPORCION_TRAMPAS = 0.35
LARGO_MAXIMO_SECCION = 1200
LARGO_MINIMO_SECCION = 40
LARGO_FRAGMENTO = 240
TERMINOS_CLAVE = 5


@dataclass(frozen=True)
class Seccion:
    doc_id: str
    titulo: str  # ruta de sección («Garantía > Exclusiones»), puede ser vacía
    texto: str


@dataclass
class Plantilla:
    filas: list[dict]
    leeme: str
    avisos: list[str] = field(default_factory=list)


def secciones_de(documento) -> list[Seccion]:
    """Bloques consecutivos con la misma ruta de sección; las secciones largas
    se parten por bloques para que cada fila apunte a un fragmento abarcable."""
    secciones: list[Seccion] = []
    actual: list[str] = []
    ruta: list[str] | None = None

    def cerrar():
        texto = "\n".join(actual).strip()
        if len(texto) >= LARGO_MINIMO_SECCION:
            secciones.append(Seccion(documento.doc_id, " > ".join(ruta or []), texto))
        actual.clear()

    for bloque in documento.bloques:
        if bloque.tipo_contenido == "titulo":
            continue
        if bloque.seccion_path != ruta or sum(map(len, actual)) + len(bloque.texto) > LARGO_MAXIMO_SECCION:
            cerrar()
            ruta = bloque.seccion_path
        actual.append(bloque.texto)
    cerrar()
    return secciones


def _fragmento(texto: str) -> str:
    plano = _RE_ESPACIOS.sub(" ", texto).strip()
    if len(plano) <= LARGO_FRAGMENTO:
        return plano
    return plano[:LARGO_FRAGMENTO].rsplit(" ", 1)[0] + " …"


def _terminos_clave(texto: str, est, paquete) -> list[str]:
    from rag.lenguaje.lexico import terminos_pregunta, tfidf_vector

    vector = tfidf_vector(terminos_pregunta(texto, paquete), est)
    # Las cifras sueltas no dicen de qué trata la sección.
    candidatos = [t for t in vector if any(c.isalpha() for c in t)]
    mejores = sorted(candidatos, key=lambda t: (-vector[t], t))[:TERMINOS_CLAVE]
    superficie = getattr(est, "superficie", {}) or {}
    return [superficie.get(t, t) for t in mejores]


def elegir_secciones(secciones: list[Seccion], k: int, est, paquete) -> list[int]:
    """``k`` secciones diversas (MMR sobre TF-IDF) que cubren todos los documentos.

    Se ordena todo el corpus por MMR; primero entra la mejor sección de cada
    documento (en ese orden) y luego el resto, siguiendo el orden de MMR.
    """
    from rag.lenguaje.lexico import mmr, terminos_pregunta, tfidf_vector

    vectores = [tfidf_vector(terminos_pregunta(s.texto, paquete), est) for s in secciones]
    orden = mmr(vectores, k=len(vectores))
    elegidos: list[int] = []
    for doc_id in dict.fromkeys(secciones[i].doc_id for i in orden):
        elegidos.append(next(i for i in orden if secciones[i].doc_id == doc_id))
    elegidos += [i for i in orden if i not in elegidos]
    return sorted(elegidos[:k], key=orden.index)


def generar_plantilla(corpus, paquete, n: int = 40) -> Plantilla:
    """Filas de ``golden.csv`` para que el cliente complete.

    ~35% son trampas «mismo tema, dato ausente», cada una en par con una fila
    respondible de la misma sección; 3 son conversacionales ya completas; el
    resto son respondibles de secciones diversas. No usa modelos ni genera
    preguntas: solo elige secciones y escribe instrucciones.

    El TF-IDF se calcula sobre las secciones (no sobre los chunks del índice):
    así los términos clave distinguen una sección de las demás.
    """
    from rag.indice.estadisticas import EstadisticasLexicas

    textos = paquete.golden_instrucciones if paquete is not None else None
    if textos is None:
        from rag.lenguaje.paquete import cargar_paquete

        textos = cargar_paquete("en").golden_instrucciones
    secciones = [s for documento in corpus for s in secciones_de(documento)]
    if not secciones:
        raise ErrorGolden(["no hay texto indexable en los documentos: carga documentos antes de generar la plantilla"])
    est = EstadisticasLexicas.construir([s.texto for s in secciones], paquete)
    avisos: list[str] = []
    n_conversacionales = len(textos.conversacionales)
    n_trampas = round(n * PROPORCION_TRAMPAS)
    n_respondibles = n - n_conversacionales - n_trampas
    if len(secciones) < n_respondibles:
        avisos.append(f"el corpus tiene {len(secciones)} secciones: se generan menos filas que las {n} pedidas")
        n_respondibles = len(secciones)
        # ~35% del total, contando las conversacionales; nunca más trampas que pares.
        n_trampas = min(n_respondibles, round((n_respondibles + n_conversacionales) * PROPORCION_TRAMPAS
                                              / (1 - PROPORCION_TRAMPAS)))
    elegidas = elegir_secciones(secciones, n_respondibles, est, paquete)
    documentos = {d.doc_id for d in corpus}
    cubiertos = {secciones[i].doc_id for i in elegidas}
    if documentos - cubiertos:
        avisos.append(f"sin filas para: {', '.join(sorted(documentos - cubiertos))} (n demasiado chico)")

    filas: list[dict] = []
    for numero, i in enumerate(elegidas, start=1):
        seccion = secciones[i]
        clave = ", ".join(_terminos_clave(seccion.texto, est, paquete))
        comunes = {"documento": seccion.doc_id, "fragmento_sugerido": _fragmento(seccion.texto),
                   "terminos_clave": clave}
        id_respondible = f"r{numero:03d}"
        filas.append({"id": id_respondible, "tipo": "respondible", **comunes,
                      "notas": textos.nota_respondible.format(documento=seccion.doc_id, terminos=clave,
                                                              par=id_respondible)})
        if numero <= n_trampas:
            filas.append({"id": f"t{numero:03d}", "tipo": "sin_respuesta", "subtipo": "trampa_mismo_tema",
                          "par": id_respondible, **comunes,
                          "notas": textos.nota_trampa.format(documento=seccion.doc_id, terminos=clave,
                                                             par=id_respondible)})
    for numero, pregunta in enumerate(textos.conversacionales, start=1):
        filas.append({"id": f"c{numero:03d}", "pregunta": pregunta, "tipo": "conversacional"})
    return Plantilla([{c: fila.get(c, "") for c in COLUMNAS} for fila in filas], textos.leeme, avisos)


def escribir_plantilla(plantilla: Plantilla, carpeta: str | Path) -> tuple[Path, Path]:
    """Escribe ``golden.csv`` (UTF-8 con BOM, para que Excel respete las tildes)
    y ``LEEME.txt`` en ``carpeta``."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_csv, ruta_leeme = carpeta / "golden.csv", carpeta / "LEEME.txt"
    with ruta_csv.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(plantilla.filas)
    ruta_leeme.write_text(plantilla.leeme, encoding="utf-8")
    return ruta_csv, ruta_leeme


__all__ = [
    "ACEPTADAS_PARA_CERTIFICAR", "COLUMNAS", "ErrorGolden", "FilaGolden", "MINIMO_FILAS", "ResultadoImportacion",
    "SUBTIPOS", "TIPOS", "Ubicacion", "a_banco", "asignar_ids", "avisos_de_tamano", "leer_csv", "leer_golden",
    "leer_jsonl", "leer_squad2", "oracion_de", "separar_dev_test", "ubicar_respuesta",
    "Plantilla", "Seccion", "elegir_secciones", "escribir_plantilla", "generar_plantilla", "secciones_de",
]
