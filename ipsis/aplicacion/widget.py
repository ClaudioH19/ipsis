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


def mensajes_de_orientacion(idioma: str) -> dict:
    """Presentación fija de v2: etiquetas y mensajes, independiente del corpus."""
    from ipsis.lenguaje.voz import voz_del_widget

    return voz_del_widget(idioma)


def contenido_publico(tema: dict) -> dict:
    """Textos del widget con las claves públicas, sin exponer el glosario al HTTP."""
    from ipsis.configuracion.glosario import a_externo

    return a_externo({"contenido": tema.get("contenido") or {}}, "estilos")["content"]


# Pilas del sistema: sin descargar tipografías (el widget no pide recursos a terceros).
_SANS_INSTITUCIONAL = "'Segoe UI Variable Text', 'Segoe UI', system-ui, -apple-system, Roboto, 'Helvetica Neue', Arial, sans-serif"
_SERIF_EDITORIAL = "'Iowan Old Style', 'Palatino Linotype', Palatino, 'Book Antiqua', Georgia, serif"

PRESETS: dict[str, dict[str, Any]] = {
    "clasico": {
        "tema": {},
    },
    "minimal": {
        "tema": {
            "colores": {"acento": "#334155", "fondo": "#f8fafc", "borde": "#e2e8f0"},
            "colores_oscuro": {"acento": "#cbd5e1", "acento_texto": "#0f172a"},
            "forma": {"radio_panel": "12px", "radio_burbuja": "10px", "radio_control": "8px"},
            "sombras": {"panel": "0 8px 28px rgba(15,23,42,.12)", "boton": "0 5px 16px rgba(15,23,42,.2)"},
            "presentacion": {"densidad": "compacta", "citas": "acordeon", "diseno_resultados": "lineas"},
        },
    },
    "editorial": {
        "tema": {
            "colores": {
                "acento": "#8f1d2c", "acento_texto": "#fff8f0", "superficie": "#fffefb", "fondo": "#f4efe6",
                "texto": "#1c1917", "texto_suave": "#6a6259", "borde": "#d8cfc2", "aviso": "#8a5a18", "aviso_borde": "#b9812d",
                "borde_resultado": "#cfc4b5",
            },
            "colores_oscuro": {"acento": "#e8a0a9", "acento_texto": "#2a0c10", "superficie": "#201c19", "fondo": "#171412",
                                "texto": "#f1ebe2", "texto_suave": "#b5aa9d", "borde": "#3c342d", "borde_resultado": "#4a4037"},
            "tipografia": {"familia": _SANS_INSTITUCIONAL, "familia_titulo": _SERIF_EDITORIAL, "interlineado": "1.6",
                           "tamano_titulo": "21px", "peso_titulo": "600", "tamano_cita": "12px"},
            "forma": {"radio_panel": "4px", "radio_burbuja": "2px", "radio_control": "2px", "radio_resultado": "0px",
                      "relleno_resultado": "4px", "separacion_resultado": "0px"},
            "sombras": {"panel": "0 1px 2px rgba(28,25,23,.06), 0 14px 36px -14px rgba(28,25,23,.26)",
                        "boton": "0 6px 18px rgba(28,25,23,.26)"},
            "presentacion": {"densidad": "comoda", "citas": "lista", "alineacion": "inicio", "diseno_resultados": "editorial"},
        },
    },
    "contraste": {
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
            "forma": {"radio_panel": "0px", "radio_burbuja": "0px", "radio_control": "0px", "radio_resultado": "0px"},
            "animaciones": {"activadas": False},
            "presentacion": {"mostrar_etiqueta_estado": True},
        },
    },
    "buscador": {
        "tema": {
            "colores_oscuro": {"acento": "#a8c7fa", "acento_texto": "#202124",
                               "texto": "#e8eaed", "texto_suave": "#bdc1c6", "titulo": "var(--rw-acento)"},
            "colores": {"acento": "#1a0dab", "fondo": "#ffffff", "superficie": "#ffffff",
                        "texto": "#202124", "texto_suave": "#5f6368", "borde": "#dadce0", "titulo": "var(--rw-acento)"},
            "tipografia": {"familia": "Arial, sans-serif", "interlineado": "1.5", "tamano_titulo": "20px", "peso_titulo": "400"},
            "forma": {"radio_panel": "12px", "radio_control": "24px"},
            "ubicacion": {"tamano": "amplio"},
            "presentacion": {"densidad": "comoda", "alineacion": "justificada", "citas": "acordeon", "diseno_resultados": "lineas"},
        },
    },
    "buscador_compacto": {
        "tema": {
            "colores": {"acento": "#1a0dab", "fondo": "#ffffff", "superficie": "#ffffff",
                        "texto": "#202124", "texto_suave": "#5f6368", "borde": "#dadce0"},
            "colores_oscuro": {"acento": "#a8c7fa", "acento_texto": "#202124"},
            "tipografia": {"familia": "Arial, sans-serif", "interlineado": "1.45", "tamano_titulo": "18px"},
            "forma": {"radio_panel": "8px", "radio_control": "20px"},
            "presentacion": {"densidad": "compacta", "alineacion": "justificada", "citas": "acordeon", "diseno_resultados": "lineas"},
        },
    },
    "oceano": {
        "tema": {
            "colores": {
                "acento": "#12355b", "acento_texto": "#ffffff", "superficie": "#ffffff", "fondo": "#f2f5f9",
                "texto": "#14202e", "texto_suave": "#566579", "borde": "#d3dbe6", "borde_resultado": "#d3dbe6",
                "titulo": "#12355b", "seccion": "#35516f",
            },
            "colores_oscuro": {"acento": "#8fb4e3", "acento_texto": "#0b1a2c", "superficie": "#131c28", "fondo": "#0d141d",
                               "texto": "#e6ecf4", "texto_suave": "#9fb0c4", "borde": "#2a3646", "borde_resultado": "#2a3646",
                               "titulo": "#c5d9f2", "seccion": "#8fb4e3"},
            "tipografia": {"familia": _SANS_INSTITUCIONAL, "familia_titulo": _SANS_INSTITUCIONAL, "interlineado": "1.55",
                           "tamano_titulo": "16px", "peso_titulo": "650"},
            "forma": {"radio_panel": "4px", "radio_burbuja": "2px", "radio_control": "2px", "radio_resultado": "2px",
                      "separacion_resultado": "12px", "relleno_resultado": "14px"},
            "sombras": {"panel": "0 1px 2px rgba(10,25,47,.08), 0 16px 40px -16px rgba(10,25,47,.32)",
                        "boton": "0 6px 18px rgba(10,25,47,.3)"},
            "presentacion": {"densidad": "comoda", "citas": "acordeon", "diseno_resultados": "tarjetas"},
        },
    },
    "bosque": {
        "tema": {
            "colores": {
                "acento": "#1f5a3b", "acento_texto": "#f6fbf7", "superficie": "#fcfdfb", "fondo": "#eff3ee",
                "texto": "#161d18", "texto_suave": "#5c685f", "borde": "#d0dbd0", "borde_resultado": "#c3d1c4",
            },
            "colores_oscuro": {"acento": "#8fd0a6", "acento_texto": "#0c2216", "superficie": "#17211b", "fondo": "#0f1612",
                               "texto": "#e8efe9", "texto_suave": "#a5b3a8", "borde": "#2f3f34", "borde_resultado": "#3a4d3f"},
            "tipografia": {"familia": _SANS_INSTITUCIONAL, "familia_titulo": _SERIF_EDITORIAL, "interlineado": "1.6",
                           "tamano_titulo": "21px", "peso_titulo": "600", "tamano_cita": "12px"},
            "forma": {"radio_panel": "4px", "radio_burbuja": "2px", "radio_control": "2px", "radio_resultado": "0px",
                      "relleno_resultado": "4px", "separacion_resultado": "0px"},
            "sombras": {"panel": "0 1px 2px rgba(22,29,24,.06), 0 14px 36px -14px rgba(22,29,24,.26)",
                        "boton": "0 6px 18px rgba(22,29,24,.26)"},
            "presentacion": {"densidad": "comoda", "citas": "lista", "alineacion": "inicio", "diseno_resultados": "editorial"},
        },
    },
    "medianoche": {
        "tema": {
            "colores": {"acento": "#d9b86c", "acento_texto": "#1a1406", "superficie": "#161d27", "fondo": "#0e131a",
                        "texto": "#e6ebf2", "texto_suave": "#98a5b6", "borde": "#273140", "borde_resultado": "#2d3949",
                        "titulo": "#f2f5f9", "seccion": "#d9b86c"},
            "colores_oscuro": {"acento": "#d9b86c", "acento_texto": "#1a1406", "superficie": "#161d27", "fondo": "#0e131a",
                               "texto": "#e6ebf2", "texto_suave": "#98a5b6", "borde": "#273140", "borde_resultado": "#2d3949",
                               "titulo": "#f2f5f9", "seccion": "#d9b86c"},
            "tipografia": {"familia": _SANS_INSTITUCIONAL, "familia_titulo": _SANS_INSTITUCIONAL, "interlineado": "1.55",
                           "tamano_titulo": "16px", "peso_titulo": "650"},
            "forma": {"radio_panel": "4px", "radio_burbuja": "2px", "radio_control": "2px", "radio_resultado": "2px",
                      "separacion_resultado": "12px", "relleno_resultado": "14px"},
            "sombras": {"panel": "0 1px 2px rgba(0,0,0,.4), 0 18px 44px -14px rgba(0,0,0,.65)",
                        "boton": "0 6px 18px rgba(0,0,0,.5)",
                        "panel_oscuro": "0 1px 2px rgba(0,0,0,.4), 0 18px 44px -14px rgba(0,0,0,.65)",
                        "boton_oscuro": "0 6px 18px rgba(0,0,0,.5)"},
            "presentacion": {"densidad": "comoda", "citas": "acordeon", "diseno_resultados": "tarjetas"},
        },
    },
}

