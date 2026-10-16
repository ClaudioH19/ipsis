"""LaTeX (.tex): conversión a Markdown legible, parser y preparación estructural."""
from __future__ import annotations

from pathlib import Path

from ipsis.ingesta.latex import latex_a_markdown
from ipsis.ingesta.parsear import EXTENSIONES_SOPORTADAS, parsear_documento
from ipsis.ingesta.preparacion import PARSER_VERSION_LATEX, preparar_documento
from ipsis.ingesta.unidades import unidades_documento

FUENTE = r"""\documentclass{article}
\usepackage[utf8]{inputenc}
\begin{document}
\maketitle
% un comentario que no debe aparecer
\section{Pr\'actica Profesional I}
La pr\'actica dura \textbf{4 semanas}\footnote{como m\'inimo} y se ve en la Tabla~\ref{tab:p1}.
\begin{table}[h]
\centering
\caption{Ponderaciones de la Pr\'actica I}\label{tab:p1}
\begin{tabular}{|l|c|}
\hline
Instrumento & Ponderaci\'on \\ \hline
Portfolio & 40\% \\
Defensa & 60\% \\ \hline
\end{tabular}
\end{table}
\subsection{Nota final}
La nota es $N = 0{,}4 P + 0{,}6 D$ y, en general,
\begin{equation}
N = \sum_{i=1}^{k} w_i x_i
\end{equation}
\begin{itemize}
\item Se aprueba con 4,0.
\item La entrega tard\'ia penaliza \emph{1,0 punto}.
\end{itemize}
\begin{theorem}[Monoton\'ia]
Si todas las notas suben, la nota final no baja.
\end{theorem}
\end{document}
"""


def test_el_markdown_conserva_titulos_tablas_listas_y_formulas():
    md, avisos = latex_a_markdown(FUENTE)
    assert "# Práctica Profesional I" in md and "## Nota final" in md
    assert "% un comentario" not in md and "comentario" not in md
    assert "La práctica dura 4 semanas (como mínimo) y se ve en la Tabla." in md
    assert "Ponderaciones de la Práctica I" in md                       # el pie queda como párrafo previo a la tabla
    assert "| Instrumento | Ponderación |" in md and "| Portfolio | 40% |" in md
    assert "$N = 0{,}4 P + 0{,}6 D$" in md                              # fórmula en línea intacta
    assert "N = \\sum_{i=1}^{k} w_i x_i" in md                           # fórmula de bloque como texto fuente
    assert "- Se aprueba con 4,0." in md and "- La entrega tardía penaliza 1,0 punto." in md
    assert "Theorem (Monotonía)" in md
    assert "ȩntering" not in md and "centering" not in md and "\\" not in md.replace("\\sum", "").replace("\\frac", "")
    assert any("fórmulas" in a for a in avisos)


def test_sin_formulas_no_hay_aviso_y_la_cedilla_no_rompe_centering():
    md, avisos = latex_a_markdown(r"\begin{document}\section{Uno}\centering Texto con fa\c{c}ade.\end{document}")
    assert "façade" in md and "centering" not in md and avisos == []


def test_parser_y_preparacion_leen_un_tex(tmp_path: Path):
    ruta = tmp_path / "reglamento.tex"
    ruta.write_text(FUENTE, encoding="utf-8")
    assert ".tex" in EXTENSIONES_SOPORTADAS
    doc = parsear_documento(str(ruta), "r", "Reglamento", "1")
    assert doc.bloques and all(doc.texto_completo[b.offset_inicio:b.offset_fin] == b.texto for b in doc.bloques)
    assert any(b.tipo_contenido == "titulo" and b.texto == "Nota final" for b in doc.bloques)
    preparado = preparar_documento(ruta, doc_id="r", doc_titulo="Reglamento")
    assert preparado.parser_version == PARSER_VERSION_LATEX
    assert any("tablas LaTeX" in a for a in preparado.advertencias)
    hijos, padres = unidades_documento(preparado)
    assert hijos and padres and all(preparado.texto_completo[p.offset_inicio:p.offset_fin] == p.texto_fuente for p in padres.values())
    assert any(p.seccion_path == ["Práctica Profesional I", "Nota final"] for p in padres.values())


def test_markdown_y_pdf_con_la_preparacion_estructural(tmp_path: Path):
    """Los otros formatos con estructura siguen produciendo unidades por sección (y alcance por línea-título)."""
    md = tmp_path / "r.md"
    md.write_text("# Reglamento\n\n## Práctica I\n\nLa práctica I dura 4 semanas.\n\n## Práctica II\n\nLa práctica II dura 8 semanas.\n",
                  encoding="utf-8")
    _, padres = unidades_documento(preparar_documento(md, doc_id="m", doc_titulo="R"))
    assert sorted(p.seccion_path[-1] for p in padres.values()) == ["Práctica I", "Práctica II"]
    txt = tmp_path / "f.txt"
    txt.write_text("Escala de niveles\n\nEstas son las competencias que esperamos que el estudiante logre durante la práctica.\n\n"
                   "Evidencia y comentario\n\nDescriba brevemente el aporte concreto del estudiante a la organización.\n", encoding="utf-8")
    _, padres = unidades_documento(preparar_documento(txt, doc_id="t", doc_titulo="F"))
    assert {tuple(p.seccion_path) for p in padres.values()} >= {("Escala de niveles",), ("Evidencia y comentario",)}
