"""Presentación del widget: presets visuales y exportación del cliente embebible."""
from __future__ import annotations

import html
import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Any

from ipsis.aplicacion.estilos import RUTA_ESTILOS, cargar_estilos, render_css
from ipsis.configuracion import rutas
from ipsis.recursos.mensajes import t
from ipsis.configuracion.archivos import escribir
from ipsis.recursos import leer_plantilla


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
            "presentacion": {"densidad": "comoda", "citas": "lista"},
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


def _externo(ruta: str) -> str:
    """``seccion.clave`` interna → la del archivo (``colores.acento`` → ``colors.accent``)."""
    from ipsis.configuracion.glosario import nombres_externos

    return nombres_externos(ruta, "estilos")


def validar_tema(tema: dict) -> None:
    if not isinstance(tema, dict):
        raise ValueError(t("styles.not_object"))
    for seccion in _SECCIONES:
        valores = tema.get(seccion)
        if valores is not None and not isinstance(valores, dict):
            raise ValueError(t("styles.section_object", section=_externo(seccion)))
        for clave, valor in (valores or {}).items():
            if isinstance(valor, bool):
                if seccion != "animaciones" or clave != "activadas":
                    raise ValueError(t("styles.no_booleans", key=_externo(f"{seccion}.{clave}")))
                continue
            if not isinstance(valor, (str, int, float)):
                raise ValueError(t("styles.scalar", key=_externo(f"{seccion}.{clave}")))
            if any(caracter in str(valor) for caracter in (";", "{", "}", "<", ">", "\n", "\r")):
                raise ValueError(t("styles.forbidden", key=_externo(f"{seccion}.{clave}")))
    presentacion = tema.get("presentacion") or {}
    if not isinstance(presentacion, dict):
        raise ValueError(t("styles.section_object", section="presentation"))
    if presentacion.get("densidad", "comoda") not in {"comoda", "compacta"}:
        raise ValueError(t("styles.density"))
    # Las citas no se pueden ocultar: «abiertas» y «ocultas» son valores anteriores
    # que se leen como «lista» y «acordeon» (citas_presentacion).
    if presentacion.get("citas", "acordeon") not in {"acordeon", "lista", "abiertas", "ocultas"}:
        raise ValueError(t("styles.citations"))
    if not isinstance(presentacion.get("mostrar_etiqueta_estado", True), bool):
        raise ValueError(t("styles.status_label"))
    ubicacion_widget(tema)  # valida tema.ubicacion
    render_css(tema=tema)


POSICIONES = ("abajo-derecha", "abajo-izquierda", "arriba-derecha", "arriba-izquierda", "incrustado")
TAMANOS = ("compacto", "normal", "amplio")
LANZADORES = ("burbuja", "pestana", "oculto")
UBICACION_POR_DEFECTO = {"posicion": "abajo-derecha", "desplazamiento_x": 24, "desplazamiento_y": 24,
                         "z_index": 2147483000, "tamano": "normal", "lanzador": "burbuja"}


def citas_presentacion(valor: str | None) -> str:
    """``acordeon`` o ``lista``; los valores anteriores no ocultan las citas."""
    return "lista" if valor in ("lista", "abiertas") else "acordeon"


def ubicacion_widget(tema: dict | None = None) -> dict:
    """``styles.yaml::ubicacion`` validada y con sus valores por defecto."""
    tema = cargar_estilos() if tema is None else tema
    propia = tema.get("ubicacion") or {}
    if not isinstance(propia, dict):
        raise ValueError(t("styles.section_object", section="placement"))
    if extra := set(propia) - set(UBICACION_POR_DEFECTO):
        raise ValueError(t("styles.unknown_keys", keys=sorted(extra)))
    base = dict(UBICACION_POR_DEFECTO)
    # Compatibilidad: forma.margen ("24px") era la distancia al borde antes de ubicacion.
    margen = str((tema.get("forma") or {}).get("margen", "")).strip().removesuffix("px")
    if margen.isdigit():
        base["desplazamiento_x"] = base["desplazamiento_y"] = int(margen)
    ubicacion = {**base, **propia}
    for clave, validos in (("posicion", POSICIONES), ("tamano", TAMANOS), ("lanzador", LANZADORES)):
        if ubicacion[clave] not in validos:
            raise ValueError(t("styles.one_of", key=_externo(clave),
                               values=", ".join(_externo(v) for v in validos)))
    for clave, minimo, maximo in (("desplazamiento_x", 0, 400), ("desplazamiento_y", 0, 400),
                                  ("z_index", 0, 2147483647)):
        valor = ubicacion[clave]
        if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
            raise ValueError(t("styles.integer_between", key=_externo(clave), minimum=minimo, maximum=maximo))
    return ubicacion


