"""Tablas y caracterización por caso de la ronda final; conserva las bases."""
from pathlib import Path
import json

SALIDA = Path(__file__).resolve().parent
ANTERIOR = SALIDA.parent / "v4"
comparacion = json.loads((SALIDA / "vigente-comparacion.json").read_text(encoding="utf-8"))
texto = ["# Caracterización de las correcciones", "",
         "Las dos referencias usan la misma métrica literal. Las respuestas exactas actuales pueden completar bordes del tramo seleccionado; el modelo no cambia y completar un tramo conserva su puntaje bruto. Cambiar la pregunta o la ventana de lectura puede cambiar el tramo elegido y su puntaje. No se acredita un actor distinto encontrado en una cita amplia.", "",
         "El núcleo conserva el orden original y los términos iniciales fuera de sus tres raíces durante un seguimiento. La intención usa la pregunta actual. El lector también la usa cuando reconoce una relación o varios términos de contenido; conserva la interpretación para calificativos aislados como «y en verano». Las preguntas por actores aíslan la oración de la acción actual. Los tramos de cantidad retienen sus unidades, límites y referencias; los de actor pueden extenderse con su acción inmediata. Estos cambios generales explican las diferencias registradas; las preguntas, interpretaciones y tramos siguientes permiten revisar cada resultado.", ""]
tablas = ["# Resultados finales", "", "## Conversaciones: respuestas literales correctas / 54", "",
          "| Perfil | Idioma | F1 | V4 inicial | Corrección | Herencia correcta / 38 | Directas negativas / 4 |",
          "|---|---|---|---|---|---|---|"]
final = json.loads((SALIDA / "vigente-conversaciones.json").read_text(encoding="utf-8"))
f1 = json.loads((ANTERIOR / "f1-conversaciones.json").read_text(encoding="utf-8"))
v4 = json.loads((ANTERIOR / "corregido-conversaciones.json").read_text(encoding="utf-8"))
for perfil, idiomas in final.items():
    for idioma, datos in idiomas.items():
        resumen = datos["resumen"]
        tablas.append(f"| {perfil} | {idioma} | {f1[perfil][idioma]['resumen']['respuestas_correctas']} | {v4[perfil][idioma]['resumen']['respuestas_correctas']} | {resumen['respuestas_correctas']} | {resumen['herencia_correcta']} | {resumen['directas_indebidas']} |")

def celda(valor):
    return str(valor or "—").replace("|", "\\|").replace("\n", " ")

for base, prefijo in (("F1", "f1"), ("V4 inicial", "corregido")):
    texto += [f"## Frente a {base}", "",
              "| Perfil | Turno | Estado anterior → actual | Literal correcto anterior → actual | Pregunta actual | Interpretación actual | Tramo actual / primera evidencia |",
              "|---|---|---|---|---|---|---|"]
    antes = f1 if prefijo == "f1" else v4
    for perfil, idiomas in final.items():
        for idioma, datos in idiomas.items():
            a = {f"{t['conversacion']}:{t['turno']}": t for t in antes[perfil][idioma]["turnos"]}
            for t in datos["turnos"]:
                id = f"{t['conversacion']}:{t['turno']}"
                previo = a[id]
                if previo["estado"] != t["estado"] or previo["correcta"] != t["correcta"]:
                    muestra = t["tramo_lector"] or t["mensaje"][:200]
                    texto.append("| " + " | ".join(map(celda, [perfil, id, f"{previo['estado']} → {t['estado']}", f"{previo['correcta']} → {t['correcta']}", t["pregunta"], t["interpretada"], muestra])) + " |")
for banco in ("consultas", "universal"):
    tablas += ["", f"## {banco}: correctas / directas erróneas", "",
               "| Perfil | Idioma | F1 | V4 inicial | Corrección |", "|---|---|---|---|---|"]
    for perfil, idiomas in comparacion["bases"]["f1"][banco].items():
        for idioma, fila in idiomas.items():
            previo = comparacion["bases"]["corregido"][banco][perfil][idioma]
            tablas.append(f"| {perfil} | {idioma} | {fila['correctas'][0]} / {fila['erroneas'][0]} | {previo['correctas'][0]} / {previo['erroneas'][0]} | {fila['correctas'][1]} / {fila['erroneas'][1]} |")
tablas += ["", "## Objetivos que motivaron las correcciones", "", "| Perfil / turno | Correcta | Tramo publicado |", "|---|---|---|"]
for id, dato in comparacion["objetivos"].items():
    tablas.append(f"| {id} | {dato['correcta']} | {celda(dato['tramo'])} |")
(SALIDA / "caracterizacion.md").write_text("\n".join(texto) + "\n", encoding="utf-8")
(SALIDA / "tablas.md").write_text("\n".join(tablas) + "\n", encoding="utf-8")
print("Tablas y caracterización actualizadas.", flush=True)
