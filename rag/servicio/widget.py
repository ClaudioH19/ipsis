"""Presentación del widget: presets visuales y exportación del cliente embebible."""
from __future__ import annotations

import os
import html as html_lib
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from rag.recursos import leer_plantilla
from rag.servicio.estilos import RUTA_ESTILOS, cargar_estilos, render_css
import html
from importlib.resources import files


PRESETS: dict[str, dict[str, Any]] = {
    "clasico": {
        "descripcion": "Azul neutro, cómodo y equivalente al diseño de fábrica.",
        "tema": {},
    },
    "minimal": {
        "descripcion": "Interfaz compacta, radios discretos y sombras suaves.",
        "tema": {
            "colores": {"acento": "#334155", "fondo": "#f8fafc", "borde": "#e2e8f0"},
            "forma": {"radio_panel": "12px", "radio_burbuja": "10px", "radio_control": "8px"},
            "sombras": {"panel": "0 8px 28px rgba(15,23,42,.12)", "boton": "0 5px 16px rgba(15,23,42,.2)"},
            "presentacion": {"densidad": "compacta", "citas": "acordeon"},
        },
    },
    "editorial": {
        "descripcion": "Paleta cálida y tipografía serif para documentación extensa.",
        "tema": {
            "colores": {
                "acento": "#8b2f3c", "acento_texto": "#fffaf3", "superficie": "#fffdf8",
                "fondo": "#f5efe5", "texto": "#29231f", "texto_suave": "#70655c",
                "borde": "#ded2c4", "aviso": "#8a5a18", "aviso_borde": "#b9812d",
            },
            "tipografia": {"familia": "Georgia, 'Times New Roman', serif", "interlineado": "1.65"},
            "forma": {"radio_panel": "8px", "radio_burbuja": "6px", "radio_control": "4px"},
            "presentacion": {"densidad": "comoda", "citas": "abiertas"},
        },
    },
    "contraste": {
        "descripcion": "Contraste alto, controles marcados y animaciones desactivadas.",
        "tema": {
            "colores": {
                "acento": "#ffd400", "acento_texto": "#000000", "superficie": "#ffffff",
                "fondo": "#ffffff", "texto": "#000000", "texto_suave": "#242424",
                "borde": "#000000", "aviso": "#000000", "aviso_borde": "#000000",
            },
            "colores_oscuro": {
                "acento": "#ffe600", "acento_texto": "#000000", "superficie": "#000000",
                "fondo": "#000000", "texto": "#ffffff", "texto_suave": "#ffffff",
                "borde": "#ffffff", "aviso": "#ffe600", "aviso_borde": "#ffe600",
            },
            "forma": {"radio_panel": "0px", "radio_burbuja": "0px", "radio_control": "0px"},
            "animaciones": {"activadas": False},
            "presentacion": {"mostrar_etiqueta_estado": True},
        },
    },
}

_SECCIONES = {"colores", "colores_oscuro", "tipografia", "forma", "sombras", "animaciones"}


def listar_presets() -> dict[str, str]:
    return {nombre: datos["descripcion"] for nombre, datos in PRESETS.items()}


def _fusionar(destino: dict, cambios: dict) -> dict:
    salida = deepcopy(destino)
    for clave, valor in cambios.items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = _fusionar(salida[clave], valor)
        else:
            salida[clave] = deepcopy(valor)
    return salida


def validar_tema(tema: dict) -> None:
    if not isinstance(tema, dict):
        raise ValueError("el tema debe ser un objeto YAML")
    for seccion in _SECCIONES:
        valores = tema.get(seccion)
        if valores is not None and not isinstance(valores, dict):
            raise ValueError(f"{seccion} debe ser un objeto")
        for clave, valor in (valores or {}).items():
            if isinstance(valor, bool):
                if seccion != "animaciones" or clave != "activadas":
                    raise ValueError(f"{seccion}.{clave} no admite booleanos")
                continue
            if not isinstance(valor, (str, int, float)):
                raise ValueError(f"{seccion}.{clave} debe ser un valor CSS escalar")
            if any(caracter in str(valor) for caracter in (";", "{", "}", "<", ">", "\n", "\r")):
                raise ValueError(f"{seccion}.{clave} contiene caracteres CSS no permitidos")
    presentacion = tema.get("presentacion") or {}
    if not isinstance(presentacion, dict):
        raise ValueError("presentacion debe ser un objeto")
    if presentacion.get("densidad", "comoda") not in {"comoda", "compacta"}:
        raise ValueError("presentacion.densidad debe ser 'comoda' o 'compacta'")
    if presentacion.get("citas", "acordeon") not in {"acordeon", "abiertas", "ocultas"}:
        raise ValueError("presentacion.citas debe ser acordeon, abiertas u ocultas")
    if not isinstance(presentacion.get("mostrar_etiqueta_estado", True), bool):
        raise ValueError("presentacion.mostrar_etiqueta_estado debe ser booleano")
    render_css(tema=tema)


