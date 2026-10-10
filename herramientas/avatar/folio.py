"""Genera ipsis/recursos/avatares/folio.avatar.json, el avatar por defecto.

Folio es la hoja del logo (``docs/assets/logo.svg``) hecha avatar: un papel
apenas redondeado e inclinado, con la esquina superior doblada, dos ojos de
tinta en forma de píldora y dos renglones de texto. No tiene boca; expresa con
los ojos (forma, ángulo, hacia dónde miran), el giro de la cabeza y el
movimiento ambiental. Encarna el proyecto: lee, mira la cita antes de afirmar
y no exagera (``happy`` se alegra recién después de leer, y en ``unsure`` o
``sorry`` nunca hay gesto de éxito).

El renderer ``herramientas/avatar/folio.js`` dibuja la silueta y las piezas
del logo en SVG; la librería controla las transiciones y el parpadeo. Los
avatares importados conservan el renderer procedural de la librería.

    python herramientas/avatar/folio.py           # escribe el JSON
    node herramientas/avatar/validar.mjs          # lo valida con la librería

Se versiona el JSON generado; este script documenta cómo se hizo.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

# FOLIO_DESTINO permite escribir en otra ruta (para revisar variantes sin tocar el paquete).
DESTINO = Path(os.environ.get("FOLIO_DESTINO") or Path(__file__).resolve().parents[2]
               / "ipsis/recursos/avatares/folio.avatar.json")

# Cabeza: x = cabeceo (negativo, mira abajo), y = giro, z = inclinación lateral.
# Folio está siempre un poco ladeado, como la hoja del logo (-5°).
INCLINACION = -5

# Proporciones del logo: la hoja mide 78 × 92 y cada ojo 9 × 20, con los
# centros a 21 de distancia y a un 39 % de la altura.
ANCHO, ALTO, GROSOR = 196, 232, 20


def ojo(ancho=9 * ANCHO / 78, alto=20 * ANCHO / 78, x=0, y=-10 * ANCHO / 78, angulo=0):
    return {"width": ancho, "height": alto, "x": x, "y": y, "angle": angulo}


def expresion(cabeza=(0, 0, INCLINACION), izq=None, der=None, separacion=21 * ANCHO / 78, ojos="none", cuerpo="none"):
    izq = izq or ojo()
    return {
        "head": {"x": cabeza[0], "y": cabeza[1], "z": cabeza[2]},
        "eyes": {"left": izq, "right": der or deepcopy(izq), "spacing": separacion},
        "perspective": 1,
        "motion": {"eyes": ojos, "body": cuerpo},
    }


def par(izq, der, **kwargs):
    return expresion(izq=izq, der=der, **kwargs)


EXPRESIONES = {
    "neutral": expresion(),
    # Atento: los ojos se abren y la hoja se endereza.
    "attentive": expresion(cabeza=(6, 0, 0), izq=ojo(27, 64, y=-28), separacion=52),
    # Lee: la mirada baja hacia los renglones y recorre la línea.
    "reading": expresion(cabeza=(-9, 0, INCLINACION), izq=ojo(24, 34, y=8), separacion=48,
                         ojos="microSaccades"),
    # Contento sobrio: ojos en arco («^ ^»), la cabeza arriba y ladeada.
    "happy": par(ojo(34, 16, y=-32, angulo=-32), ojo(34, 16, y=-32, angulo=32),
                 cabeza=(10, 0, INCLINACION + 9), separacion=54),
    "kind": par(ojo(30, 20, y=-24, angulo=-14), ojo(30, 20, y=-24, angulo=14),
                cabeza=(4, -10, INCLINACION - 9), separacion=50),
    # Duda: un ojo abierto y el otro entornado, la hoja muy ladeada.
    "unsure": par(ojo(24, 58, y=-28), ojo(28, 24, y=-20, angulo=12),
                  cabeza=(0, 14, INCLINACION - 14), separacion=50),
    # Apenado: los ojos caen hacia afuera y la hoja se inclina hacia abajo.
    "sorry": par(ojo(26, 34, y=4, angulo=26), ojo(26, 34, y=4, angulo=-26),
                 cabeza=(-9, 0, INCLINACION - 10), separacion=44),
    "thinking": expresion(cabeza=(14, -18, INCLINACION + 6), izq=ojo(22, 50, x=-14, y=-40), separacion=46,
                          cuerpo="slowDrift"),
    "thinking-side": expresion(cabeza=(12, 18, INCLINACION - 4), izq=ojo(22, 50, x=14, y=-38), separacion=46,
                               cuerpo="slowDrift"),
    "sleepy": expresion(cabeza=(-8, 0, INCLINACION - 10), izq=ojo(30, 7, y=-12), separacion=50),
    "eyes-closed": expresion(cabeza=(-9, 0, INCLINACION - 10), izq=ojo(30, 4, y=-10), separacion=50),
    "surprised": expresion(cabeza=(10, 0, 0), izq=ojo(32, 72, y=-30), separacion=56),
    # Preocupado: ojos que suben hacia el centro y tiemblan.
    "worried": par(ojo(24, 44, y=-18, angulo=-18), ojo(24, 44, y=-18, angulo=18),
                   cabeza=(-6, 0, INCLINACION + 4), separacion=44, ojos="shake"),
    "nod-down": expresion(cabeza=(-10, 0, INCLINACION), izq=ojo(25, 44, y=-8), separacion=50),
    # Nuevas: miradas a los lados (el reposo se ve vivo), curiosidad y guiño.
    "look-left": expresion(cabeza=(0, -14, INCLINACION), izq=ojo(25, 56, x=-16, y=-24), separacion=50),
    "look-right": expresion(cabeza=(0, 14, INCLINACION), izq=ojo(25, 56, x=16, y=-24), separacion=50),
    "curious": par(ojo(26, 64, y=-30), ojo(25, 46, y=-22),
                   cabeza=(6, 10, INCLINACION + 12), separacion=50),
    "wink": par(ojo(30, 5, y=-20), ojo(27, 60, y=-26),
                cabeza=(6, -6, INCLINACION + 8), separacion=52),
}

PARPADEO = {"enabled": True, "initialDelayMs": 1800, "minIntervalMs": 3000, "maxIntervalMs": 6000, "durationMs": 160}
SIN_PARPADEO = {**PARPADEO, "enabled": False}


def paso(expr, hold, trans=260, curva="smooth"):
    return {"expression": expr, "holdMs": hold, "transitionMs": trans, "transition": curva}


def animacion(modo, pasos, parpadeo=PARPADEO, etiqueta="", descripcion=""):
    datos = {"playbackMode": modo, "steps": pasos, "blink": parpadeo}
    if etiqueta:
        datos["metadata"] = {"label": etiqueta, "description": descripcion, "group": "ipsis"}
    return datos


# Transitorios en modo "once" (≥ 600 ms); persistentes en "loop".
ANIMACIONES = {
    "idle": animacion("loop", [paso("neutral", 4200, 400), paso("look-left", 900, 420),
                               paso("neutral", 2600, 420), paso("reading", 1800, 500),
                               paso("neutral", 3200, 500), paso("look-right", 900, 420),
                               paso("neutral", 2400, 420)],
                      etiqueta="idle", descripcion="Breathes, glances around and now and then rereads the page."),
    "wave": animacion("once", [paso("attentive", 400, 200, "spring"), paso("wink", 500, 180, "snappy"),
                               paso("kind", 800, 240), paso("neutral", 300, 300)],
                      etiqueta="wave", descripcion="Straightens up, winks and greets with its eyes."),
    "attentive": animacion("loop", [paso("attentive", 4000, 220)], etiqueta="attentive"),
    "listening": animacion("loop", [paso("attentive", 1300, 200), paso("curious", 900, 260),
                                    paso("reading", 700, 260), paso("attentive", 1100, 260)],
                           etiqueta="listening", descripcion="Follows what is being typed."),
    "nod": animacion("once", [paso("nod-down", 220, 160, "snappy"), paso("attentive", 260, 180),
                              paso("nod-down", 200, 160, "snappy"), paso("neutral", 200, 200)],
                     etiqueta="nod", descripcion="Got the question."),
    "thinking": animacion("loop", [paso("thinking", 1500, 420), paso("reading", 1200, 420),
                                   paso("thinking-side", 1300, 520)],
                          etiqueta="thinking", descripcion="Searches the documents."),
    "thinking-long": animacion("loop", [paso("thinking", 1400, 420), paso("thinking-side", 1400, 520),
                                        paso("reading", 1600, 420), paso("curious", 800, 360)],
                               etiqueta="thinking-long", descripcion="The search takes a while: reads more calmly."),
    # Primero mira las citas; recién después se alegra, y sin celebrar.
    "happy": animacion("once", [paso("reading", 700, 260), paso("happy", 1300, 300, "spring"),
                                paso("neutral", 300, 360)],
                       etiqueta="happy", descripcion="Checked the citation and found it."),
    "unsure": animacion("once", [paso("reading", 600, 260), paso("unsure", 1600, 320),
                                 paso("neutral", 300, 360)],
                        etiqueta="unsure", descripcion="Found something related, not direct."),
    "sorry": animacion("once", [paso("reading", 500, 260), paso("sorry", 1800, 380),
                                paso("neutral", 300, 420)],
                       etiqueta="sorry", descripcion="It is not in the documents."),
    "kind": animacion("once", [paso("kind", 1300, 260), paso("neutral", 300, 300)], etiqueta="kind"),
    "goodbye": animacion("once", [paso("kind", 600, 240), paso("wink", 600, 180, "snappy"),
                                  paso("kind", 500, 200), paso("neutral", 300, 300)],
                         SIN_PARPADEO, etiqueta="goodbye"),
    "worried": animacion("once", [paso("worried", 1100, 220), paso("neutral", 300, 360)],
                         etiqueta="worried", descripcion="The connection or the service failed."),
    "sleepy": animacion("loop", [paso("sleepy", 3200, 900), paso("eyes-closed", 2400, 900)],
                        {**PARPADEO, "minIntervalMs": 6000, "maxIntervalMs": 9000, "durationMs": 400},
                        etiqueta="sleepy", descripcion="Nobody has typed for a while."),
    "wake-up": animacion("once", [paso("eyes-closed", 260, 100), paso("surprised", 600, 180, "spring"),
                                  paso("attentive", 400, 240)],
                         SIN_PARPADEO, etiqueta="wake-up"),
    # Movimientos de la hoja completa: la trayectoria vive en movimiento-folio.js.
    # Se ofrecen para configurar eventos; el mapa por defecto conserva sus gestos.
    "spin": animacion("once", [paso("neutral", 1800, 0)], SIN_PARPADEO,
                      etiqueta="spin", descripcion="One complete 360-degree turn."),
    "flip": animacion("once", [paso("neutral", 2000, 0)], SIN_PARPADEO,
                      etiqueta="flip", descripcion="Turns around its vertical axis, showing the back of the page."),
    "bounce": animacion("once", [paso("neutral", 1500, 0)], SIN_PARPADEO,
                        etiqueta="bounce", descripcion="Two small jumps with a soft squash and stretch."),
    "sway": animacion("loop", [paso("neutral", 2600, 0)],
                      etiqueta="sway", descripcion="Rocks from side to side."),
    "dance": animacion("loop", [paso("happy", 2100, 300)],
                       etiqueta="dance", descripcion="Steps sideways, bobs and rocks with happy eyes."),
    "float": animacion("loop", [paso("neutral", 4000, 0)],
                       etiqueta="float", descripcion="Floats gently up and down."),
    "paper-plane-out": animacion("once", [paso("neutral", 3200, 0)], SIN_PARPADEO,
                                 etiqueta="paper-plane-out", descripcion="Folds into a paper plane and flies away with the question."),
    "paper-plane-in": animacion("once", [paso("neutral", 3200, 0)], SIN_PARPADEO,
                                etiqueta="paper-plane-in", descripcion="Flies in with a citation, lands and unfolds into Folio."),
}


def renglon(ancho, x, y, alto=12):
    """Un renglón de texto pegado a la cara de la hoja."""
    return {"surface": {"type": "cube", "width": ancho, "height": alto, "depth": 3, "roundness": 0.5},
            "position": [x, y, GROSOR / 2 + 4], "rotation": [0, 0, 0]}


DEFINICION = {
    "schema": "bible-strong/avatar-definition",
    "schemaVersion": 1,
    "name": "Folio",
    "body": {
        "primary": {"type": "cube", "width": ANCHO, "height": ALTO, "depth": GROSOR, "roundness": 0.2},
        "nodes": [
            # La esquina doblada del logo: un triángulo (un cono aplanado visto de frente)
            # con la base sobre la diagonal de la esquina y la punta hacia adentro.
            {"surface": {"type": "cone", "width": 60, "height": 30, "depth": 3, "roundness": 0.1},
             "position": [ANCHO / 2 - 24, -ALTO / 2 + 24, GROSOR / 2 + 4], "rotation": [0, 0, -45]},
            # Los renglones del logo: uno largo y, debajo, uno medio y uno corto.
            renglon(128, 0, 44),
            renglon(82, -22, 74, alto=20),
            renglon(34, 50, 74),
        ],
    },
    "colors": {"body": "#f5f1e8", "eyes": "#1e293b"},
    "expressions": EXPRESIONES,
    "expressionOrder": list(EXPRESIONES),
    "animations": ANIMACIONES,
    "animationOrder": list(ANIMACIONES),
}


def main() -> None:
    DESTINO.write_text(json.dumps(DEFINICION, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{DESTINO.name}: {len(EXPRESIONES)} expresiones, {len(ANIMACIONES)} animaciones")


if __name__ == "__main__":
    main()
