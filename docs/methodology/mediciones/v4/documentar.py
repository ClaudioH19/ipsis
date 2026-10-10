"""Actualiza procedencia verificable y genera tablas a partir de los JSON."""
from pathlib import Path
import hashlib
import json
import zipfile

RAIZ = Path(__file__).resolve().parent


def cargar(nombre):
    return json.loads((RAIZ / nombre).read_text(encoding="utf-8"))


def escribir(nombre, dato):
    (RAIZ / nombre).write_text(json.dumps(dato, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main():
    informe = cargar("comparacion.json")
    metadata = cargar("metadata.json")
    f2 = json.loads((RAIZ.parent / "f2/metadata.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(RAIZ / "antes-code.zip") as a, zipfile.ZipFile(RAIZ.parent / "f2/final-code.zip") as b:
        nombres_a = {p for p in a.namelist() if Path(p).suffix in {".py", ".yaml"}}
        nombres_b = {p for p in b.namelist() if Path(p).suffix in {".py", ".yaml"}}
        assert nombres_a == nombres_b and all(a.read(p) == b.read(p) for p in nombres_a)
    for banco in ("consultas", "universal", "conversaciones"):
        assert (RAIZ / f"antes-{banco}.json").read_bytes() == (RAIZ.parent / f"f2/despues-{banco}.json").read_bytes()
    metadata.update(model_cache_snapshots=f2["model_cache_snapshots"],
                    before_python_yaml_byte_identical_to_f2_final=True,
                    before_banks_byte_identical_to_f2_results=True,
                    policy_thresholds_changed=False, data_downloads=False,
                    metric="selected_reader_span_v2",
                    comparison_baselines={"antes": "Fin de F2; ya contenía memoria de temas", "f1": "39c7878, solo evaluación literal corregida"},
                    final_source="corregido-code.zip; separación de genéricas de memoria y respuesta",
                    previous_round_post_bank_change={"files": informe["cambios_post_medicion_anterior"],
                                      "reason": "El ranking de diagnóstico ahora usa la intención efectiva y el contexto, como la selección real. No modifica respuestas ni decisiones.",
                                      "validated_by": "pruebas-diagnostico.xml: 19 aprobadas; una prueba añadida después de recoger la suite completa"},
                    validation={"full": informe["pruebas"], "separation_unit_tests": informe["pruebas_separacion"]},
                    previous_round_failure="comparacion-antes-separacion.json: G3 falla por es-parafrasis-019; validacion-antes-separacion.json conserva todos los criterios",
                    archives={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAIZ.glob("*-code.zip"))})
    with zipfile.ZipFile(RAIZ / "corregido-code.zip") as z:
        repo = RAIZ.parents[3]
        assert all((repo / p).read_bytes() == z.read(p) for p in z.namelist()), "El código actual difiere de la captura final"
    escribir("metadata.json", metadata)
    tablas = []
    for banco in ("consultas", "universal"):
        tablas += [f"## {banco.title()}: correctas / directas erróneas, F1 → final", "", "| Perfil | es | en | pt |", "|---|---|---|---|"]
        filas = informe["desde_f1"][banco]
        for perfil in ("light", "medium"):
            vv = [next(f for f in filas if f["perfil"] == perfil and f["idioma"] == idioma) for idioma in ("es", "en", "pt")]
            tablas.append("| " + perfil + " | " + " | ".join(f"{f['correctas_antes']} / {f['erroneas_antes']} → {f['correctas_despues']} / {f['erroneas_despues']}" for f in vv) + " |")
        tablas.append("")
    tablas += ["## Conversaciones: herencias correctas; respuestas literales correctas, F1 → final", "", "| Perfil | es | en | pt |", "|---|---|---|---|"]
    for perfil in ("light", "medium"):
        vv = [next(f for f in informe["desde_f1"]["conversaciones"] if f["perfil"] == perfil and f["idioma"] == idioma) for idioma in ("es", "en", "pt")]
        tablas.append("| " + perfil + " | " + " | ".join(f"{f['antes']['herencia_correcta']} → {f['despues']['herencia_correcta']}; {f['antes']['respuestas_correctas']} → {f['despues']['respuestas_correctas']}" for f in vv) + " |")
    tablas += ["", "38 turnos etiquetados para herencia, 54 para respuesta literal y 4 negativos por idioma. Herencias indebidas y directas negativas: **0 → 0 en las seis combinaciones**.", "",
               "## Latencia universal light (ms), tres pares alternados", "", "| Base | Idioma | Antes | Final | Cambio | G5 |", "|---|---|---|---|---|---|"]
    for referencia in ("inicio", "f1"):
        for f in informe[f"latencia_desde_{referencia}"]["filas"]:
            tablas.append(f"| {referencia} | {f['idioma']} | {f['media_antes_ms']:.1f} | {f['media_despues_ms']:.1f} | {f['cambio_pct']:+.1f}% | {'pasa' if f['g5'] else 'falla'} |")
    tablas += ["", "## Respaldo efectivo de intención", "", "| Banco | Perfil | Idioma | Intentos | Aceptadas |", "|---|---|---|---|---|"]
    for banco, filas in informe["intenciones"].items():
        for f in filas:
            tablas.append(f"| {banco} | {f['perfil']} | {f['idioma']} | {f['intentos']} | {f['aceptadas']} |")
    (RAIZ / "tablas.md").write_text("\n".join(tablas)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
