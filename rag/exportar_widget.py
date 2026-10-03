"""Exportación autocontenida del cliente web embebible."""
from __future__ import annotations

import html
from importlib.resources import files
from pathlib import Path


def exportar_widget(
    carpeta: str,
    *,
    api: str = "http://127.0.0.1:8000",
    posicion: str = "abajo-derecha",
) -> Path:
    if posicion not in {"abajo-derecha", "abajo-izquierda"}:
        raise ValueError("posición debe ser abajo-derecha o abajo-izquierda")
    destino = Path(carpeta).resolve()
    destino.mkdir(parents=True, exist_ok=True)
    javascript = files("rag.servicio").joinpath("estaticos", "widget.js").read_text(encoding="utf-8")
    (destino / "widget.js").write_text(javascript, encoding="utf-8")
    api_attr = html.escape(api.rstrip("/"), quote=True)
    posicion_attr = html.escape(posicion, quote=True)
    snippet = (
        f'<rag-extractivo-chat api="{api_attr}" posicion="{posicion_attr}">'
        "</rag-extractivo-chat>\n"
        '<script src="./widget.js"></script>\n'
    )
    (destino / "snippet.html").write_text(snippet, encoding="utf-8")
    return destino


__all__ = ["exportar_widget"]
