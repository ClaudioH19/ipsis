"""Genera rag/recursos/avatares/folio.avatar.json, el avatar por defecto.

Folio es una hoja de papel viva: un rectángulo redondeado, levemente inclinado,
con la esquina doblada y dos ojos de tinta. No tiene boca; expresa con los ojos,
el giro de la cabeza y el movimiento ambiental. Encarna el proyecto: lee, mira
la cita antes de afirmar y no exagera (``contento`` es sobrio y en ``dudoso`` o
``apenado`` nunca hay gesto de éxito).

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
               / "rag/recursos/avatares/folio.avatar.json")

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
    "atento": expresion(cabeza=(4, 0, INCLINACION / 2), izq=ojo(21, 46, y=-14), separacion=38),
    # Lee: la mirada baja hacia las citas.
    "leyendo": expresion(cabeza=(-14, 0, INCLINACION), izq=ojo(19, 30, y=6), separacion=36),
    # Contento sobrio: ojos entrecerrados en arco, la cabeza apenas arriba.
    "contento": expresion(cabeza=(5, 0, INCLINACION), izq=ojo(23, 20, y=-15, angulo=-12),
                          der=ojo(23, 20, y=-15, angulo=12), separacion=38),
    "amable": expresion(cabeza=(3, -6, INCLINACION - 3), izq=ojo(22, 20, y=-12), separacion=37),
    "dudoso": expresion(cabeza=(0, 8, INCLINACION - 8), izq=ojo(18, 40, y=-14),
                        der=ojo(20, 22, y=-10), separacion=36),
    "apenado": expresion(cabeza=(-12, 0, INCLINACION - 2), izq=ojo(20, 30, y=4, angulo=-14),
                         der=ojo(20, 30, y=4, angulo=14), separacion=34),
    "pensando": expresion(cabeza=(10, -14, INCLINACION + 4), izq=ojo(17, 36, x=-6, y=-24), separacion=34,
                          cuerpo="slowDrift"),
    "pensando-lado": expresion(cabeza=(8, 14, INCLINACION - 2), izq=ojo(17, 36, x=6, y=-22), separacion=34,
                               cuerpo="slowDrift"),
    "somnoliento": expresion(cabeza=(-8, 0, INCLINACION - 4), izq=ojo(22, 6, y=-6), separacion=36),
    "ojos-cerrados": expresion(cabeza=(-10, 0, INCLINACION - 5), izq=ojo(22, 3, y=-4), separacion=36),
    "sorprendido": expresion(cabeza=(6, 0, INCLINACION / 2), izq=ojo(24, 50, y=-16), separacion=40),
    "preocupado": expresion(cabeza=(-4, 0, INCLINACION), izq=ojo(19, 34, y=-10, angulo=12),
                            der=ojo(19, 34, y=-10, angulo=-12), separacion=34, ojos="shake"),
    "asentir-abajo": expresion(cabeza=(-12, 0, INCLINACION), izq=ojo(19, 36, y=-6), separacion=36),
}

PARPADEO = {"enabled": True, "initialDelayMs": 1800, "minIntervalMs": 3200, "maxIntervalMs": 6400, "durationMs": 160}
SIN_PARPADEO = {**PARPADEO, "enabled": False}


def paso(expr, hold, trans=260, curva="smooth"):
    return {"expression": expr, "holdMs": hold, "transitionMs": trans, "transition": curva}


def animacion(modo, pasos, parpadeo=PARPADEO, etiqueta="", descripcion=""):
    datos = {"playbackMode": modo, "steps": pasos, "blink": parpadeo}
    if etiqueta:
        datos["metadata"] = {"label": etiqueta, "description": descripcion, "group": "rag-extractivo"}
    return datos


# Transitorios en modo "once" (≥ 600 ms); persistentes en "loop".
ANIMACIONES = {
    "inactivo": animacion("loop", [paso("neutral", 5200, 400), paso("leyendo", 1800, 500),
                                   paso("neutral", 4200, 500)],
                          etiqueta="inactivo", descripcion="Respira; de vez en cuando relee la página."),
    "saludo": animacion("once", [paso("atento", 500, 200, "spring"), paso("amable", 900, 240),
                                 paso("neutral", 300, 300)],
                        etiqueta="saludo", descripcion="Se endereza y saluda con la mirada."),
    "atento": animacion("loop", [paso("atento", 4000, 220)], etiqueta="atento"),
    "escuchando": animacion("loop", [paso("atento", 1400, 200), paso("leyendo", 700, 260),
                                     paso("atento", 1200, 260)],
                            etiqueta="escuchando", descripcion="Sigue lo que se escribe."),
    "asentir": animacion("once", [paso("asentir-abajo", 220, 160, "snappy"), paso("atento", 260, 180),
                                  paso("asentir-abajo", 200, 160, "snappy"), paso("neutral", 200, 200)],
                         etiqueta="asentir", descripcion="Recibió la pregunta."),
    "pensando": animacion("loop", [paso("pensando", 1600, 420), paso("leyendo", 1200, 420)],
                          etiqueta="pensando", descripcion="Busca en los documentos."),
    "pensando-largo": animacion("loop", [paso("pensando", 1400, 420), paso("pensando-lado", 1400, 520),
                                         paso("leyendo", 1600, 420)],
                                etiqueta="pensando-largo", descripcion="La búsqueda tarda: lee con más calma."),
    # Primero mira las citas; recién después se alegra, y sin celebrar.
    "contento": animacion("once", [paso("leyendo", 700, 260), paso("contento", 1100, 300),
                                   paso("neutral", 300, 360)],
                          etiqueta="contento", descripcion="Revisó la cita y la encontró."),
    "dudoso": animacion("once", [paso("leyendo", 600, 260), paso("dudoso", 1400, 320),
                                 paso("neutral", 300, 360)],
                        etiqueta="dudoso", descripcion="Encontró algo relacionado, no directo."),
    "apenado": animacion("once", [paso("leyendo", 500, 260), paso("apenado", 1600, 380),
                                  paso("neutral", 300, 420)],
                         etiqueta="apenado", descripcion="No está en los documentos."),
    "amable": animacion("once", [paso("amable", 1200, 260), paso("neutral", 300, 300)], etiqueta="amable"),
    "despedida": animacion("once", [paso("amable", 700, 240), paso("ojos-cerrados", 300, 160),
                                    paso("amable", 600, 200), paso("neutral", 300, 300)],
                           SIN_PARPADEO, etiqueta="despedida"),
    "preocupado": animacion("once", [paso("preocupado", 900, 220), paso("neutral", 300, 360)],
                            etiqueta="preocupado", descripcion="Falló la conexión o el servicio."),
    "somnoliento": animacion("loop", [paso("somnoliento", 3200, 900), paso("ojos-cerrados", 2400, 900)],
                             {**PARPADEO, "minIntervalMs": 6000, "maxIntervalMs": 9000, "durationMs": 400},
                             etiqueta="somnoliento", descripcion="Nadie escribe desde hace rato."),
    "despertar": animacion("once", [paso("ojos-cerrados", 260, 100), paso("sorprendido", 500, 180, "spring"),
                                    paso("atento", 400, 240)],
                           SIN_PARPADEO, etiqueta="despertar"),
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
