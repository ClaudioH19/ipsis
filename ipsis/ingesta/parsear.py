"""Parser determinista de documentos a texto plano + estructura + offsets,
con despacho por extensión.

Produce, para cada documento, sea cual sea su formato de origen:
  - ``texto_completo``: concatenación de todos los bloques de contenido, en el
    orden real del documento.
  - una lista de :class:`Bloque`, cada uno con su ``seccion_path`` (pila de
    encabezados vigente en ese punto del documento), su rango de offsets
    ``[offset_inicio, offset_fin)`` dentro de ``texto_completo`` y su
    ``tipo_contenido`` (``narrativo``, ``tabla`` o ``titulo``).

Esta separación permite que ``chunking.py`` agrupe bloques en chunks sin volver
a tocar el archivo de origen, y que toda evidencia del golden set se ancle a
offsets de caracteres estables mientras el parser no cambie -- **la propiedad
de la que depende todo el sistema de citas**, verificada con ``assert`` en cada
parser y con tests adversariales por formato (``tests/ingesta/test_parsear_docx.py``).

Formatos soportados y punto de entrada único: :func:`parsear_documento`,
que despacha por extensión a uno de los cuatro parsers de abajo. Ningún otro
módulo del proyecto debe importar un parser específico salvo para pruebas: el
resto del pipeline (``chunking.py``, ``metadata.py``, ``corpus.py``) solo
conoce :class:`DocumentoParseado`, nunca el formato de origen.

  - **``.docx``**: :func:`parsear_docx` (sin cambios respecto de las etapas
    anteriores). Secciones desde los estilos Heading 1/2/3 de Word.
  - **``.pdf`` con capa de texto**: :func:`parsear_pdf`, con ``pypdf``
    (licencia BSD-3-Clause, permisiva -- **deliberadamente NO se usa
    PyMuPDF**, que es AGPL y obligaría a liberar bajo esa misma licencia a
    quien distribuya este plugin). Secciones desde los marcadores/outline del
    PDF si existen; si no, se indexa sin secciones y se advierte (ver docstring
    de ``parsear_pdf`` para por qué no se implementó además una heurística por
    tamaño de letra en esta tanda).
  - **``.pdf`` escaneado**: se detecta porque la extracción de texto devuelve
    casi nada por página -- se RECHAZA con :class:`DocumentoEscaneadoError`
    (nunca se indexa un documento vacío en silencio).
  - **``.md`` / ``.markdown``**: :func:`parsear_markdown`. Los ``#`` dan el
    ``seccion_path`` directamente.
  - **``.txt``**: :func:`parsear_texto_plano`. Párrafos separados por líneas
    en blanco, sin secciones, con advertencia.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from ipsis.recursos.mensajes import t

SEPARADOR_BLOQUE = "\n"

# Formatos que reconoce el despacho de `parsear_documento`.
EXTENSIONES_SOPORTADAS = {".docx", ".pdf", ".md", ".markdown", ".txt"}


class DocumentoEscaneadoError(ValueError):
    """Un PDF sin capa de texto (escaneado): la extracción devolvió casi nada
    de texto por página. El OCR NO está soportado por este proyecto (offline,
    sin dependencias pesadas nuevas) -- se rechaza el documento explícitamente
    en vez de indexarlo vacío en silencio."""


@dataclass
class Bloque:
    indice: int
    seccion_path: list[str]
    seccion_nivel: int
    tipo_contenido: str  # "narrativo" | "tabla" | "titulo"
    texto: str
    offset_inicio: int
    offset_fin: int


@dataclass
class DocumentoParseado:
    doc_id: str
    doc_titulo: str
    version: str
    ruta_origen: str
    texto_completo: str
    bloques: list[Bloque] = field(default_factory=list)
    hash_documento: str = ""
    # Advertencias accionables de la ingesta: p.ej.
    # "este documento no tiene estructura de secciones" -- degrada los
    # filtros por seccion_path pero no impide indexar. `ipsis index` las
    # junta e imprime al final (ver ipsis/ingesta/ingesta.py::ejecutar_ingesta).
    advertencias: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.hash_documento:
            self.hash_documento = hashlib.sha256(self.texto_completo.encode("utf-8")).hexdigest()


HEADING_NIVEL = {
    "Heading 1": 1,
    "Heading 2": 2,
    "Heading 3": 3,
    "Title": 0,
}


def _fila_a_texto(row) -> str:
    # colapsa celdas repetidas por merge de word (misma celda física varias veces)
    celdas_unicas: list[str] = []
    vistas: set[int] = set()
    for c in row.cells:
        cid = id(c._tc)
        if cid in vistas:
            continue
        vistas.add(cid)
        celdas_unicas.append(c.text.strip().replace("\n", " "))
    return " | ".join(x for x in celdas_unicas if x)


def _iter_bloques_crudos(document: docx.document.Document):
    """Itera párrafos y tablas en el orden real del documento."""
    parent_elm = document.element.body
    for child in parent_elm.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def parsear_docx(ruta: str, doc_id: str, doc_titulo: str, version: str) -> DocumentoParseado:
    """Parsea un .docx real a :class:`DocumentoParseado` con offsets exactos."""
    document = docx.Document(ruta)

    bloques: list[Bloque] = []
    texto_partes: list[str] = []
    offset_actual = 0
    pila_secciones: list[tuple[int, str]] = []  # (nivel, titulo)
    indice = 0
    tabla_contador = 0

    for elemento in _iter_bloques_crudos(document):
        if isinstance(elemento, Paragraph):
            texto = elemento.text.strip()
            if not texto:
                continue
            estilo = elemento.style.name if elemento.style else "Normal"
            nivel_heading = HEADING_NIVEL.get(estilo)

            if nivel_heading is not None:
                # actualiza la pila: descarta niveles >= al actual, agrega el nuevo
                pila_secciones = [(n, t) for (n, t) in pila_secciones if n < nivel_heading]
                pila_secciones.append((nivel_heading, texto))
                tipo_contenido = "titulo"
                seccion_path_bloque = [t for (_, t) in pila_secciones]
                seccion_nivel = nivel_heading
            else:
                tipo_contenido = "narrativo"
                seccion_path_bloque = [t for (_, t) in pila_secciones]
                seccion_nivel = pila_secciones[-1][0] if pila_secciones else 0

            inicio = offset_actual
            texto_partes.append(texto)
            offset_actual += len(texto)
            fin = offset_actual
            texto_partes.append(SEPARADOR_BLOQUE)
            offset_actual += len(SEPARADOR_BLOQUE)

            bloques.append(Bloque(
                indice=indice, seccion_path=seccion_path_bloque, seccion_nivel=seccion_nivel,
                tipo_contenido=tipo_contenido, texto=texto, offset_inicio=inicio, offset_fin=fin,
            ))
            indice += 1

        elif isinstance(elemento, Table):
            tabla_contador += 1
            seccion_path_bloque = [t for (_, t) in pila_secciones] + [f"Tabla {tabla_contador}"]
            seccion_nivel = (pila_secciones[-1][0] if pila_secciones else 0) + 1
            for row in elemento.rows:
                texto_fila = _fila_a_texto(row)
                if not texto_fila:
                    continue
                inicio = offset_actual
                texto_partes.append(texto_fila)
                offset_actual += len(texto_fila)
                fin = offset_actual
                texto_partes.append(SEPARADOR_BLOQUE)
                offset_actual += len(SEPARADOR_BLOQUE)

                bloques.append(Bloque(
                    indice=indice, seccion_path=seccion_path_bloque, seccion_nivel=seccion_nivel,
                    tipo_contenido="tabla", texto=texto_fila, offset_inicio=inicio, offset_fin=fin,
                ))
                indice += 1

    texto_completo = "".join(texto_partes)

    # Verificación de la invariante central del parser: cada bloque debe
    # reconstruirse leyendo el rango de offsets correspondiente en texto_completo.
    for b in bloques:
        extraido = texto_completo[b.offset_inicio:b.offset_fin]
        assert extraido == b.texto, (
            f"Offset desalineado en bloque {b.indice}: esperado {b.texto!r}, "
            f"encontrado {extraido!r}"
        )

    return DocumentoParseado(
        doc_id=doc_id, doc_titulo=doc_titulo, version=version, ruta_origen=ruta,
        texto_completo=texto_completo, bloques=bloques,
    )


# ---------------------------------------------------------------------------
# Motor compartido para los formatos nuevos: Markdown,
# texto plano y PDF (para el texto que no viene organizado en tablas) arman
# su documento como una secuencia de "eventos" -- (texto, nivel_heading) con
# nivel_heading=None para contenido narrativo -- y este motor les da la misma
# pila de secciones y la misma invariante de offsets que ya usa `parsear_docx`
# para párrafos. No reemplaza la lógica de `.docx` (que además maneja tablas,
# con su propio recorrido del árbol XML): es la pieza NUEVA que evita
# reimplementar la construcción de bloques/offsets tres veces (Markdown, txt,
# PDF), que es justamente la duplicación que este proyecto evita a propósito.
# ---------------------------------------------------------------------------

def _ensamblar_bloques(eventos: list[tuple[str, int | None]]) -> tuple[str, list[Bloque]]:
    """``eventos``: lista de ``(texto, nivel_heading)``. ``nivel_heading`` no
    ``None`` marca un título que actualiza la pila de secciones (mismo
    criterio que los estilos Heading de Word: descarta niveles >= al actual y
    agrega el nuevo); ``None`` es contenido narrativo bajo la sección
    vigente. Devuelve ``(texto_completo, bloques)`` con la misma invariante de
    offsets reconstructivos que :func:`parsear_docx`."""
    bloques: list[Bloque] = []
    texto_partes: list[str] = []
    offset_actual = 0
    pila_secciones: list[tuple[int, str]] = []
    indice = 0

    for texto, nivel_heading in eventos:
        texto = texto.strip()
        if not texto:
            continue

        if nivel_heading is not None:
            pila_secciones = [(n, t) for (n, t) in pila_secciones if n < nivel_heading]
            pila_secciones.append((nivel_heading, texto))
            tipo_contenido = "titulo"
            seccion_path_bloque = [t for (_, t) in pila_secciones]
            seccion_nivel = nivel_heading
        else:
            tipo_contenido = "narrativo"
            seccion_path_bloque = [t for (_, t) in pila_secciones]
            seccion_nivel = pila_secciones[-1][0] if pila_secciones else 0

        inicio = offset_actual
        texto_partes.append(texto)
        offset_actual += len(texto)
        fin = offset_actual
        texto_partes.append(SEPARADOR_BLOQUE)
        offset_actual += len(SEPARADOR_BLOQUE)

        bloques.append(Bloque(
            indice=indice, seccion_path=seccion_path_bloque, seccion_nivel=seccion_nivel,
            tipo_contenido=tipo_contenido, texto=texto, offset_inicio=inicio, offset_fin=fin,
        ))
        indice += 1

    texto_completo = "".join(texto_partes)
    for b in bloques:
        extraido = texto_completo[b.offset_inicio:b.offset_fin]
        assert extraido == b.texto, (
            f"Offset desalineado en bloque {b.indice}: esperado {b.texto!r}, encontrado {extraido!r}"
        )
    return texto_completo, bloques


def _leer_texto_archivo(ruta: str) -> str:
    """Lee un archivo de texto en UTF-8; si trae BOM o no es UTF-8 estricto
    (documentos exportados desde otros editores), cae a `latin-1` en vez de
    fallar -- nunca se inventa contenido, solo se tolera la codificación."""
    datos = Path(ruta).read_bytes()
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return datos.decode("latin-1")


# ---------------------------------------------------------------------------
# Markdown: los `#` dan el seccion_path directamente.
# ---------------------------------------------------------------------------
_RE_HEADING_MD = re.compile(r"^(#{1,6})\s+(.*)$")


def parsear_markdown(ruta: str, doc_id: str, doc_titulo: str, version: str) -> DocumentoParseado:
    """Parsea un ``.md``/``.markdown``: cada línea ``#..######`` es un título
    de nivel 1-6 que actualiza ``seccion_path``; los párrafos (líneas no vacías
    consecutivas, sin encabezado) son contenido narrativo. Igual que en
    ``.docx``, un documento sin ningún encabezado queda sin ``seccion_path``
    -- se advierte, porque degrada los filtros deterministas por sección."""
    texto = _leer_texto_archivo(ruta)
    lineas = texto.split("\n")

    eventos: list[tuple[str, int | None]] = []
    parrafo_actual: list[str] = []
    hay_encabezados = False

    def _cerrar_parrafo():
        if parrafo_actual:
            eventos.append((" ".join(parrafo_actual), None))
            parrafo_actual.clear()

    for linea in lineas:
        m = _RE_HEADING_MD.match(linea.strip())
        if m:
            _cerrar_parrafo()
            nivel = len(m.group(1))
            eventos.append((m.group(2).strip(), nivel))
            hay_encabezados = True
        elif linea.strip():
            parrafo_actual.append(linea.strip())
        else:
            _cerrar_parrafo()
    _cerrar_parrafo()

    texto_completo, bloques = _ensamblar_bloques(eventos)
    advertencias = []
    if not hay_encabezados:
        advertencias.append(t("core.no_headings"))
    return DocumentoParseado(
        doc_id=doc_id, doc_titulo=doc_titulo, version=version, ruta_origen=ruta,
        texto_completo=texto_completo, bloques=bloques, advertencias=advertencias,
    )


# ---------------------------------------------------------------------------
# Texto plano: párrafos separados por líneas en blanco, sin secciones.
# ---------------------------------------------------------------------------

def parsear_texto_plano(ruta: str, doc_id: str, doc_titulo: str, version: str) -> DocumentoParseado:
    """Parsea un ``.txt``: párrafos separados por una o más líneas en blanco.
    Nunca hay ``seccion_path`` (el formato no declara ninguna estructura) --
    se advierte siempre, a diferencia de Markdown/PDF donde la ausencia de
    encabezados es la excepción."""
    texto = _leer_texto_archivo(ruta)
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    eventos: list[tuple[str, int | None]] = [(p.replace("\n", " "), None) for p in parrafos]

    texto_completo, bloques = _ensamblar_bloques(eventos)
    advertencias = [
        "el texto plano no declara estructura de secciones: todo el documento "
        "queda sin seccion_path, lo que degrada los filtros deterministas."
    ]
    return DocumentoParseado(
        doc_id=doc_id, doc_titulo=doc_titulo, version=version, ruta_origen=ruta,
        texto_completo=texto_completo, bloques=bloques, advertencias=advertencias,
    )


# ---------------------------------------------------------------------------
# PDF con capa de texto: `pypdf` (BSD-3-Clause, licencia permisiva).
#
# Decisión de licencia: se descartó
# PyMuPDF a propósito -- es AGPL-3.0, lo que obligaría a liberar bajo esa
# misma licencia (copyleft fuerte) a cualquiera que distribuya este plugin
# como parte de un producto propio. `pypdf` (antes PyPDF2) es BSD-3-Clause,
# compatible con un plugin que alguien más empaquete y distribuya sin heredar
# una licencia. `pdfplumber` (la otra opción considerada) es
# también viable (MIT) pero depende de `pdfminer.six` con una superficie más
# grande; `pypdf` ya estaba disponible en este entorno (verificado antes de
# elegir, no asumido) y es más liviano.
# ---------------------------------------------------------------------------

# Umbral heurístico (no una métrica medida: un parámetro del algoritmo de
# detección, igual en naturaleza a `largo_min` de ipsis/lenguaje/texto.py) para
# distinguir un PDF con capa de texto real de uno escaneado: si el promedio
# de caracteres extraídos por página cae por debajo de esto, se asume que no
# hay texto extraíble (imagen sin OCR) y se rechaza en vez de indexar vacío.
UMBRAL_PDF_ESCANEADO_CHARS_POR_PAGINA = 20


def _mapear_outline_a_paginas(reader) -> dict[int, list[tuple[int, str]]]:
    """Traduce el outline/marcadores del PDF (si existen) a
    ``{indice_pagina: [(nivel, titulo), ...]}``, en el orden en que aparecen
    en el outline. Devuelve ``{}`` si el PDF no tiene outline o si es
    ilegible (algunos PDF traen un outline corrupto; se degrada a "sin
    secciones" en vez de fallar la ingesta completa por eso)."""
    try:
        outline = reader.outline
    except Exception:
        return {}
    if not outline:
        return {}

    resultado: dict[int, list[tuple[int, str]]] = {}

    def _recorrer(nodos, nivel: int) -> None:
        for nodo in nodos:
            if isinstance(nodo, list):
                _recorrer(nodo, nivel + 1)
                continue
            try:
                pagina = reader.get_destination_page_number(nodo)
                titulo = (nodo.title or "").strip()
            except Exception:
                continue
            if titulo:
                resultado.setdefault(pagina, []).append((nivel, titulo))

    try:
        _recorrer(outline, 1)
    except Exception:
        return {}
    return resultado


def parsear_pdf(ruta: str, doc_id: str, doc_titulo: str, version: str) -> DocumentoParseado:
    """Parsea un ``.pdf`` con capa de texto real. Secciones desde el
    outline/marcadores del PDF si existen (:func:`_mapear_outline_a_paginas`);
    si no, se indexa sin ``seccion_path`` y se advierte -- se acepta
    esto como "peor caso" ("heurística por tamaño de letra; en el peor caso,
    indexar sin secciones y advertir"). **Decisión de alcance de esta tanda**:
    no se implementó además la heurística intermedia por tamaño de letra
    (requiere leer el tamaño de fuente de cada fragmento de texto vía
    ``visitor_text`` de pypdf y agrupar líneas en encabezados por umbral, una
    pieza bastante más grande que el resto de este módulo) -- queda como
    mejora futura; por ahora se informa explícitamente la falta de estructura
    si aparece un PDF real sin outline que la necesite.

    Rechaza con :class:`DocumentoEscaneadoError` si la extracción de texto
    devuelve casi nada (PDF escaneado, sin capa de texto) -- nunca indexa un
    documento vacío en silencio."""
    import pypdf

    reader = pypdf.PdfReader(ruta)
    n_paginas = len(reader.pages)
    if n_paginas == 0:
        raise DocumentoEscaneadoError(t("core.pdf_no_pages", path=ruta))

    textos_paginas = [(pagina.extract_text() or "") for pagina in reader.pages]
    total_chars = sum(len(t.strip()) for t in textos_paginas)
    promedio = total_chars / n_paginas
    if promedio < UMBRAL_PDF_ESCANEADO_CHARS_POR_PAGINA:
        raise DocumentoEscaneadoError(t("core.pdf_scanned", path=ruta, average=promedio,
                                        threshold=UMBRAL_PDF_ESCANEADO_CHARS_POR_PAGINA, pages=n_paginas))

    encabezados_por_pagina = _mapear_outline_a_paginas(reader)
    advertencias = []
    if not encabezados_por_pagina:
        advertencias.append(t("core.pdf_no_outline"))

    eventos: list[tuple[str, int | None]] = []
    for i, texto_pagina in enumerate(textos_paginas):
        for nivel, titulo in encabezados_por_pagina.get(i, []):
            eventos.append((titulo, nivel))
        parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto_pagina) if p.strip()]
        if not parrafos and texto_pagina.strip():
            # el PDF no trae líneas en blanco entre párrafos (común en
            # extracción de PDF): toda la página queda como un solo bloque.
            parrafos = [texto_pagina.strip()]
        for p in parrafos:
            eventos.append((" ".join(p.split()), None))

    texto_completo, bloques = _ensamblar_bloques(eventos)
    return DocumentoParseado(
        doc_id=doc_id, doc_titulo=doc_titulo, version=version, ruta_origen=ruta,
        texto_completo=texto_completo, bloques=bloques, advertencias=advertencias,
    )


