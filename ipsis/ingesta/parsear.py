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
    tipo_contenido: str  # "narrativo" | "lista" | "tabla" | "titulo"
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
    # Solo la preparación opt-in llena esta representación versionada.
    estructura: dict | None = None

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
                tipo_contenido = "lista" if estilo.startswith("List") else "narrativo"
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
            encabezado_tabla = None
            for row in elemento.rows:
                texto_fila = _fila_a_texto(row)
                if not texto_fila:
                    continue
                # Desde la segunda fila, el encabezado de la tabla es el último nivel de la sección.
                ruta_fila = seccion_path_bloque + [encabezado_tabla] if encabezado_tabla else seccion_path_bloque
                if encabezado_tabla is None:
                    encabezado_tabla = texto_fila
                inicio = offset_actual
                texto_partes.append(texto_fila)
                offset_actual += len(texto_fila)
                fin = offset_actual
                texto_partes.append(SEPARADOR_BLOQUE)
                offset_actual += len(SEPARADOR_BLOQUE)

                bloques.append(Bloque(
                    indice=indice, seccion_path=ruta_fila, seccion_nivel=seccion_nivel + (len(ruta_fila) > len(
                        seccion_path_bloque)),
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

Evento = tuple  # (texto, nivel_heading) o (texto, None, tipo_contenido)


def _ensamblar_bloques(eventos: list[Evento]) -> tuple[str, list[Bloque]]:
    """``eventos``: lista de ``(texto, nivel_heading)``. ``nivel_heading`` no
    ``None`` marca un título que actualiza la pila de secciones (mismo
    criterio que los estilos Heading de Word: descarta niveles >= al actual y
    agrega el nuevo); ``None`` es contenido bajo la sección vigente, narrativo
    salvo que el evento traiga un tercer elemento (``"lista"`` o ``"tabla"``).
    Devuelve ``(texto_completo, bloques)`` con la misma invariante de
    offsets reconstructivos que :func:`parsear_docx`."""
    bloques: list[Bloque] = []
    texto_partes: list[str] = []
    offset_actual = 0
    pila_secciones: list[tuple[int, str]] = []
    indice = 0

    for evento in eventos:
        texto, nivel_heading = evento[0].strip(), evento[1]
        tipo_evento = evento[2] if len(evento) > 2 else "narrativo"
        if not texto:
            continue

        if nivel_heading is not None:
            pila_secciones = [(n, t) for (n, t) in pila_secciones if n < nivel_heading]
            pila_secciones.append((nivel_heading, texto))
            tipo_contenido = "titulo"
            seccion_path_bloque = [t for (_, t) in pila_secciones]
            seccion_nivel = nivel_heading
        else:
            tipo_contenido = tipo_evento
            seccion_path_bloque = [t for (_, t) in pila_secciones]
            seccion_nivel = pila_secciones[-1][0] if pila_secciones else 0
            encabezado = evento[3] if len(evento) > 3 else None
            if tipo_evento == "tabla" and encabezado:
                # La fila queda bajo el encabezado de su tabla: «40%» es una «Ponderación».
                # El texto de la fila no cambia (la cita sigue literal); el encabezado llega al
                # foco y al orden de oraciones como cualquier título de sección.
                seccion_path_bloque = seccion_path_bloque + [encabezado]
                seccion_nivel += 1

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
# Estructura que el texto plano no declara pero se ve: viñetas y numeración
# (cada ítem es un bloque ``lista``, así la respuesta conserva un ítem por
# línea) y títulos sueltos. El texto de cada bloque sigue siendo el del
# documento, con su viñeta: solo cambia por dónde se corta.
# ---------------------------------------------------------------------------
_RE_ITEM = re.compile(r"^(?:[-*+\u2022\u2023\u25e6\u25aa\u2013\u2014]|\(?\d{1,3}[.)]|\(?[a-zA-Z][)])\s+\S")
_RE_FIN_DE_FRASE = re.compile(r"[.,;:!?\u2026)\]\u00bb\"']$")


def _es_item(linea: str) -> bool:
    return bool(_RE_ITEM.match(linea.strip()))


def _parece_titulo(linea: str) -> bool:
    """Una línea corta, sin puntuación final y que empieza en mayúscula o
    número: «Garantía», «3. Mantenimiento». Heurística conservadora para
    documentos que no marcan sus títulos (``.txt``, PDF sin marcadores)."""
    linea = linea.strip()
    if not linea or len(linea) > 80 or len(linea.split()) > 10 or _RE_FIN_DE_FRASE.search(linea):
        return False
    inicial = next((c for c in linea if c.isalnum()), "")
    return bool(inicial) and (inicial.isupper() or inicial.isdigit()) and any(c.isalpha() for c in linea)


def _eventos_de_lineas(lineas: list[str]) -> list[Evento]:
    """Las líneas de un párrafo: los ítems de lista por separado (con sus
    líneas de continuación) y el resto unido con espacios, como antes."""
    eventos: list[Evento] = []
    actual: list[str] = []
    tipo = "narrativo"

    def cerrar():
        if actual:
            eventos.append((" ".join(actual), None, tipo))
            actual.clear()

    for linea in (l.strip() for l in lineas):
        if not linea:
            continue
        if _es_item(linea):
            cerrar()
            tipo = "lista"
        actual.append(linea)
    cerrar()
    return eventos


# ---------------------------------------------------------------------------
# Markdown: los `#` dan el seccion_path directamente.
# ---------------------------------------------------------------------------
_RE_HEADING_MD = re.compile(r"^(#{1,6})\s+(.*)$")
_RE_SEPARADOR_TABLA_MD = re.compile(r"^\|?[\s:|-]+\|?$")


def _fila_tabla_md(linea: str) -> str | None:
    """``| a | b |`` → ``a | b`` (como las filas de ``.docx``); ``None`` si no es fila."""
    linea = linea.strip()
    if not (linea.startswith("|") and linea.endswith("|") and len(linea) > 1):
        return None
    celdas = [c.strip() for c in linea[1:-1].split("|")]
    return " | ".join(c for c in celdas if c)


def parsear_markdown(ruta: str, doc_id: str, doc_titulo: str, version: str) -> DocumentoParseado:
    """Parsea un ``.md``/``.markdown``: cada línea ``#..######`` es un título
    de nivel 1-6 que actualiza ``seccion_path``; los párrafos (líneas no vacías
    consecutivas, sin encabezado) son contenido narrativo. Igual que en
    ``.docx``, un documento sin ningún encabezado queda sin ``seccion_path``
    -- se advierte, porque degrada los filtros deterministas por sección."""
    texto = _leer_texto_archivo(ruta)
    lineas = texto.split("\n")

    eventos: list[Evento] = []
    parrafo_actual: list[str] = []
    hay_encabezados = False

    def _cerrar_parrafo():
        if parrafo_actual:
            eventos.extend(_eventos_de_lineas(parrafo_actual))
            parrafo_actual.clear()

    encabezado_tabla: str | None = None  # primera fila de la tabla en curso
    for linea in lineas:
        m = _RE_HEADING_MD.match(linea.strip())
        fila = _fila_tabla_md(linea)
        if fila is None:
            encabezado_tabla = None
        if m:
            _cerrar_parrafo()
            nivel = len(m.group(1))
            eventos.append((m.group(2).strip(), nivel))
            hay_encabezados = True
        elif fila is not None:
            _cerrar_parrafo()
            if not _RE_SEPARADOR_TABLA_MD.match(linea.strip()) and fila:
                eventos.append((fila, None, "tabla", encabezado_tabla))
                if encabezado_tabla is None:
                    encabezado_tabla = fila
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
# Texto plano: párrafos separados por líneas en blanco.
# ---------------------------------------------------------------------------

def _eventos_de_parrafos(parrafos: list[str]) -> tuple[list[Evento], bool]:
    """Párrafos sueltos (``.txt``, PDF): un párrafo de una sola línea con
    forma de título (:func:`_parece_titulo`) y seguido de contenido es un
    título de nivel 1; el resto, ítems de lista o texto unido con espacios.
    Devuelve los eventos y si encontró algún título."""
    eventos: list[Evento] = []
    hay_titulos = False
    for i, parrafo in enumerate(parrafos):
        lineas = [l for l in parrafo.split("\n") if l.strip()]
        if (len(lineas) == 1 and i + 1 < len(parrafos) and not _es_item(lineas[0])
                and _parece_titulo(lineas[0])):
            eventos.append((lineas[0].strip(), 1))
            hay_titulos = True
            continue
        eventos.extend(_eventos_de_lineas(lineas))
    return eventos, hay_titulos


def parsear_texto_plano(ruta: str, doc_id: str, doc_titulo: str, version: str) -> DocumentoParseado:
    """Parsea un ``.txt``: párrafos separados por una o más líneas en blanco,
    con sus listas por ítem. El formato no declara secciones: solo se
    reconocen títulos sueltos evidentes (:func:`_eventos_de_parrafos`) y, si
    no hay ninguno, se advierte."""
    texto = _leer_texto_archivo(ruta)
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    eventos, hay_titulos = _eventos_de_parrafos(parrafos)

    texto_completo, bloques = _ensamblar_bloques(eventos)
    advertencias = [] if hay_titulos else [t("runtime.plain_text_sections")]
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


# Palabra cortada al final de una línea («garan-\ntía»): se une solo si sigue una minúscula.
_RE_GUION_FINAL = re.compile(r"(?<=[^\W\d_])-\n(?=[^\W\d_A-ZÁÉÍÓÚÑÜÀÂÊÔÃÕÇ])")
# Un título se distingue del cuerpo por un tamaño de letra al menos así de mayor.
FACTOR_TITULO_PDF = 1.15


def _titulos_por_tamano(pagina) -> tuple[str, dict[str, float]]:
    """Texto de la página y, para las líneas escritas en letra más grande que
    el cuerpo, ``{línea normalizada: tamaño}``. Lee el tamaño de cada trozo
    con el ``visitor_text`` de pypdf; agrupa los trozos por altura."""
    lineas: dict[float, list] = {}

    def visitor(texto, cm, tm, _fuente, tamano):
        if not texto or not texto.strip() or not tamano:
            return
        escala = abs(tm[3]) if tm[3] else 1.0
        efectivo = float(tamano) * escala * (abs(cm[3]) if cm[3] else 1.0)
        altura = round(float(tm[5]) * (cm[3] or 1.0) + float(cm[5]), 0)
        datos = lineas.setdefault(altura, [[], 0.0])
        datos[0].append(texto)
        datos[1] = max(datos[1], efectivo)

    texto_pagina = pagina.extract_text(visitor_text=visitor) or ""
    if not lineas:
        return texto_pagina, {}
    # Tamaño del cuerpo: el que más caracteres escribe.
    por_tamano: dict[float, int] = {}
    for trozos, tamano in lineas.values():
        por_tamano[round(tamano, 1)] = por_tamano.get(round(tamano, 1), 0) + sum(len(x) for x in trozos)
    cuerpo = max(por_tamano, key=por_tamano.get)
    grandes = {}
    for trozos, tamano in lineas.values():
        linea = " ".join("".join(trozos).split())
        if tamano >= cuerpo * FACTOR_TITULO_PDF and _parece_titulo(linea):
            grandes[linea] = tamano
    return texto_pagina, grandes


def _parrafos_pdf(texto_pagina: str) -> list[str]:
    """Párrafos de una página. Si el PDF no trae líneas en blanco (lo común),
    corta donde una línea termina una frase y queda claramente más corta que
    las demás, o antes de un ítem de lista; nunca reescribe las líneas. Las
    palabras cortadas con guion se unen después de cortar: unidas antes, la
    línea corta que cierra un párrafo dejaría de parecerlo."""
    if re.search(r"\n\s*\n", texto_pagina):
        return [_RE_GUION_FINAL.sub("", p.strip()) for p in re.split(r"\n\s*\n", texto_pagina) if p.strip()]
    lineas = [l.strip() for l in texto_pagina.split("\n") if l.strip()]
    if not lineas:
        return []
    ancho = max(len(l) for l in lineas)
    parrafos, actual = [], [lineas[0]]
    for previa, linea in zip(lineas, lineas[1:]):
        fin_de_frase = previa.endswith((".", ":", "!", "?", ";")) and len(previa) < 0.85 * ancho
        titulo = (len(actual) == 1 and len(previa) < 0.6 * ancho and not previa.endswith("-")
                  and _parece_titulo(previa))
        if fin_de_frase or titulo or _es_item(linea):
            parrafos.append("\n".join(actual))
            actual = []
        actual.append(linea)
    parrafos.append("\n".join(actual))
    return [_RE_GUION_FINAL.sub("", parrafo) for parrafo in parrafos]


def parsear_pdf(ruta: str, doc_id: str, doc_titulo: str, version: str) -> DocumentoParseado:
    """Parsea un ``.pdf`` con capa de texto real. Secciones desde el
    outline/marcadores del PDF si existen (:func:`_mapear_outline_a_paginas`);
    si no, desde las líneas en letra más grande que el cuerpo
    (:func:`_titulos_por_tamano`, el tamaño mayor es el nivel 1), y si
    tampoco hay, se indexa sin ``seccion_path`` y se advierte. Los párrafos
    se reconstruyen con :func:`_parrafos_pdf` (palabras cortadas con guion
    unidas, ítems de lista por separado).

    Las páginas sin texto (escaneos, fotos) se leen con OCR si está
    disponible (``ipsis.ingesta.ocr``) y se avisa cuáles fueron. Rechaza con
    :class:`DocumentoEscaneadoError` si aun así el documento queda casi sin
    texto -- nunca indexa un documento vacío en silencio."""
    import pypdf

    reader = pypdf.PdfReader(ruta)
    n_paginas = len(reader.pages)
    if n_paginas == 0:
        raise DocumentoEscaneadoError(t("core.pdf_no_pages", path=ruta))

    paginas = [_titulos_por_tamano(pagina) for pagina in reader.pages]
    sin_texto = [i for i, (texto, _) in enumerate(paginas)
                 if len(texto.strip()) < UMBRAL_PDF_ESCANEADO_CHARS_POR_PAGINA]
    leidas_ocr: list[int] = []
    confianza_ocr: dict[int, float] = {}
    motivo_sin_ocr, motor = "", None
    if sin_texto:
        from ipsis.ingesta.ocr import idioma_del_proyecto, leer_paginas, motor_ocr

        motor, motivo_sin_ocr = motor_ocr(idioma_del_proyecto())
        if motor is not None:
            for i, leida in leer_paginas(ruta, sin_texto, motor).items():
                if len(leida.texto.strip()) >= UMBRAL_PDF_ESCANEADO_CHARS_POR_PAGINA:
                    paginas[i] = (leida.texto, {})  # sin tamaños de letra: los títulos salen del texto
                    leidas_ocr.append(i)
                    confianza_ocr[i] = leida.confianza
            if len(leidas_ocr) < len(sin_texto):
                motivo_sin_ocr = t("core.ocr_no_text")
    textos_paginas = [texto for texto, _ in paginas]
    total_chars = sum(len(t.strip()) for t in textos_paginas)
    promedio = total_chars / n_paginas
    if promedio < UMBRAL_PDF_ESCANEADO_CHARS_POR_PAGINA:
        raise DocumentoEscaneadoError(t("core.pdf_scanned", path=ruta, average=promedio,
                                        threshold=UMBRAL_PDF_ESCANEADO_CHARS_POR_PAGINA, pages=n_paginas,
                                        ocr=motivo_sin_ocr))

    encabezados_por_pagina = _mapear_outline_a_paginas(reader)
    # Sin marcadores, los títulos salen del tamaño de letra: el mayor es el nivel 1.
    tamanos = sorted({tam for _, grandes in paginas for tam in grandes.values()}, reverse=True)
    nivel_por_tamano = {tam: min(i + 1, 3) for i, tam in enumerate(tamanos)}
    hay_titulos_ocr = False

    eventos: list[Evento] = []
    for i, (texto_pagina, grandes) in enumerate(paginas):
        for nivel, titulo in encabezados_por_pagina.get(i, []):
            eventos.append((titulo, nivel))
        if i in leidas_ocr and not encabezados_por_pagina:
            # Una página leída con OCR no trae tamaños de letra: los títulos se
            # reconocen como en texto plano (una línea suelta seguida de contenido).
            # Tesseract suele dejar una línea en blanco entre renglones algo
            # separados: no marcan párrafos, así que se cortan como en un PDF
            # sin líneas en blanco (fin de frase en línea corta, ítems, títulos).
            renglones = re.sub(r"\n\s*\n", "\n", texto_pagina)
            de_ocr, titulos = _eventos_de_parrafos(_parrafos_pdf(renglones))
            hay_titulos_ocr = hay_titulos_ocr or titulos
            eventos.extend((" ".join(texto.split()), nivel, *resto) for texto, nivel, *resto in de_ocr)
            continue
        for parrafo in _parrafos_pdf(texto_pagina):
            lineas = parrafo.split("\n")
            normal = " ".join(lineas[0].split())
            if not encabezados_por_pagina and normal in grandes:
                eventos.append((normal, nivel_por_tamano[grandes[normal]]))
                lineas = lineas[1:]
            # dentro de un párrafo, los espacios repetidos de la extracción se colapsan
            eventos.extend((" ".join(texto.split()), nivel, *resto)
                           for texto, nivel, *resto in _eventos_de_lineas(lineas))

    hay_estructura = bool(encabezados_por_pagina) or bool(tamanos) or hay_titulos_ocr
    advertencias = [] if hay_estructura else [t("core.pdf_no_outline")]
    # Las páginas leídas con OCR se avisan (conviene revisar sus citas), y las que
    # siguen sin texto también, en vez de perderlas en silencio.
    if leidas_ocr:
        from ipsis.ingesta.ocr import CONFIANZA_BAJA

        media = sum(confianza_ocr.values()) / len(confianza_ocr)
        advertencias.append(t("core.pdf_ocr_pages", pages=", ".join(str(i + 1) for i in leidas_ocr),
                              n=len(leidas_ocr), total=n_paginas, languages=motor.idiomas,
                              confidence=f"{media:.0f}"))
        bajas = [i for i in leidas_ocr if confianza_ocr[i] < CONFIANZA_BAJA]
        if bajas:
            advertencias.append(t("core.pdf_ocr_low_confidence", threshold=f"{CONFIANZA_BAJA:.0f}",
                                  pages=", ".join(f"{i + 1} ({confianza_ocr[i]:.0f} %)" for i in bajas)))
    vacias = [i + 1 for i in sin_texto if i not in leidas_ocr]
    if vacias:
        advertencias.append(t("core.pdf_pages_without_text", pages=", ".join(map(str, vacias)),
                              n=len(vacias), total=n_paginas, ocr=motivo_sin_ocr))

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
