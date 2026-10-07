"""Elige τ/δ exclusivamente en dev, conservando predicciones y test separado."""
from pathlib import Path
import json
import os
import sys

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
os.environ["HF_HUB_OFFLINE"] = "1"

import numpy as np
import yaml
from ipsis.lenguaje.consultas import comprender, sinonimos_presentes
from ipsis.lenguaje.intenciones import RespaldoIntenciones, tiene_tema
from ipsis.indice.estadisticas import EstadisticasLexicas
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.modelos.catalogo import obtener
from ipsis.modelos.denso import CodificadorDenso

MODELO = "intfloat/multilingual-e5-small"


def calibrar():
    etiquetas = yaml.safe_load((RAIZ / "tests/datos/banco_consultas/intenciones.yaml").read_text(encoding="utf-8"))
    modelo = CodificadorDenso(obtener(MODELO))
    informe = {"modelo": MODELO, "criterio": "máxima cobertura correcta sin errores en dev; desempate por menor δ y luego τ",
               "grid": {"tau": "0.700..0.995, paso 0.005", "delta": "0.000..0.200, paso 0.005"}, "idiomas": {}}
    for idioma in ("es", "en", "pt"):
        paquete = cargar_paquete(idioma)
        respaldo = RespaldoIntenciones(paquete, modelo, similitud=0, margen=0)
        casos = [json.loads(l) for l in (RAIZ / f"tests/datos/banco_consultas/{idioma}/banco.jsonl").read_text(encoding="utf-8").splitlines()]
        corpus = RAIZ / f"tests/datos/banco_consultas/{idioma}/corpus"
        estadisticas = EstadisticasLexicas.construir([p.read_text(encoding="utf-8") for p in sorted(corpus.glob("*.md"))], paquete)
        preparadas = []
        for c in casos:
            sinonimos = sinonimos_presentes(c["pregunta"], paquete, estadisticas)
            extra = " ".join(f for formas in sinonimos.values() for f in formas)
            preparadas.append(f"{c['pregunta'].rstrip()} {extra}" if extra else c["pregunta"])
        vectores = modelo.codificar_consultas(preparadas)
        filas = []
        for caso, preparada, vector in zip(casos, preparadas, vectores, strict=True):
            p = respaldo.predecir(vector)
            filas.append({"id": caso["id"], "split": caso["split"], "pregunta": caso["pregunta"],
                          "esperada": etiquetas[caso["id"].split("-", 1)[1]],
                          "pregunta_efectiva": preparada,
                          "patron": comprender(preparada, paquete).intencion,
                          "con_tema": tiene_tema(preparada, paquete, estadisticas),
                          "candidato": p.candidato, "similitud": p.similitud, "margen": p.margen, "ejemplo": p.ejemplo})
        dev = [f for f in filas if f["split"] == "dev" and f["patron"] is None and f["con_tema"]]
        opciones = []
        for tau in np.arange(0.700, 1.000, 0.005):
            for delta in np.arange(0.000, 0.205, 0.005):
                aceptadas = [f for f in dev if f["similitud"] > tau and f["margen"] > delta]
                if all(f["candidato"] == f["esperada"] for f in aceptadas):
                    opciones.append((-len(aceptadas), float(delta), float(tau)))
        cantidad, delta, tau = min(opciones)
        habilitadas = sorted({f["candidato"] for f in dev if f["similitud"] > tau and f["margen"] > delta})
        resumen = {}
        for split in ("dev", "test"):
            sin_patron = [f for f in filas if f["split"] == split and f["patron"] is None]
            aceptadas = [f for f in sin_patron if f["con_tema"] and f["candidato"] in habilitadas
                        and f["similitud"] > tau and f["margen"] > delta]
            resumen[split] = {"sin_patron": len(sin_patron), "aceptadas": len(aceptadas),
                              "correctas": sum(f["candidato"] == f["esperada"] for f in aceptadas),
                              "errores": [f["id"] for f in aceptadas if f["candidato"] != f["esperada"]]}
        informe["idiomas"][idioma] = {"tau": round(tau, 3), "delta": round(delta, 3), "habilitadas": habilitadas,
                                     "resumen": resumen, "casos": filas}
        print(idioma, round(tau, 3), round(delta, 3), resumen, flush=True)
    salida = Path(__file__).resolve().parent / "intenciones-dev-test.json"
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    calibrar()
