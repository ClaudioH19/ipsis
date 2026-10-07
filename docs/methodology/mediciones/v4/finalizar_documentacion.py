"""Marca implementación y medición completas, dejando el cierre a revisión."""
from pathlib import Path
import json

SALIDA = Path(__file__).resolve().parent
REPO = SALIDA.parents[3]

notas = {
    "F4.1": "Temas, compactación y retoma auditados; herencia 36/35/34 de 38 en ambos perfiles. -007/-015 mejoran en los tres idiomas. Costes literales frente a F1 documentados.",
    "F4.2": "Configuración opcional, reloj inyectado, vencimiento exacto y tope; suite completa en verde.",
    "F4.3": "ID nuevo por carga de página, panel conserva sesión; widget y guías verificados.",
    "F4.4": "Acción y núcleo en diagnóstico/CLI; esquema y diagnóstico verificados.",
    "F4.5": "Aislamiento, concurrencia, expiración, compactación y registro posterior a guardias; 1.054 pruebas completas aprobadas, 2 omitidas.",
    "F4.6": "Tres bancos × seis combinaciones y dos bases; G1–G6 formales pasan. Cuatro aciertos conversacionales perdidos y cinco nuevas directas sin literal frente a F1 se informan por separado.",
    "F4.7": "ADR 0006, arquitectura, guías, README, CHANGELOG y resultados permanentes actualizados.",
    "F3.1": "210 ejemplos independientes: diez por cada una de siete intenciones en es/en/pt.",
    "F3.2": "Vectores al arrancar, consulta reutilizada, prioridad de patrones, BM25/modelos no medidos inactivos y diagnóstico de aceptación/rechazo; G5 pasa.",
    "F3.3": "Umbrales elegidos en dev: 6 aciertos dev + 2 test, cero errores activos en el banco natural. Errores de intención en bancos secundarios e iteraciones fallidas documentados.",
    "F3.4": "Ocho consultas adicionales con intención por perfil; ronda aislada F3 sin cambios de respuesta. Suite completa y G1–G6 en verde; respaldo de cobertura limitada.",
    "F3.5": "ADR 0005, metodología, arquitectura, guías, CHANGELOG y evaluación final actualizados.",
    "F5.1": "Resumen y evidencias permanentes preparados. Falta revisión/aprobación del cierre; se conserva docs/plan/. Errores del lector y costes literales no se declaran resueltos.",
}


def main():
    v = json.loads((SALIDA / "validacion.json").read_text(encoding="utf-8"))
    assert all(v["criterios"].values()), "No se cierra implementación con criterios fallidos"
    p = REPO / "docs/plan/avance.md"
    texto = p.read_text(encoding="utf-8")
    lineas = []
    for linea in texto.splitlines():
        campos = linea.split("|")
        tarea = campos[1].strip() if len(campos) >= 7 else ""
        if tarea in notas:
            estado = "⚠" if tarea == "F5.1" else "✅"
            linea = f"| {tarea} | {estado} | 2026-10-06 | este commit | {notas[tarea]} |"
        elif tarea.startswith("F2."):
            campos[4] = " este commit "
            linea = "|".join(campos)
        lineas.append(linea)
    texto = "\n".join(lineas)+"\n"
    texto = texto.replace("## Línea base (F1.4)\n", "## Línea base histórica (F1.4)\n\nEsta tabla usaba el literal de la cita amplia. Los conteos medium no son\ncomparables directamente con la métrica corregida; F1 se reevalúa en la\ncomparación final abajo.\n")
    tablas = (SALIDA / "tablas.md").read_text(encoding="utf-8")
    texto += "\n## Final F4/F3 y preparación de F5\n\n"
    texto += ("G1–G6 formales pasan. Suite final: **1.054 aprobadas, 2 omitidas**\n"
              "(21 min 53 s); 62 pruebas específicas de separación aprobadas.\n"
              "La comparación F1 corrige solo la métrica, no su motor. El fallo G3\n"
              "inicial se conserva y se corrige separando `genericas_memoria` del foco.\n\n"
              "[Informe permanente](../methodology/v4-results.md),\n"
              "[evidencias y reproducción](../methodology/mediciones/v4/README.md),\n"
              "[validación por criterio](../methodology/mediciones/v4/validacion.json).\n\n"
              "Pasar G4 no implica ausencia de errores en turnos positivos: hay cuatro\n"
              "pérdidas literales conversacionales frente a F1 y cinco nuevas directas\n"
              "sin el literal elegido por el lector; dos seleccionan a quien firma\n"
              "cuando se pregunta quién redacta. La similitud también infiere etiquetas\n"
              "incorrectas en bancos secundarios, sin alterar sus respuestas en esta\n"
              "medición. Se mantienen como limitaciones y requieren revisión del cierre.\n\n")
    texto += tablas
    p.write_text(texto, encoding="utf-8")


if __name__ == "__main__":
    main()