_SECCIONES = {"colores", "colores_oscuro", "tipografia", "forma", "sombras", "animaciones"}


def listar_presets() -> dict[str, str]:
    """Nombre del preset (como en ``styles.yaml``) → su descripción en el idioma de la interfaz."""
    from ipsis.configuracion.glosario import PRESETS as NOMBRES_PRESETS

    return {NOMBRES_PRESETS[nombre]: t(f"presets.{NOMBRES_PRESETS[nombre]}") for nombre in PRESETS}


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
    if presentacion.get("alineacion", "justificada") not in {"inicio", "justificada"}:
        raise ValueError(t("styles.text_align"))
    if presentacion.get("diseno_resultados", "tarjetas") not in {"tarjetas", "lineas", "editorial"}:
        raise ValueError(t("styles.result_layout"))
    for clave in ("mostrar_numeros", "mostrar_ruta", "expandir_contexto", "mostrar_sugerencias"):
        if not isinstance(presentacion.get(clave, True), bool):
            raise ValueError(t("styles.expected_boolean", value=_externo("presentacion." + clave)))
    contenido = tema.get("contenido", {})
    if not isinstance(contenido, dict):
        raise ValueError(t("styles.section_object", section="content"))
    for clave, valor in contenido.items():
        if clave not in {"titulo", "subtitulo", "titulo_inicio", "texto_inicio"} or not isinstance(valor, str):
            raise ValueError(t("styles.content_text"))
    ubicacion_widget(tema)  # valida tema.ubicacion
    render_css(tema=tema)


