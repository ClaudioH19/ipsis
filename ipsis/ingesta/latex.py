"""LaTeX (``.tex``) a Markdown legible, para reutilizar el parser y la preparación estructural de Markdown.

No pretende compilar LaTeX: conserva lo que se lee y se busca. Los títulos (``\\section``…), las listas, las tablas
(``tabular``), los pies de tabla y figura, y los entornos tipo teorema (que dejan una línea-título corta) se
convierten en su equivalente Markdown; el formato en línea (``\\textbf``, ``\\emph``…) se reduce a su texto, y las
**fórmulas se conservan como texto fuente** (``$…$`` en línea; las de bloque, como párrafo propio), porque buscar
«\\frac{a}{b}» o «E = mc^2» debe poder encontrarlas. Los comentarios y el preámbulo se descartan.
"""
from __future__ import annotations

import re

_ACENTOS = {"'": "\u0301", "`": "\u0300", '"': "\u0308", "^": "\u0302", "~": "\u0303", "c": "\u0327"}
_NIVELES = ("chapter", "section", "subsection", "subsubsection", "paragraph", "subparagraph")
_FORMATO = {"textbf", "textit", "emph", "underline", "textsc", "texttt", "textrm", "textsf", "mbox", "text",
            "uppercase", "lowercase", "mathrm_texto", "section_name"}
_TEOREMAS = {"theorem", "lemma", "proposition", "corollary", "definition", "proof", "remark", "example", "claim",
             "note", "exercise", "problem", "solution", "conjecture", "axiom"}
_MATEMATICAS_BLOQUE = ("equation", "align", "gather", "multline", "eqnarray", "displaymath", "flalign", "alignat")
_RE_COMENTARIO = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
_RE_ENTORNO_MATE = "|".join(_MATEMATICAS_BLOQUE)
_RE_MATE_BLOQUE = re.compile(
    rf"\$\$(?P<a>.+?)\$\$|\\\[(?P<b>.+?)\\\]|\\begin\{{(?P<e>{_RE_ENTORNO_MATE})\*?\}}(?P<c>.+?)\\end\{{(?P=e)\*?\}}",
    re.DOTALL)
_RE_MATE_LINEA = re.compile(r"\\\((?P<a>.+?)\\\)|(?<![\\$])\$(?!\$)(?P<b>[^$\n]+?)(?<!\\)\$(?!\$)", re.DOTALL)
_RE_VERBATIM = re.compile(r"\\begin\{(verbatim|lstlisting|minted)\*?\}(?:\[[^\]]*\])?(?:\{[^}]*\})?(?P<c>.*?)\\end\{\1\*?\}", re.DOTALL)
_RE_TABULAR = re.compile(r"\\begin\{(tabular|tabularx|longtable|array)\*?\}(?:\{[^}]*\})?(?:\[[^\]]*\])?(?:\{[^}]*\})?(?P<c>.*?)\\end\{\1\*?\}", re.DOTALL)
_RE_SECCION = re.compile(r"\\(chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?(?:\[[^\]]*\])?\{(?P<t>(?:[^{}]|\{[^{}]*\})*)\}")
_RE_TEOREMA = re.compile(r"\\begin\{(?P<n>%s)\*?\}(?:\[(?P<o>[^\]]*)\])?" % "|".join(_TEOREMAS))
_RE_ITEM = re.compile(r"\\item(?:\[(?P<l>[^\]]*)\])?")


def _sin_comentarios(texto: str) -> str:
    return _RE_COMENTARIO.sub("", texto)


def _acentos(texto: str) -> str:
    def poner(m):
        marca, letra = m.group(1) or "c", m.group(2) or m.group(3) or m.group(4)
        return letra + _ACENTOS[marca]
    import unicodedata

    # \'a, \"{o}, \c{c}, \c c (la cedilla exige una sola letra, para no confundirla con \centering)
    texto = re.sub(r"\\(?:([\'`\"^~])\s*\{?([A-Za-z])\}?|c(?:\{([A-Za-z])\}|\s+([A-Za-z])(?![A-Za-z])))", poner, texto)
    texto = texto.replace(r"\ss", "ß").replace(r"\ae", "æ").replace(r"\o", "ø").replace(r"\aa", "å")
    return unicodedata.normalize("NFC", texto)


def _limpiar_linea(texto: str) -> str:
    """Formato en línea -> texto. No toca los marcadores de fórmula (``\\x00M…\\x00``)."""
    texto = _acentos(texto)
    texto = re.sub(r"\\(?:cite|citep|citet|nocite)\*?(?:\[[^\]]*\])*\{([^{}]*)\}", r"[\1]", texto)
    texto = re.sub(r"\\(?:ref|eqref|autoref|pageref|cref|Cref|label)\*?\{[^{}]*\}", "", texto)
    texto = re.sub(r"\\footnote\{((?:[^{}]|\{[^{}]*\})*)\}", r" (\1)", texto)
    texto = re.sub(r"\\href\{[^{}]*\}\{([^{}]*)\}", r"\1", texto)
    texto = re.sub(r"\\url\{([^{}]*)\}", r"\1", texto)
    for _ in range(4):  # comandos anidados: \textbf{\emph{x}}
        anterior = texto
        texto = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", texto)
        if texto == anterior:
            break
    texto = re.sub(r"\\(?:hline|toprule|midrule|bottomrule|centering|noindent|maketitle|tableofcontents|newpage|"
                   r"clearpage|medskip|bigskip|smallskip|par|quad|qquad|hfill|vfill|linebreak)\b\*?", " ", texto)
    texto = texto.replace(r"\ldots", "…").replace(r"\dots", "…").replace(r"\&", "&").replace(r"\%", "%")
    texto = texto.replace(r"\$", "$").replace(r"\_", "_").replace(r"\#", "#").replace(r"\{", "{").replace(r"\}", "}")
    texto = texto.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”").replace("~", " ")
    texto = re.sub(r"\\\\(?:\[[^\]]*\])?", " ", texto)
    texto = re.sub(r"\\[a-zA-Z]+\*?", " ", texto)  # comandos sin argumento que quedan
    texto = texto.replace("{", "").replace("}", "")
    texto = re.sub(r"[ \t]+", " ", texto).strip()
    return re.sub(r"\s+([.,;:])", r"\1", texto)


