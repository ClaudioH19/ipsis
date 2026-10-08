"""Rendimiento de la postura proactiva (ADR 0008) sobre un proyecto ya indexado.

    python rendimiento.py <proyecto> <salida.json> [carga]

1. Latencia en proceso, motor caliente: las preguntas del banco de
   alternativas (es) y del banco de consultas (es), 3 rondas, en sesiones
   nuevas, con postura proactiva y estricta alternadas pregunta a pregunta
   (mismo estado de caché y de CPU para ambas).
2. Con ``carga``: ``ipsis serve`` y 8 clientes concurrentes, 240 peticiones
   por postura (el servicio limita la concurrencia del motor: 503 si satura).
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[4]
DATOS = RAIZ / "tests" / "datos"


def preguntas() -> list[str]:
    alternativas = [c["pregunta"] for c in yaml.safe_load(
        (DATOS / "banco_alternativas" / "es" / "casos.yaml").read_text(encoding="utf-8"))]
    consultas = [json.loads(linea)["pregunta"] for linea in
                 (DATOS / "banco_consultas" / "es" / "banco.jsonl").read_text(encoding="utf-8").splitlines() if linea]
    return alternativas + consultas


def percentil(valores: list[float], p: float) -> float:
    orden = sorted(valores)
    return round(orden[min(len(orden) - 1, int(round(p / 100 * (len(orden) - 1))))], 1)


def resumen(valores: list[float]) -> dict:
    return {"n": len(valores), "media": round(statistics.mean(valores), 1), "p50": percentil(valores, 50),
            "p95": percentil(valores, 95), "max": round(max(valores), 1)} if valores else {"n": 0}


def en_proceso(proyecto: Path) -> dict:
    os.chdir(proyecto)
    from ipsis.aplicacion.consulta import construir_motor_del_proyecto

    motor = construir_motor_del_proyecto()
    motor.calentar()
    lista = preguntas()
    for pregunta in lista[:10]:
        motor.consultar(pregunta, "calentar")
    medidas = {"proactiva": [], "estricta": []}
    con_alternativas, politica = [], {"proactiva": [], "estricta": []}
    for ronda in range(3):
        for i, pregunta in enumerate(lista):
            orden = ("proactiva", "estricta") if (i + ronda) % 2 == 0 else ("estricta", "proactiva")
            for modo in orden:
                motor.alternativas.modo = modo
                marca = time.perf_counter()
                r = motor.consultar(pregunta, f"{modo}-{ronda}-{i}")
                ms = (time.perf_counter() - marca) * 1000
                medidas[modo].append(ms)
                politica[modo].append((r.diagnostico.get("etapas") or {}).get("politica_ms", 0))
                if modo == "proactiva" and (r.diagnostico.get("contrato_http") or {}).get("alternativas"):
                    con_alternativas.append((i, ms))
    indices = {i for i, _ in con_alternativas}
    pares_estricta = [ms for k, ms in enumerate(medidas["estricta"]) if k % len(lista) in indices]
    return {
        "preguntas": len(lista), "rondas": 3,
        "proactiva": resumen(medidas["proactiva"]), "estricta": resumen(medidas["estricta"]),
        "politica_ms": {m: resumen([float(v) for v in vs]) for m, vs in politica.items()},
        "con_alternativas": {"preguntas": len(indices), "proactiva": resumen([ms for _, ms in con_alternativas]),
                             "estricta_mismas_preguntas": resumen(pares_estricta)},
    }


def carga(proyecto: Path, modo: str, puerto: int = 8765) -> dict:
    import httpx

    asistente = proyecto / "config" / "assistant.yaml"
    texto = asistente.read_text(encoding="utf-8")
    asistente.write_text(texto.replace("mode: proactive", f"mode: {'proactive' if modo == 'proactiva' else 'strict'}")
                         .replace("mode: strict", f"mode: {'proactive' if modo == 'proactiva' else 'strict'}"),
                         encoding="utf-8")
    ejecutable = RAIZ / ".venv" / "Scripts" / "ipsis.exe"
    proceso = subprocess.Popen([str(ejecutable), "serve", "--port", str(puerto)], cwd=proyecto,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{puerto}"
        for _ in range(240):
            try:
                if httpx.get(f"{base}/ready", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        lista = preguntas()

        def pedir(k: int):
            marca = time.perf_counter()
            r = httpx.post(f"{base}/ask", json={"question": lista[k % len(lista)], "session_id": f"carga-{k}"},
                           timeout=60)
            return r.status_code, (time.perf_counter() - marca) * 1000, bool(r.json().get("alternatives")) if r.status_code == 200 else False

        for k in range(8):
            pedir(k)
        marca = time.perf_counter()
        with ThreadPoolExecutor(8) as pool:
            resultados = list(pool.map(pedir, range(240)))
        total = time.perf_counter() - marca
    finally:
        proceso.terminate()
        proceso.wait(timeout=30)
    codigos: dict[int, int] = {}
    for codigo, _, _ in resultados:
        codigos[codigo] = codigos.get(codigo, 0) + 1
    return {"peticiones": len(resultados), "clientes": 8, "segundos": round(total, 1),
            "por_segundo": round(len(resultados) / total, 1), "codigos": codigos,
            "latencia_ok": resumen([ms for c, ms, _ in resultados if c == 200]),
            "con_alternativas": sum(a for _, _, a in resultados)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    proyecto, salida = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    if len(sys.argv) > 3 and sys.argv[3] == "carga":
        resultado = {"carga": {modo: carga(proyecto, modo) for modo in ("proactiva", "estricta")}}
    else:
        resultado = {"en_proceso": en_proceso(proyecto)}
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=1))