# ---------------------------------------------------------------------------
# Despacho por extensión: punto de entrada único que
# el resto del proyecto (ipsis/ingesta/ingesta.py::parsear_corpus, la CLI) debe usar en
# vez de llamar a un parser de formato concreto.
# ---------------------------------------------------------------------------

def parsear_documento(ruta: str, doc_id: str, doc_titulo: str, version: str) -> DocumentoParseado:
    """Despacha al parser correspondiente según la extensión de ``ruta``.
    Lanza ``ValueError`` con la lista de formatos soportados si la extensión
    no se reconoce -- nunca intenta adivinar el formato por contenido."""
    ext = Path(ruta).suffix.lower()
    if ext == ".docx":
        return parsear_docx(ruta, doc_id, doc_titulo, version)
    if ext == ".pdf":
        return parsear_pdf(ruta, doc_id, doc_titulo, version)
    if ext in (".md", ".markdown"):
        return parsear_markdown(ruta, doc_id, doc_titulo, version)
    if ext == ".txt":
        return parsear_texto_plano(ruta, doc_id, doc_titulo, version)
    raise ValueError(t("core.unsupported_format", extension=ext, path=ruta, supported=sorted(EXTENSIONES_SOPORTADAS)))


if __name__ == "__main__":
    import sys
    doc = parsear_docx(sys.argv[1], doc_id="doc", doc_titulo="doc", version="1")
    print(f"Bloques: {len(doc.bloques)}, caracteres: {len(doc.texto_completo)}")
    for b in doc.bloques[:15]:
        print(b.seccion_path, "->", b.texto[:60])