def aplicar_preset(nombre: str, ruta: str = RUTA_ESTILOS) -> dict:
    if nombre not in PRESETS:
        raise ValueError(f"preset desconocido {nombre!r}; disponibles: {sorted(PRESETS)}")
    base = yaml.safe_load(leer_plantilla("estilos.yaml")) or {}
    actual = cargar_estilos(ruta)
    # Cada preset parte de fábrica para no heredar accidentalmente valores de
    # otro preset. Se preservan CSS explícito y extensiones ajenas al esquema.
    tema = _fusionar(base, PRESETS[nombre]["tema"])
    if "css_extra" in actual:
        tema["css_extra"] = actual["css_extra"]
    for clave, valor in actual.items():
        if clave not in base and clave != "preset":
            tema[clave] = deepcopy(valor)
    tema["preset"] = nombre
    validar_tema(tema)

    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".tmp")
    temporal.write_text(
        yaml.safe_dump(tema, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    os.replace(temporal, destino)
    return tema


def generar_vista_previa(
    salida: str = ".cache/widget-vista-previa.html",
    ruta_estilos: str = RUTA_ESTILOS,
) -> Path:
    """Genera un mockup autónomo, sin API ni índice, con todos los estados."""
    tema = cargar_estilos(ruta_estilos)
    validar_tema(tema)
    css_tema = render_css(tema=tema)
    preset = str(tema.get("preset") or "personalizado")
    if "</style" in css_tema.lower():
        raise ValueError("css_extra no puede cerrar la etiqueta style en la vista previa")
    preset_html = html_lib.escape(preset)
    contenido_html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vista previa del widget — {preset_html}</title>
<style>
{css_tema}
*{{box-sizing:border-box}} body{{margin:0;padding:32px;background:#dfe3e8;font-family:Arial,sans-serif}}
.preview{{max-width:920px;margin:auto;display:grid;grid-template-columns:minmax(280px,390px) 1fr;gap:28px;align-items:start}}
.rw-raiz{{position:static;background:var(--rw-fondo,#f4f5f7);color:var(--rw-texto,#15181d);font-family:var(--rw-fuente,Arial,sans-serif);border:1px solid var(--rw-borde,#ddd);border-radius:var(--rw-radio-panel,18px);box-shadow:var(--rw-sombra-panel);overflow:hidden}}
.cabecera{{padding:16px;background:var(--rw-superficie,#fff);border-bottom:1px solid var(--rw-borde,#ddd);font-weight:700}}
.mensajes{{padding:16px;display:flex;flex-direction:column;gap:12px}}
.rw-msg{{padding:10px 13px;border-radius:var(--rw-radio-burbuja,16px);font-size:var(--rw-tamano-mensaje,13.5px);line-height:var(--rw-interlineado,1.55)}}
.rw-msg-usuario{{align-self:flex-end;background:var(--rw-acento,#2563eb);color:var(--rw-acento-texto,#fff)}}
.rw-msg-ok,.rw-msg-relacionado,.rw-msg-conversacional{{background:var(--rw-superficie,#fff);border:1px solid var(--rw-borde,#ddd)}}
.rw-msg-relacionado{{border-left:4px solid var(--rw-aviso-borde,#d9a441)}}
.rw-msg-sin_respuesta{{color:var(--rw-texto-suave,#666);text-align:center}}
.etiqueta{{font-size:10px;font-weight:800;text-transform:uppercase;color:var(--rw-aviso,#9a6500);margin-bottom:5px}}
.rw-citas{{margin-top:10px;border-top:1px solid var(--rw-borde,#ddd);padding-top:8px}}
.rw-citas details{{background:var(--rw-fondo,#f4f5f7);border:1px solid var(--rw-borde,#ddd);padding:8px;border-radius:8px}}
.rw-citas summary{{cursor:pointer;font-weight:700}} .rw-cita-texto{{font-size:var(--rw-tamano-cita,12px)}}
.info{{background:white;padding:22px;border-radius:12px}} code{{background:#eef1f4;padding:2px 5px}}
@media(max-width:720px){{body{{padding:14px}}.preview{{grid-template-columns:1fr}}}}
</style></head><body><main class="preview">
<section class="rw-raiz" aria-label="Mockup del widget">
  <div class="cabecera">Asistente documental · preset {preset_html}</div>
  <div class="mensajes">
    <div class="rw-msg rw-msg-usuario">¿Cada cuánto debo cambiar el filtro?</div>
    <div class="rw-msg rw-msg-ok"><div class="etiqueta">Respuesta directa</div>El filtro se cambia cada 6 meses.
      <div class="rw-citas"><details open><summary>Manual · Filtros</summary><p class="rw-cita-texto">El filtro de sedimentos se cambia cada 6 meses.</p></details></div>
    </div>
    <div class="rw-msg rw-msg-relacionado"><div class="etiqueta">Información relacionada</div>El documento describe la garantía, pero no confirma ese supuesto.</div>
    <div class="rw-msg rw-msg-sin_respuesta">No encontré una respuesta respaldada por los documentos.</div>
    <div class="rw-msg rw-msg-conversacional">Hola, puedo ayudarte a consultar la documentación.</div>
  </div>
</section>
<aside class="info"><h1>Vista previa</h1><p>Este mockup no consulta el índice. Permite revisar paleta, tipografía, forma, estados y citas antes de publicar.</p><p>Preset activo: <code>{preset_html}</code></p></aside>
</main></body></html>"""
    destino = Path(salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido_html, encoding="utf-8")
    return destino


__all__ = [
    "PRESETS", "aplicar_preset", "generar_vista_previa", "listar_presets",
    "validar_tema",
]


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
