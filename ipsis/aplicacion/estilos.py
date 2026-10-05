"""Traduce ``config/styles.yaml`` a la hoja de estilos que el
widget enlaza en ``GET /estilos.css``.

Consume: el YAML de estilos del despliegue. Produce: una cadena de CSS con
las variables que el widget ya usa, más las reglas derivadas de apagar las
animaciones y el CSS propio del usuario.

Por qué existe este módulo y no un .css a mano: el widget declara sus
valores de repuesto dentro del Shadow DOM, y esta hoja se enlaza DESPUÉS
para redefinir solo lo que el despliegue quiera cambiar. Así una clave
borrada del YAML vuelve sola al valor de fábrica, en vez de dejar el widget
sin estilo. El YAML es además el único archivo que alguien tiene que abrir
para repintar el asistente entero, sin tocar JavaScript ni reconstruir nada.

Nada de lo que hay aquí genera texto que el usuario lea como información del
documento: es presentación pura.
"""
from __future__ import annotations

from ipsis.configuracion import rutas



RUTA_ESTILOS = rutas.ESTILOS

# Cada entrada mapea una clave del YAML a la variable CSS que el widget ya
# consume. Lo que no esté declarado en el YAML simplemente no se emite, y el
# widget se queda con su valor de repuesto.
_COLORES = {
    "acento": "--rw-acento",
    "acento_texto": "--rw-acento-texto",
    "superficie": "--rw-superficie",
    "fondo": "--rw-fondo",
    "texto": "--rw-texto",
    "texto_suave": "--rw-texto-suave",
    "borde": "--rw-borde",
    "aviso": "--rw-aviso",
    "aviso_borde": "--rw-aviso-borde",
    "vivo": "--rw-vivo",
}
_TIPOGRAFIA = {
    "familia": "--rw-fuente",
    "tamano_base": "--rw-tamano-base",
    "tamano_mensaje": "--rw-tamano-mensaje",
    "tamano_cita": "--rw-tamano-cita",
    "tamano_etiqueta": "--rw-tamano-etiqueta",
    "interlineado": "--rw-interlineado",
}
_FORMA = {
    "radio_panel": "--rw-radio-panel",
    "radio_burbuja": "--rw-radio-burbuja",
    "radio_control": "--rw-radio-control",
    "ancho_panel": "--rw-ancho-panel",
    "alto_panel": "--rw-alto-panel",
    "tamano_boton": "--rw-tamano-boton",
    "tamano_icono": "--rw-tamano-icono",
    "separacion": "--rw-separacion",
    "relleno": "--rw-relleno",
}
_ANIMACIONES = {
    "duracion_panel": "--rw-dur-panel",
    "duracion_burbuja": "--rw-dur-burbuja",
    "duracion_control": "--rw-dur-control",
    "duracion_latido": "--rw-dur-latido",
    "curva": "--rw-curva",
    "desplazamiento_entrada": "--rw-desplazamiento-entrada",
    "escala_entrada": "--rw-escala-entrada",
    "escala_hover": "--rw-escala-hover",
}
_SOMBRAS_CLARO = {"panel": "--rw-sombra-panel", "boton": "--rw-sombra-boton"}
_SOMBRAS_OSCURO = {"panel_oscuro": "--rw-sombra-panel", "boton_oscuro": "--rw-sombra-boton"}


def cargar_estilos(ruta: str = RUTA_ESTILOS) -> dict:
    """Lee el YAML de estilos. Si no existe, devuelve un tema vacío: el
    widget se ve entonces con sus valores de repuesto, que es exactamente
    el comportamiento deseado en un proyecto recién creado."""
    from ipsis.configuracion.archivos import leer

    return leer(ruta, "estilos")


def _declaraciones(seccion: dict | None, mapa: dict[str, str]) -> list[str]:
    if not seccion:
        return []
    salida = []
    for clave, variable in mapa.items():
        valor = seccion.get(clave)
        if valor is None or str(valor).strip() == "":
            continue
        salida.append(f"  {variable}:{valor};")
    return salida


def render_css(tema: dict | None = None, ruta: str = RUTA_ESTILOS) -> str:
    """Produce la hoja de estilos completa a partir del tema.

    El orden importa: primero las variables del modo claro, después el
    bloque de modo oscuro (que solo redefine lo que cambie), después las
    reglas de apagado de animaciones y por último el CSS propio del
    usuario, para que pueda sobreescribir cualquier cosa anterior."""
    tema = cargar_estilos(ruta) if tema is None else tema
    partes: list[str] = [
        "/* Generado desde config/styles.yaml -- no editar a mano. */"
    ]

    claras: list[str] = []
    claras += _declaraciones(tema.get("colores"), _COLORES)
    claras += _declaraciones(tema.get("tipografia"), _TIPOGRAFIA)
    claras += _declaraciones(tema.get("forma"), _FORMA)
    claras += _declaraciones(tema.get("sombras"), _SOMBRAS_CLARO)
    animaciones = tema.get("animaciones") or {}
    claras += _declaraciones(animaciones, _ANIMACIONES)
    if claras:
        partes.append(".rw-raiz{\n" + "\n".join(claras) + "\n}")

    oscuras: list[str] = []
    oscuras += _declaraciones(tema.get("colores_oscuro"), _COLORES)
    oscuras += _declaraciones(tema.get("sombras"), _SOMBRAS_OSCURO)
    if oscuras:
        partes.append(
            "@media (prefers-color-scheme:dark){\n.rw-raiz{\n"
            + "\n".join(oscuras)
            + "\n}\n}"
        )

    # `activadas: false` apaga todo el movimiento de una vez, sin tener que
    # poner cada duración en cero a mano.
    if animaciones.get("activadas") is False:
        partes.append(
            ".rw-panel,.rw-msg,.rw-punto{animation:none !important;}\n"
            ".rw-boton,.rw-enviar,.rw-cerrar,.rw-form input{transition:none !important;}\n"
            ".rw-boton:hover,.rw-enviar:hover:not(:disabled){transform:none !important;}"
        )

    extra = str(tema.get("css_extra") or "").strip()
    if extra:
        partes.append("/* css_extra de config/styles.yaml */\n" + extra)

    return "\n\n".join(partes) + "\n"
