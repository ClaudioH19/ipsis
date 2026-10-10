"""Compara respuestas por caso con F1 y con el commit V4 previo."""
from pathlib import Path
import json
import sys

SALIDA = Path(__file__).resolve().parent
ANTERIOR = SALIDA.parent / "v4"
nombre = sys.argv[1]
informe = {"ronda": nombre, "bases": {}, "objetivos": {}}
for prefijo in ("f1", "corregido"):
    resultado = {"conversaciones": {}, "consultas": {}, "universal": {}}
    for banco in resultado:
        ruta = SALIDA / f"{nombre}-{banco}.json"
        if not ruta.exists():
            continue
        antes = json.loads((ANTERIOR / f"{prefijo}-{banco}.json").read_text(encoding="utf-8"))
        despues = json.loads(ruta.read_text(encoding="utf-8"))
        for perfil, idiomas in despues.items():
            resultado[banco][perfil] = {}
            for idioma, nuevo in idiomas.items():
                viejo = antes[perfil][idioma]
                if banco == "conversaciones":
                    clave = lambda t: f"{t['conversacion']}:{t['turno']}"
                    a = {clave(t): t for t in viejo["turnos"]}
                    b = {clave(t): t for t in nuevo["turnos"]}
                    correcta = lambda t: t["correcta"]
                    erronea = lambda t: t["directa"] and (t["directa_esperada"] is False or bool(t["respuesta"]) and not t["correcta"])
                    resumen = {"antes": viejo["resumen"], "despues": nuevo["resumen"]}
                else:
                    a, b = viejo["casos"], nuevo["casos"]
                    correcta = lambda t: t["directa"] and not t["falso_ok"] and not t["sin_literal"]
                    erronea = lambda t: t["directa"] and (t["falso_ok"] or t["sin_literal"])
                    resumen = {"correctas": [viejo["correctas"], nuevo["correctas"]], "erroneas": [viejo["erroneas"], nuevo["erroneas"]]}
                assert a.keys() == b.keys()
                resumen.update(
                    perdidas=[k for k in a if correcta(a[k]) and not correcta(b[k])],
                    ganancias=[k for k in a if not correcta(a[k]) and correcta(b[k])],
                    errores_nuevos=[k for k in a if not erronea(a[k]) and erronea(b[k])],
                    errores_corregidos=[k for k in a if erronea(a[k]) and not erronea(b[k])],
                    cambios_estado={k: [a[k]["estado"], b[k]["estado"]] for k in a if a[k]["estado"] != b[k]["estado"]},
                )
                resultado[banco][perfil][idioma] = resumen
                print(prefijo, banco, perfil, idioma, "perdidas", resumen["perdidas"], "errores nuevos", resumen["errores_nuevos"], flush=True)
    informe["bases"][prefijo] = resultado
conversaciones = SALIDA / f"{nombre}-conversaciones.json"
if conversaciones.exists():
    datos = json.loads(conversaciones.read_text(encoding="utf-8"))
    objetivos = {"light": {"pt": ["pt-conv-003:2", "pt-conv-016:2"]},
                 "medium": {"es": ["es-conv-004:3", "es-conv-007:3", "es-conv-013:3"],
                            "en": ["en-conv-010:3", "en-conv-013:3"], "pt": ["pt-conv-007:3"]}}
    for perfil, idiomas in objetivos.items():
        for idioma, ids in idiomas.items():
            turnos = {f"{t['conversacion']}:{t['turno']}": t for t in datos[perfil][idioma]["turnos"]}
            for id in ids:
                informe["objetivos"][f"{perfil}/{id}"] = {"correcta": turnos[id]["correcta"], "tramo": turnos[id]["tramo_lector"]}
(SALIDA / f"{nombre}-comparacion.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("OBJETIVOS", json.dumps(informe["objetivos"], ensure_ascii=False), flush=True)