def snippet_widget(api: str, *, componente: bool = False, clave_widget: str | None = None) -> str:
    """Etiqueta lista para pegar en el sitio, según ``styles.yaml::ubicacion``."""
    u = ubicacion_widget()
    api = api.rstrip("/")
    atributos = {"posicion": u["posicion"], "tamano": u["tamano"], "lanzador": u["lanzador"],
                 "desplazamiento-x": u["desplazamiento_x"], "desplazamiento-y": u["desplazamiento_y"]}
    if clave_widget:
        atributos["widget-key"] = clave_widget
    if componente:
        attrs = " ".join(f'{k}="{html.escape(str(v), quote=True)}"' for k, v in atributos.items())
        return (f'<ipsis-chat api="{html.escape(api, quote=True)}" {attrs}></ipsis-chat>\n'
                f'<script src="{html.escape(api, quote=True)}/widget.js" defer></script>')
    attrs = " ".join(f'data-{k}="{html.escape(str(v), quote=True)}"' for k, v in atributos.items())
    return f'<script src="{html.escape(api, quote=True)}/widget.js" data-api="{html.escape(api, quote=True)}" {attrs} defer></script>' 


def aplicar_preset(nombre: str, ruta: str = RUTA_ESTILOS) -> dict:
    from ipsis.configuracion.glosario import PRESETS as NOMBRES_PRESETS

    nombre = {externo: interno for interno, externo in NOMBRES_PRESETS.items()}.get(nombre, nombre)
    if nombre not in PRESETS:
        raise ValueError(t("styles.unknown_preset", name=nombre,
                           available=", ".join(sorted(NOMBRES_PRESETS.values()))))
    base = _tema_base()
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
    escribir(ruta, tema, "estilos")
    return tema


def generar_vista_previa(
    salida: str = rutas.VISTA_PREVIA,
    ruta_estilos: str = RUTA_ESTILOS,
) -> Path:
    """Genera un mockup autónomo, sin API ni índice, con todos los estados."""
    tema = cargar_estilos(ruta_estilos)
    validar_tema(tema)
    css_tema = render_css(tema=tema)
    preset = str(tema.get("preset") or "personalizado")
    if "</style" in css_tema.lower():
        raise ValueError(t("styles.custom_css_style"))
    preset_html = html.escape(preset)
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
    "PRESETS", "actualizar_estilos", "aplicar_preset", "citas_presentacion", "exportar_widget",
    "generar_vista_previa", "listar_presets", "snippet_widget", "ubicacion_widget", "validar_tema",
]


def _definicion_para_exportar() -> tuple[str, dict] | None:
    """Nombre y definición pública del avatar activo, o ``None`` si no hay uno válido."""
    from ipsis.aplicacion.personalidad import config_avatar_publica, definicion_publica

    try:
        publica = config_avatar_publica()
        if not publica["activo"]:
            return None
        return publica["nombre"], definicion_publica(publica["nombre"])
    except Exception:  # noqa: BLE001 - sin proyecto o sin avatar: se exporta sin él
        return None


def exportar_widget(
    carpeta: str,
    *,
    api: str = "http://127.0.0.1:8000",
    posicion: str = "abajo-derecha",
) -> Path:
    if posicion not in POSICIONES:
        raise ValueError(t("styles.position", values=", ".join(POSICIONES)))
    destino = Path(carpeta).resolve()
    destino.mkdir(parents=True, exist_ok=True)
    estaticos = files("ipsis.servicio").joinpath("estaticos")
    (destino / "widget.js").write_bytes(estaticos.joinpath("widget.js").read_bytes())
    # El motor del avatar, su aviso de licencias y la definición activa (con los
    # colores del proyecto): el widget exportado los carga desde esta carpeta.
    for nombre in ("avatar.js", "avatar.js.LICENSE.txt"):
        (destino / nombre).write_bytes(estaticos.joinpath(nombre).read_bytes())
    avatar_attr = ""
    definicion = _definicion_para_exportar()
    if definicion is not None:
        nombre, datos = definicion
        (destino / "avatares").mkdir(exist_ok=True)
        (destino / "avatares" / f"{nombre}.avatar.json").write_text(json.dumps(datos, ensure_ascii=False),
                                                                     encoding="utf-8")
        avatar_attr = ' avatar-base="."'
    api_attr = html.escape(api.rstrip("/"), quote=True)
    posicion_attr = html.escape(posicion, quote=True)
    snippet = (
        f'<ipsis-chat api="{api_attr}" posicion="{posicion_attr}"{avatar_attr}>'
        "</ipsis-chat>\n"
        '<script src="./widget.js"></script>\n'
    )
    (destino / "snippet.html").write_text(snippet, encoding="utf-8")
    return destino



