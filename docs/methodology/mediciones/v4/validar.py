"""Comprueba criterios formales sin ocultar pérdidas de literales positivos."""
from pathlib import Path
import json

RAIZ = Path(__file__).resolve().parent


def main():
    informe = json.loads((RAIZ / "comparacion.json").read_text(encoding="utf-8"))
    texto = (RAIZ / "caracterizacion.md").read_text(encoding="utf-8")
    estados = [c for banco in ("consultas", "universal", "conversaciones")
               for f in informe["desde_f1"][banco] for c in f["cambios"]
               if c["antes"]["estado"] != c["despues"]["estado"]]
    sin_explicar = [c["id"] for c in estados if c["id"] not in texto]
    retornos = [t for f in informe["desde_f1"]["conversaciones"] for t in f["retoma_007_015"]]
    criterios = {"G1": informe["g1"], **{k.upper(): informe["desde_f1"][k] for k in ("g2", "g3", "g4")},
                 "G5": informe["g5"], "G6": not sin_explicar,
                 "F4_herencia_no_disminuye": informe["desde_f1"]["f4_herencia"],
                 "F4_retornos_mejoran_todas_combinaciones": all(not t["antes"] and t["despues"] for t in retornos),
                 "sin_regresiones_desde_inicio": informe["desde_inicio"]["calidad_sin_regresiones_por_caso"],
                 "F3_etiquetas_naturales": all(not f["errores_intencion"] for f in informe["intenciones"]["consultas"])}
    resultado = dict(criterios=criterios, estados_sin_explicar=sin_explicar,
                     perdidas_literales_f1=[dict(perfil=f["perfil"], idioma=f["idioma"], casos=f["correctas_perdidas"])
                                           for f in informe["desde_f1"]["conversaciones"] if f["correctas_perdidas"]],
                     alcance="G4 solo mide directas en turnos negativos. Hay pérdidas literales positivas frente a F1; no se declara ausencia general de regresiones.")
    (RAIZ / "validacion.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    assert all(criterios.values()), "Faltan criterios; ver validacion.json"


if __name__ == "__main__":
    main()
