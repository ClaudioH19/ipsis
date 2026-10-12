"""Comprobación HTTP del servicio real: readiness, conversación y fuente literal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

PREGUNTA = "¿Cuántas unidades tiene el producto CI-001?"
PASO_DOCUMENTAL = "El producto CI-001 tiene 17 unidades disponibles."


def exigir(condicion, mensaje):
    if not condicion:
        raise RuntimeError(mensaje)


def validar_conversacion(respuesta, categoria):
    exigir(respuesta.get("status") == "conversational", "No respondió como conversación")
    exigir(respuesta.get("conversational_category") == categoria, "Categoría de conversación incorrecta")
    exigir(isinstance(respuesta.get("answer"), str) and respuesta["answer"].strip(), "Respuesta vacía")
    exigir(not respuesta.get("fragments"), "La cortesía se mezcló con fuentes documentales")


def validar_fuentes(respuesta):
    exigir(respuesta.get("response_mode") == "ranked_sources", "No respondió con el motor de fuentes")
    exigir(respuesta.get("status") == "related", "La consulta no produjo fuentes para revisar")
    fuentes = respuesta.get("fragments", [])
    exigir(1 <= len(fuentes) <= 3, "Cantidad de fuentes inesperada")
    exigir(any(PASO_DOCUMENTAL in f.get("text", "") for f in fuentes), "No recuperó el dato conocido del corpus")
    for fuente in fuentes:
        exigir(bool(fuente.get("doc_title")), "Falta la referencia documental")
        exigir(fuente["offset_end"] - fuente["offset_start"] == len(fuente["text"]), "Offsets inconsistentes")


def comprobar(url, *, espera=180, salida=None):
    url = url.rstrip("/")
    reporte = {"ok": False, "comprobaciones": []}

    def solicitar(ruta, cuerpo=None):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
        req = urllib.request.Request(url + ruta, data=datos, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)

    try:
        limite = time.monotonic() + espera
        ultimo_error = None
        while True:
            try:
                listo = solicitar("/ready")
                exigir(listo.get("ready") is True and listo.get("pipeline") == "v2", "Motor v2 no está listo")
                exigir(listo.get("n_chunks", 0) > 0, "Índice vacío")
                break
            except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                ultimo_error = str(exc)
                if time.monotonic() >= limite:
                    raise RuntimeError(f"El servicio no estuvo listo: {ultimo_error}") from exc
                time.sleep(.5)
        reporte["comprobaciones"].append({"paso": "ready", "respuesta": listo})
        salud = solicitar("/health")
        exigir(salud.get("status") == "alive" and salud.get("mode") == "production", "Servicio no está vivo en producción")
        cfg = solicitar("/config")
        exigir(cfg.get("response_mode") == "ranked_sources", "Configuración del widget no corresponde a v2")
        exigir(sum(map(len, cfg.get("assistant_messages", {}).values())) == 100, "Falta el catálogo de conversación")
        reporte["comprobaciones"].append({"paso": "health_config", "ok": True})
        for pregunta, categoria in [("hola", "greeting"), ("gracias", "thanks"), ("adiós", "farewell"),
                                    ("¿Qué puedes hacer?", "capability")]:
            respuesta = solicitar("/ask", {"question": pregunta, "session_id": "ipsis-ci"})
            validar_conversacion(respuesta, categoria)
            reporte["comprobaciones"].append({"paso": categoria, "respuesta": respuesta})
        for pregunta in (PREGUNTA, "hola, " + PREGUNTA):
            respuesta = solicitar("/ask", {"question": pregunta, "session_id": "ipsis-ci"})
            validar_fuentes(respuesta)
            reporte["comprobaciones"].append({"paso": "fuentes", "respuesta": respuesta})
        reporte["ok"] = True
        return reporte
    except Exception as exc:
        reporte["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if salida is not None:
            salida = Path(salida)
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_text(json.dumps(reporte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--wait", type=float, default=180)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    comprobar(args.url, espera=args.wait, salida=args.output)
    print("OK: servicio listo, conversación y recuperación literal por HTTP")
