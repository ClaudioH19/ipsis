"""Inspecciona los errores del banco español con el motor y los modelos reales.

Desde la raíz: python docs/methodology/auditoria-2026-10-08/ejemplos.py
Usar HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1 e IPSIS_ONNX_THREADS=2.
Requiere los modelos ya descargados. Crea proyectos temporales aislados.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from pathlib import Path

from ipsis.aplicacion.consulta import construir_motor_del_proyecto
from ipsis.cli import main


def ejecutar() -> list[dict]:
    raiz = Path(__file__).resolve().parents[3]
    datos = raiz / "tests/datos/banco_consultas/es"
    casos = {c["id"]: c for linea in (datos / "banco.jsonl").read_text(encoding="utf-8").splitlines()
             if (c := json.loads(linea))}
    medicion = json.loads(Path(__file__).with_name("consultas-es.json").read_text(encoding="utf-8"))
    elegidos = {perfil: [identificador for identificador, caso in idiomas["es"]["casos"].items()
                        if caso["directa"] and (caso["falso_ok"] or caso["sin_literal"])]
                for perfil, idiomas in medicion.items()}
    resultados = []
    anterior = Path.cwd()
    for perfil, ids in elegidos.items():
        with tempfile.TemporaryDirectory(prefix=f"ipsis-auditoria-{perfil}-", ignore_cleanup_errors=True) as temporal:
            motor = None
            try:
                os.chdir(temporal)
                with contextlib.redirect_stdout(io.StringIO()):
                    assert main(["init", "--profile", perfil, "--language", "es"]) == 0
                    assert main(["load", str(datos / "corpus")]) == 0
                    assert main(["index"]) == 0
                    motor = construir_motor_del_proyecto()
                    motor.calentar()
                    for identificador in ids:
                        caso = casos[identificador]
                        respuesta = motor.consultar(caso["pregunta"], f"auditoria:{identificador}")
                        diagnostico = respuesta.diagnostico
                        contrato = diagnostico.get("contrato_http") or {}
                        resultados.append({
                            "perfil": perfil, "caso": identificador, "pregunta": caso["pregunta"],
                            "respondible": caso["respondible"], "esperado": caso.get("respuesta_literal"),
                            "estado": respuesta.estado.value, "respuesta": respuesta.mensaje_usuario,
                            "respuesta_exacta": contrato.get("respuesta_exacta"),
                            "evidencias": [e.model_dump(mode="json") for e in respuesta.evidencias],
                            "regla": diagnostico.get("regla"),
                            "senales": diagnostico.get("senales_politica"),
                        })
            finally:
                if motor is not None:
                    motor.cerrar()
                os.chdir(anterior)
    return resultados


if __name__ == "__main__":
    salida = Path(__file__).with_name("ejemplos.json")
    resultados = ejecutar()
    salida.write_text(json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in resultados:
        print(r["perfil"], r["caso"], r["estado"], r["respuesta_exacta"], flush=True)
    print(salida)