POSICIONES = ("abajo-derecha", "abajo-izquierda", "arriba-derecha", "arriba-izquierda", "incrustado")
TAMANOS = ("compacto", "normal", "amplio")
LANZADORES = ("burbuja", "pestana", "oculto")
UBICACION_POR_DEFECTO = {"posicion": "abajo-derecha", "desplazamiento_x": 24, "desplazamiento_y": 24,
                         "z_index": 2147483000, "tamano": "normal", "lanzador": "burbuja"}


def citas_presentacion(valor: str | None) -> str:
    """``acordeon`` o ``lista`` (también en inglés: ``accordion`` o ``list``); los valores
    anteriores no ocultan las citas."""
    if valor in ("accordion", "list"):
        return "list" if valor == "list" else "accordion"
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


def ubicacion_publica(ubicacion: dict) -> dict:
    """``ubicacion_widget`` con los nombres del archivo (``placement``): lo que publica /config."""
    from ipsis.configuracion.glosario import a_externo

    return a_externo({"ubicacion": ubicacion}, "estilos")["placement"]


def presentacion_publica(tema: dict) -> dict:
    """``preset`` y ``presentation`` del tema con los nombres y valores del archivo."""
    from ipsis.configuracion.glosario import a_externo

    externo = a_externo({"preset": tema.get("preset") or "clasico", "presentacion": tema.get("presentacion") or {}},
                        "estilos")
    presentacion = externo.get("presentation") or {}
    diseno_defecto = PRESETS.get(tema.get("preset"), {}).get("tema", {}).get("presentacion", {}).get(
        "diseno_resultados", "tarjetas")
    diseno_defecto = {"tarjetas": "cards", "lineas": "lines", "editorial": "editorial"}[diseno_defecto]
    return {"preset": externo["preset"], "density": presentacion.get("density", "comfortable"),
            "citations": presentacion.get("citations", "accordion"),
            "show_status_label": presentacion.get("show_status_label", True),
            "text_align": presentacion.get("text_align", "justify"),
            "result_layout": presentacion.get("result_layout", diseno_defecto),
            "show_result_numbers": presentacion.get("show_result_numbers", True),
            "show_section_path": presentacion.get("show_section_path", True),
            "expand_context": presentacion.get("expand_context", False),
            "show_suggestions": presentacion.get("show_suggestions", True)}


