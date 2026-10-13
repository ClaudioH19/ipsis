"""Capturas reproducibles del widget real con datos de ejemplo, sin modelos ni API.

uv run --extra browser python herramientas/capturas_widget.py
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ipsis.aplicacion.widget import aplicar_preset, generar_vista_previa


def capturar():
    from playwright.sync_api import sync_playwright

    temporal = RAIZ / ".cache" / "capturas-widget"
    temporal.mkdir(parents=True, exist_ok=True)
    activos = RAIZ / "docs" / "assets"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for idioma in ("en", "es"):
                os.environ["IPSIS_LANG"] = idioma
                ruta = str(temporal / (idioma + ".yaml"))
                aplicar_preset("ocean", ruta)
                vista = generar_vista_previa(str(temporal / (idioma + ".html")), ruta)
                for nombre, ancho, alto, esquema in (
                    ("sources", 1100, 1000, "light"),
                    ("sources-dark", 1100, 1000, "dark"),
                    ("mobile", 375, 1000, "light"),
                    ("faq", 1100, 1000, "light"),
                ):
                    page = browser.new_page(viewport={"width": ancho, "height": alto},
                                            color_scheme=esquema, reduced_motion="reduce", device_scale_factor=1)
                    errores = []
                    page.on("pageerror", lambda e: errores.append(str(e)))
                    page.add_init_script("Math.random = function () { return 0; };")
                    page.goto(vista.as_uri())
                    page.locator(".rw-faq summary").wait_for()
                    if nombre == "faq":
                        page.locator(".rw-faq summary").click()
                    else:
                        page.locator("#mostrar").click()
                        page.locator(".rw-resultado").first.wait_for()
                        page.locator(".rw-resultado-titulo").first.click()
                        page.locator(".rw-resultado-contexto").first.wait_for()
                    if errores:
                        raise RuntimeError(errores)
                    destino = activos / f"widget-{nombre}-{idioma}.png"
                    page.locator(".rw-panel").screenshot(path=str(destino), animations="disabled")
                    print(destino.relative_to(RAIZ))
                    page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    capturar()
