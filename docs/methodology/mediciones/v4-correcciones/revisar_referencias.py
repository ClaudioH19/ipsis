"""Audita puntajes y el único cambio de evidencia relacionada ya revisado."""
from pathlib import Path
import json
import subprocess

SALIDA = Path(__file__).resolve().parent
RAIZ = SALIDA.parents[3]
informe = {}
for perfil in ("light", "medium"):
    ruta = f"tests/datos/caracterizacion/{perfil}.json"
    previo = json.loads(subprocess.run(["git", "show", f"b23ad8a:{ruta}"], cwd=RAIZ, check=True,
                                     capture_output=True, encoding="utf-8").stdout)
    actual = json.loads((RAIZ / ruta).read_text(encoding="utf-8"))
    assert previo.keys() == actual.keys()
    filas = []
    presentacion = []
    for pregunta in previo:
        a, b = json.loads(json.dumps(previo[pregunta])), json.loads(json.dumps(actual[pregunta]))
        ca, cb = a.pop("confidence"), b.pop("confidence")
        sa = [f.pop("score") for f in a["fragments"]]
        sb = [f.pop("score") for f in b["fragments"]]
        if a != b:
            # El lector actual deja de ofrecer la oración del filtro como
            # evidencia del precio ausente. Mantiene related, sin respuesta
            # exacta; los offsets siguen siendo literales (prueba HTTP).
            assert perfil == "medium" and pregunta == "¿Cuánto cuesta el purificador?", (perfil, pregunta)
            assert a["status"] == b["status"] == "related"
            assert a["service_level"] == b["service_level"] and a["plan"] == b["plan"]
            presentacion.append({"pregunta": pregunta, "antes": a, "actual": b,
                                 "causa": "El lector usa la pregunta actual y deja de escoger una oración del filtro para un precio que el corpus no informa; cae a evidencia relacionada."})
        if ca != cb or sa != sb:
            filas.append({"pregunta": pregunta, "confianza_antes": ca, "confianza_actual": cb,
                          "scores_fragmentos_antes": sa, "scores_fragmentos_actuales": sb})
    informe[perfil] = {"solo_puntajes": not presentacion, "cambios": filas, "presentacion_relacionada": presentacion}
(SALIDA / "referencias-http.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(informe, ensure_ascii=False, indent=2), flush=True)
