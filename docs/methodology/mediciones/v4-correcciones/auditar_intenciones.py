"""Resumen de intentos y aceptación; conserva ejemplos para revisión semántica."""
from collections import Counter
from pathlib import Path
import json

SALIDA = Path(__file__).resolve().parent
tablas = ["# Respaldo efectivo de intención", "",
          "Los intentos usan la pregunta actual y exigen compatibilidad además del umbral. Las filas aceptadas se conservan para revisión; las etiquetas del banco natural se verifican en `validar.py`. Los bancos secundarios no disponen de etiquetas exhaustivas independientes.", "",
          "| Banco | Perfil | Idioma | Intentos | Aceptadas | Incompatibles |",
          "|---|---|---|---|---|---|"]
informe = {}
for banco in ("consultas", "universal", "conversaciones"):
    filas = json.loads((SALIDA / f"vigente-{banco}.intenciones.json").read_text(encoding="utf-8"))
    resumen, aceptadas, incompatibles = Counter(), [], []
    for fila in filas:
        d = fila["diagnostico"]
        if d.get("origen") != "similitud":
            continue
        clave = fila["perfil"], fila["idioma"]
        resumen[clave + ("intentos",)] += 1
        if d.get("aceptada"):
            resumen[clave + ("aceptadas",)] += 1
            aceptadas.append(fila)
        if d.get("compatible") is False:
            resumen[clave + ("incompatibles",)] += 1
            incompatibles.append(fila)
    for perfil in ("light", "medium"):
        for idioma in ("es", "en", "pt"):
            tablas.append(f"| {banco} | {perfil} | {idioma} | " +
                          " | ".join(str(resumen[perfil, idioma, k]) for k in
                                     ("intentos", "aceptadas", "incompatibles")) + " |")
    informe[banco] = {"aceptadas": aceptadas, "incompatibles": incompatibles}
    print(banco)
    for fila in aceptadas:
        if fila["perfil"] == "light":
            print(fila["idioma"], fila["sesion"], fila["intencion"], fila["pregunta_efectiva"])
(SALIDA / "respaldo-intenciones.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(SALIDA / "respaldo-intenciones.md").write_text("\n".join(tablas) + "\n", encoding="utf-8")
