"""Genera ipsis/recursos/avatares/folio.avatar.json, el avatar por defecto.

Folio es una hoja de papel viva: un rectángulo redondeado, levemente inclinado,
con la esquina doblada y dos ojos de tinta. No tiene boca; expresa con los ojos,
el giro de la cabeza y el movimiento ambiental. Encarna el proyecto: lee, mira
la cita antes de afirmar y no exagera (``happy`` es sobrio y en ``unsure`` o
``sorry`` nunca hay gesto de éxito).

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
# Folio está siempre un poco ladeado, como una hoja apoyada.
INCLINACION = -4


def ojo(ancho=18, alto=40, x=0, y=-12, angulo=0):
    return {"width": ancho, "height": alto, "x": x, "y": y, "angle": angulo}


def expresion(cabeza=(0, 0, INCLINACION), izq=None, der=None, separacion=36, ojos="none", cuerpo="none"):
    izq = izq or ojo()
    return {
        "head": {"x": cabeza[0], "y": cabeza[1], "z": cabeza[2]},
        "eyes": {"left": izq, "right": der or deepcopy(izq), "spacing": separacion},
        "perspective": 1,
        "motion": {"eyes": ojos, "body": cuerpo},
    }


EXPRESIONES = {
    "neutral": expresion(),
    "attentive": expresion(cabeza=(4, 0, INCLINACION / 2), izq=ojo(21, 46, y=-14), separacion=38),
    # Lee: la mirada baja hacia las citas.
    "reading": expresion(cabeza=(-14, 0, INCLINACION), izq=ojo(19, 30, y=6), separacion=36),
    # Contento sobrio: ojos entrecerrados en arco, la cabeza apenas arriba.
    "happy": expresion(cabeza=(5, 0, INCLINACION), izq=ojo(23, 20, y=-15, angulo=-12),
                          der=ojo(23, 20, y=-15, angulo=12), separacion=38),
    "kind": expresion(cabeza=(3, -6, INCLINACION - 3), izq=ojo(22, 20, y=-12), separacion=37),
    "unsure": expresion(cabeza=(0, 8, INCLINACION - 8), izq=ojo(18, 40, y=-14),
                        der=ojo(20, 22, y=-10), separacion=36),
    "sorry": expresion(cabeza=(-12, 0, INCLINACION - 2), izq=ojo(20, 30, y=4, angulo=-14),
                         der=ojo(20, 30, y=4, angulo=14), separacion=34),
    "thinking": expresion(cabeza=(10, -14, INCLINACION + 4), izq=ojo(17, 36, x=-6, y=-24), separacion=34,
                          cuerpo="slowDrift"),
    "thinking-side": expresion(cabeza=(8, 14, INCLINACION - 2), izq=ojo(17, 36, x=6, y=-22), separacion=34,
                               cuerpo="slowDrift"),
    "sleepy": expresion(cabeza=(-8, 0, INCLINACION - 4), izq=ojo(22, 6, y=-6), separacion=36),
    "eyes-closed": expresion(cabeza=(-10, 0, INCLINACION - 5), izq=ojo(22, 3, y=-4), separacion=36),
    "surprised": expresion(cabeza=(6, 0, INCLINACION / 2), izq=ojo(24, 50, y=-16), separacion=40),
    "worried": expresion(cabeza=(-4, 0, INCLINACION), izq=ojo(19, 34, y=-10, angulo=12),
                            der=ojo(19, 34, y=-10, angulo=-12), separacion=34, ojos="shake"),
    "nod-down": expresion(cabeza=(-12, 0, INCLINACION), izq=ojo(19, 36, y=-6), separacion=36),
}

PARPADEO = {"enabled": True, "initialDelayMs": 1800, "minIntervalMs": 3200, "maxIntervalMs": 6400, "durationMs": 160}
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
    "idle": animacion("loop", [paso("neutral", 5200, 400), paso("reading", 1800, 500),
                                   paso("neutral", 4200, 500)],
                          etiqueta="idle", descripcion="Breathes; now and then rereads the page."),
    "wave": animacion("once", [paso("attentive", 500, 200, "spring"), paso("kind", 900, 240),
                                 paso("neutral", 300, 300)],
                        etiqueta="wave", descripcion="Straightens up and greets with its eyes."),
    "attentive": animacion("loop", [paso("attentive", 4000, 220)], etiqueta="attentive"),
    "listening": animacion("loop", [paso("attentive", 1400, 200), paso("reading", 700, 260),
                                     paso("attentive", 1200, 260)],
                            etiqueta="listening", descripcion="Follows what is being typed."),
    "nod": animacion("once", [paso("nod-down", 220, 160, "snappy"), paso("attentive", 260, 180),
                                  paso("nod-down", 200, 160, "snappy"), paso("neutral", 200, 200)],
                         etiqueta="nod", descripcion="Got the question."),
    "thinking": animacion("loop", [paso("thinking", 1600, 420), paso("reading", 1200, 420)],
                          etiqueta="thinking", descripcion="Searches the documents."),
    "thinking-long": animacion("loop", [paso("thinking", 1400, 420), paso("thinking-side", 1400, 520),
                                         paso("reading", 1600, 420)],
                                etiqueta="thinking-long", descripcion="The search takes a while: reads more calmly."),
    # Primero mira las citas; recién después se alegra, y sin celebrar.
    "happy": animacion("once", [paso("reading", 700, 260), paso("happy", 1100, 300),
                                   paso("neutral", 300, 360)],
                          etiqueta="happy", descripcion="Checked the citation and found it."),
    "unsure": animacion("once", [paso("reading", 600, 260), paso("unsure", 1400, 320),
                                 paso("neutral", 300, 360)],
                        etiqueta="unsure", descripcion="Found something related, not direct."),
    "sorry": animacion("once", [paso("reading", 500, 260), paso("sorry", 1600, 380),
                                  paso("neutral", 300, 420)],
                         etiqueta="sorry", descripcion="It is not in the documents."),
    "kind": animacion("once", [paso("kind", 1200, 260), paso("neutral", 300, 300)], etiqueta="kind"),
    "goodbye": animacion("once", [paso("kind", 700, 240), paso("eyes-closed", 300, 160),
                                    paso("kind", 600, 200), paso("neutral", 300, 300)],
                           SIN_PARPADEO, etiqueta="goodbye"),
    "worried": animacion("once", [paso("worried", 900, 220), paso("neutral", 300, 360)],
                            etiqueta="worried", descripcion="The connection or the service failed."),
    "sleepy": animacion("loop", [paso("sleepy", 3200, 900), paso("eyes-closed", 2400, 900)],
                             {**PARPADEO, "minIntervalMs": 6000, "maxIntervalMs": 9000, "durationMs": 400},
                             etiqueta="sleepy", descripcion="Nobody has typed for a while."),
    "wake-up": animacion("once", [paso("eyes-closed", 260, 100), paso("surprised", 500, 180, "spring"),
                                    paso("attentive", 400, 240)],
                           SIN_PARPADEO, etiqueta="wake-up"),
}

DEFINICION = {
    "schema": "bible-strong/avatar-definition",
    "schemaVersion": 1,
    "name": "Folio",
    "body": {
        "primary": {"type": "cube", "width": 190, "height": 236, "depth": 22, "roundness": 0.28},
        # La esquina que se levanta: una pieza girada en 3D sobre la esquina superior derecha.
        "nodes": [{"surface": {"type": "cube", "width": 60, "height": 60, "depth": 20, "roundness": 0.3},
                   "position": [64, -88, 14], "rotation": [30, 30, 45]}],
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