def snippet_widget(api: str, *, componente: bool = False, clave_widget: str | None = None) -> str:
    """Etiqueta lista para pegar en el sitio, según ``styles.yaml::placement``."""
    u = ubicacion_publica(ubicacion_widget())
    api = api.rstrip("/")
    atributos = {"position": u["position"], "size": u["size"], "launcher": u["launcher"],
                 "offset-x": u["offset_x"], "offset-y": u["offset_y"]}
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
    if "contenido" in actual:
        tema["contenido"] = deepcopy(actual["contenido"])
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
    """Genera una vista autónoma del widget real con datos de ejemplo, sin API ni índice."""
    tema = cargar_estilos(ruta_estilos)
    validar_tema(tema)
    css_tema = render_css(tema=tema)
    from ipsis.aplicacion.vista_widget import vista_widget

    if "</style" in css_tema.lower():
        raise ValueError(t("styles.custom_css_style"))
    destino = Path(salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(vista_widget(tema, css_tema, presentacion_publica(tema)), encoding="utf-8")
    return destino


__all__ = [
    "PRESETS", "actualizar_estilos", "aplicar_preset", "citas_presentacion", "exportar_widget",
    "generar_vista_previa", "listar_presets", "mensajes_de_orientacion", "snippet_widget", "ubicacion_widget", "validar_tema",
]


def _definicion_para_exportar() -> tuple[str, dict] | None:
    """Nombre y definición pública del avatar activo, o ``None`` si no hay uno válido."""
    from ipsis.aplicacion.personalidad import config_avatar_publica, definicion_publica

    try:
        publica = config_avatar_publica()
        if not publica["enabled"]:
            return None
        return publica["name"], definicion_publica(publica["name"])
    except Exception:  # noqa: BLE001 - sin proyecto o sin avatar: se exporta sin él
        return None


def exportar_widget(
    carpeta: str,
    *,
    api: str = "http://127.0.0.1:8000",
    posicion: str = "bottom-right",
) -> Path:
    from ipsis.configuracion.glosario import POSICIONES as NOMBRES_POSICIONES

    posicion = {externo: interno for interno, externo in NOMBRES_POSICIONES.items()}.get(posicion, posicion)
    if posicion not in POSICIONES:
        raise ValueError(t("styles.position", values=", ".join(NOMBRES_POSICIONES.values())))
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
        (destino / "avatars").mkdir(exist_ok=True)
        (destino / "avatars" / f"{nombre}.avatar.json").write_text(json.dumps(datos, ensure_ascii=False),
                                                                     encoding="utf-8")
        avatar_attr = ' avatar-base="."'
    api_attr = html.escape(api.rstrip("/"), quote=True)
    posicion_attr = html.escape(ubicacion_publica({"posicion": posicion})["position"], quote=True)
    snippet = (
        f'<ipsis-chat api="{api_attr}" position="{posicion_attr}"{avatar_attr}>'
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
SECCIONES_EDITABLES = ("presentation", "content", "placement", "colors", "dark_colors", "typography", "shape", "shadows",
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
