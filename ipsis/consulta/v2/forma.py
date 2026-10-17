"""Forma de una página de resultados (plan de presentación, P1.1).

Describe cómo se parecen entre sí las primeras fuentes publicadas, para que el widget elija el mensaje y la disposición
(«Esto dice…», «Depende de tu caso», «Lo encontré en dos documentos»). **No cambia qué se publica ni su orden**: es una
función pura sobre lo ya publicado, y una descripción de la página, no una afirmación de que la primera fuente responda
(ADR 0001, ``docs/plan/presentacion.md``).

Cada fuente es un ``dict`` con ``score``, ``tipo_puntaje``, ``doc_id``, ``seccion_path`` (lista) y ``alcance``.

Formas, en este orden de decisión:

* ``clara``: la primera fuente se separa de la segunda por al menos ``margen_claro`` (solo con un margen medido);
* ``variantes``: las dos primeras son variantes de lo mismo (mismo documento y secciones hermanas, o alcances distintos);
* ``documentos``: las dos primeras vienen de documentos distintos;
* ``neutral``: cualquier otro caso, la función apagada o una sola fuente.
"""
from __future__ import annotations

FORMAS = ("clara", "variantes", "documentos", "neutral")


def margen(fuentes: list[dict]) -> float | None:
    """``score`` de la primera fuente menos el de la segunda.

    ``None`` si hay menos de dos fuentes, si falta algún puntaje o si no son del mismo tipo (un logit del reranker y un
    puntaje de recuperación no se restan).
    """
    if len(fuentes) < 2:
        return None
    primera, segunda = fuentes[0], fuentes[1]
    if primera.get("score") is None or segunda.get("score") is None:
        return None
    if primera.get("tipo_puntaje") != segunda.get("tipo_puntaje"):
        return None
    return float(primera["score"]) - float(segunda["score"])


def _padre(fuente: dict) -> tuple:
    return tuple((fuente.get("seccion_path") or [])[:-1])


def relacion(fuentes: list[dict]) -> str | None:
    """Cómo se relacionan las dos primeras fuentes: ``documentos``, ``variantes`` u ``otra``; ``None`` si hay menos de dos.

    * ``documentos``: distinto ``doc_id``;
    * ``variantes``: el mismo documento y (los dos tienen ``alcance`` y es distinto, o sus rutas de sección difieren
      pero comparten una sección padre no vacía: son hermanas);
    * ``otra``: el mismo documento sin esa relación (otra sección, o la misma sección).
    """
    if len(fuentes) < 2:
        return None
    a, b = fuentes[0], fuentes[1]
    if a.get("doc_id") != b.get("doc_id"):
        return "documentos"
    if a.get("alcance") and b.get("alcance") and a["alcance"] != b["alcance"]:
        return "variantes"
    ruta_a, ruta_b = tuple(a.get("seccion_path") or ()), tuple(b.get("seccion_path") or ())
    if ruta_a != ruta_b and _padre(a) and _padre(a) == _padre(b):
        return "variantes"
    return "otra"


def forma_de_pagina(fuentes: list[dict], *, activo: bool = False, margen_claro: float | None = None) -> str:
    """La forma de la página (``FORMAS``). Apagada, o con menos de dos fuentes, es siempre ``neutral``."""
    if not activo or len(fuentes) < 2:
        return "neutral"
    separacion = margen(fuentes)
    if margen_claro is not None and separacion is not None and separacion >= margen_claro:
        return "clara"
    return {"variantes": "variantes", "documentos": "documentos"}.get(relacion(fuentes), "neutral")


def margen_claro_efectivo(presentacion: dict, perfil: str | None) -> float | None:
    """El margen de ``presentacion`` (``PresentacionConfig`` volcada) para ``perfil``: el suyo, o el general."""
    por_perfil = presentacion.get("margen_claro_por_perfil") or {}
    if perfil is not None and perfil in por_perfil:
        return por_perfil[perfil]
    return presentacion.get("margen_claro")


__all__ = ["FORMAS", "forma_de_pagina", "margen", "margen_claro_efectivo", "relacion"]