def actualizar_estilos(cambios: dict, ruta: str = RUTA_ESTILOS) -> dict:
    """Fusiona ``cambios`` (parcial) sobre ``styles.yaml``; valida el tema completo
    antes de escribir (escritura atómica)."""
    if not isinstance(cambios, dict):
        raise ValueError(t("styles.body_object"))
    tema = _fusionar(cargar_estilos(ruta), cambios)
    validar_tema(tema)
    escribir(ruta, tema, "estilos")
    return tema


# --- estilo clave por clave (ipsis widget style, panel /admin) ---------------------------------
# Con los nombres del archivo (inglés): es lo que el usuario escribe y ve.
SECCIONES_EDITABLES = ("presentation", "placement", "colors", "dark_colors", "typography", "shape", "shadows",
                       "animations")


def _tema_base() -> dict:
    from ipsis.configuracion.archivos import interpretar

    return interpretar(leer_plantilla("styles.yaml"), "estilos")


def estilo_plano(tema: dict | None = None) -> list[tuple[str, Any]]:
    """Cada valor editable como ``seccion.clave`` → valor (nombres y valores del archivo):
    lo del proyecto sobre la plantilla."""
    from ipsis.configuracion.glosario import a_externo

    tema = a_externo(_fusionar(_tema_base(), tema if tema is not None else cargar_estilos()), "estilos")
    return [(f"{seccion}.{clave}", valor)
            for seccion in SECCIONES_EDITABLES for clave, valor in (tema.get(seccion) or {}).items()]


def _convertir(texto: str, ejemplo: Any) -> Any:
    """El valor de ``ipsis widget style set`` con el tipo de la plantilla."""
    if isinstance(ejemplo, bool):
        if texto.lower() in ("true", "si", "sí", "1"):
            return True
        if texto.lower() in ("false", "no", "0"):
            return False
        raise ValueError(t("styles.expected_boolean", value=texto))
    if isinstance(ejemplo, int):
        try:
            return int(texto)
        except ValueError as e:
            raise ValueError(t("styles.expected_integer", value=texto)) from e
    return texto


def cambiar_estilo(asignaciones: list[str], ruta: str = RUTA_ESTILOS) -> dict:
    """Aplica ``seccion.clave=valor`` sobre ``styles.yaml``. Solo acepta claves que
    existen en la plantilla, para que una errata no se guarde en silencio, y valida
    el tema completo antes de escribir."""
    from ipsis.configuracion.glosario import a_externo, a_interno

    base = a_externo(_tema_base(), "estilos")
    cambios: dict[str, dict] = {}
    for asignacion in asignaciones:
        clave, separador, valor = asignacion.partition("=")
        seccion, punto, nombre = clave.strip().partition(".")
        if not separador or not punto:
            raise ValueError(t("styles.assignment_form", assignment=asignacion))
        if seccion not in SECCIONES_EDITABLES:
            raise ValueError(t("styles.unknown_section", section=seccion, valid=", ".join(SECCIONES_EDITABLES)))
        validas = base.get(seccion) or {}
        if nombre not in validas:
            raise ValueError(t("styles.unknown_key", key=clave, section=seccion, valid=", ".join(validas)))
        try:
            cambios.setdefault(seccion, {})[nombre] = _convertir(valor.strip(), validas[nombre])
        except ValueError as e:
            raise ValueError(t("styles.key_error", key=clave, error=e)) from e
    if not cambios:
        raise ValueError(t("styles.no_changes"))
    return actualizar_estilos(a_interno(cambios, "estilos"), ruta)


__all__ += ["SECCIONES_EDITABLES", "cambiar_estilo", "estilo_plano"]