def _tabla_a_markdown(cuerpo: str) -> str:
    filas = []
    for fila in re.split(r"\\\\(?:\[[^\]]*\])?", cuerpo):
        fila = re.sub(r"\\(?:hline|toprule|midrule|bottomrule|endhead|endfirsthead|endfoot|endlastfoot)\b|\\cline\{[^}]*\}", " ", fila)
        if not fila.strip():
            continue
        celdas = [_limpiar_linea(re.sub(r"\\multicolumn\{\d+\}\{[^}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", c)) for c in fila.split("&")]
        if any(celdas):
            filas.append(celdas)
    if not filas:
        return ""
    ancho = max(len(f) for f in filas)
    lineas = []
    for i, f in enumerate(filas):
        f = f + [""] * (ancho - len(f))
        lineas.append("| " + " | ".join(f) + " |")
        if i == 0:
            lineas.append("|" + "|".join([" --- "] * ancho) + "|")
    return "\n" + "\n".join(lineas) + "\n"


def latex_a_markdown(fuente: str) -> tuple[str, list[str]]:
    """``(markdown, advertencias)``. Determinista y tolerante: lo que no entiende se descarta, no falla."""
    avisos: list[str] = []
    texto = _sin_comentarios(fuente.replace("\r\n", "\n"))
    inicio, fin = texto.find(r"\begin{document}"), texto.rfind(r"\end{document}")
    if inicio != -1:
        texto = texto[inicio + len(r"\begin{document}"):fin if fin > inicio else len(texto)]
    texto = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", "", texto, flags=re.DOTALL)
    protegidos: list[tuple[str, str]] = []

    def guardar(valor: str, bloque: bool) -> str:
        protegidos.append((valor.strip(), "bloque" if bloque else "linea"))
        return f"\x00M{len(protegidos) - 1}\x00"

    texto = _RE_VERBATIM.sub(lambda m: "\n\n" + guardar(m.group("c"), True) + "\n\n", texto)
    texto = _RE_MATE_BLOQUE.sub(lambda m: "\n\n" + guardar(next(g for g in (m.group("a"), m.group("b"), m.group("c")) if g), True)
                                + "\n\n", texto)
    texto = _RE_MATE_LINEA.sub(lambda m: guardar(m.group("a") or m.group("b"), False), texto)
    if protegidos:
        avisos.append("LaTeX: las fórmulas se conservan como texto fuente")

    # Títulos: el nivel más alto presente es el 1.
    usados = [n for n in _NIVELES if re.search(rf"\\{n}\*?(?:\[[^\]]*\])?\{{", texto)]
    nivel = {n: i + 1 for i, n in enumerate(sorted(set(_NIVELES[:1]) & set(usados) | set(usados), key=_NIVELES.index))}
    texto = _RE_SECCION.sub(lambda m: f"\n\n{'#' * nivel[m.group(1)]} {_limpiar_linea(m.group('t'))}\n\n", texto)
    texto = re.sub(r"\\begin\{abstract\}", "\n\n# Abstract\n\n", texto).replace(r"\end{abstract}", "\n\n")

    # Tablas y pies.
    texto = _RE_TABULAR.sub(lambda m: _tabla_a_markdown(m.group("c")), texto)
    texto = re.sub(r"\\caption(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})*)\}", lambda m: f"\n\n{_limpiar_linea(m.group(1))}\n\n", texto)
    texto = re.sub(r"\\(?:begin|end)\{(?:table|figure|wraptable|center|flushleft|flushright|quote|quotation|minipage|"
                   r"landscape|sidewaystable|tabbing)\*?\}(?:\[[^\]]*\])?(?:\{[^}]*\})?", "\n\n", texto)
    texto = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{[^{}]*\}", "", texto)
    # Teoremas y similares: una línea-título corta («Theorem (Pythagoras)»).
    texto = _RE_TEOREMA.sub(lambda m: "\n\n" + m.group("n").capitalize() + (f" ({_limpiar_linea(m.group('o'))})" if m.group("o") else "") + "\n\n", texto)
    texto = re.sub(r"\\end\{(?:%s)\*?\}" % "|".join(_TEOREMAS), "\n\n", texto)
    # Listas.
    texto = re.sub(r"\\(?:begin|end)\{(?:itemize|enumerate|description)\}(?:\[[^\]]*\])?", "\n", texto)
    texto = _RE_ITEM.sub(lambda m: "\n- " + (f"{m.group('l')}: " if m.group("l") else ""), texto)

    lineas = []
    for linea in texto.split("\n"):
        limpia = linea if linea.lstrip().startswith(("#", "|")) else _limpiar_linea(linea)
        lineas.append(limpia)
    texto = "\n".join(lineas)

    def restaurar(m):
        valor, clase = protegidos[int(m.group(1))]
        return f"${valor}$" if clase == "linea" else valor
    texto = re.sub(r"\x00M(\d+)\x00", restaurar, texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip() + "\n"
    texto = re.sub(r"(?m)^(- .*)\n\n(?=- )", r"\1\n", texto)  # los ítems de una lista van juntos
    return texto, avisos
