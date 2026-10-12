"""Comparación offline sobre copias de un proyecto; no cambia el proyecto servido.

Las preguntas se leen de JSON: lista de strings o de objetos con id/question y,
opcionalmente, required/forbidden (comprobaciones literales, no un juez semántico).
Cada implementación corre en un proceso separado, con el mismo índice y CPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]


def copiar_proyecto(origen: Path, destino: Path):
    for nombre in ("config", "documents", ".ipsis/index"):
        shutil.copytree(origen / nombre, destino / nombre,
                        ignore=shutil.ignore_patterns(".lock", "*.sqlite", "*.sqlite-wal", "*.sqlite-shm"))
    for archivo in (origen / ".ipsis/index").rglob("*.sqlite"):
        objetivo = destino / archivo.relative_to(origen)
        objetivo.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(archivo.resolve().as_uri() + "?mode=ro", uri=True) as fuente:
            with sqlite3.connect(objetivo) as copia:
                fuente.backup(copia)


def preguntas_desde_json(ruta):
    valores = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(valores, list) or not valores:
        raise ValueError("questions debe contener una lista no vacía")
    salida = []
    for i, valor in enumerate(valores):
        if not isinstance(valor, (str, dict)):
            raise ValueError("cada caso debe ser texto u objeto")
        caso = {"id": str(i + 1), "question": valor} if isinstance(valor, str) else dict(valor)
        if not isinstance(caso.get("question"), str) or not caso["question"].strip():
            raise ValueError("cada caso requiere question")
        caso.setdefault("id", str(i + 1))
        if not isinstance(caso["id"], str) or not caso["id"]:
            raise ValueError("id debe ser texto no vacío")
        for clave in ("required", "forbidden"):
            if not isinstance(caso.get(clave, []), list) or not all(isinstance(s, str) for s in caso.get(clave, [])):
                raise ValueError(f"{clave} debe ser una lista de textos")
        salida.append(caso)
    if len({c["id"] for c in salida}) != len(salida):
        raise ValueError("los identificadores deben ser únicos")
    return salida


def aislar_indice(cfg, proyecto):
    """Abrir exclusivamente el índice copiado, incluso con rutas absolutas o env."""
    recuperacion = cfg["recuperacion"]
    ruta = Path(recuperacion["qdrant_path"])
    if not ruta.is_absolute():
        ruta = proyecto / ruta
    ruta = ruta.resolve()
    raiz = (proyecto / ".ipsis/index").resolve()
    if not ruta.is_relative_to(raiz):
        raise ValueError("el comparador requiere un índice local dentro de .ipsis/index")
    if cfg.get("qdrant", {}).get("modo", "local") != "local":
        raise ValueError("el comparador requiere un snapshot local de Qdrant")
    recuperacion["qdrant_path"] = str(ruta)
    cfg.setdefault("qdrant", {})["modo"] = "local"
    os.environ["QDRANT_MODE"] = "local"


def _rss():
    try:
        import psutil

        return psutil.Process().memory_info().rss
    except (ImportError, OSError):
        return None


def preparar_codigo(raiz):
    # Resolver antes de cambiar cwd: una ruta relativa no debe cargar por
    # accidente la instalación editable en lugar del código congelado.
    raiz = raiz.resolve()
    if not (raiz / "ipsis/__init__.py").is_file():
        raise ValueError("source-root no contiene el paquete ipsis")
    sys.path.insert(0, str(raiz))
    import ipsis

    if not Path(ipsis.__file__).resolve().is_relative_to(raiz / "ipsis"):
        raise ValueError("el código cargado no coincide con source-root; ejecutar un proceso aislado")
    return raiz


def worker(args):
    args.source_root = preparar_codigo(args.source_root)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["IPSIS_ONNX_THREADS"] = str(args.threads)
    os.chdir(args.project)
    from ipsis.aplicacion.consulta import construir_motor
    from ipsis.aplicacion.registro import entrada_de_registro
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto
    from ipsis.nucleo.traza import capturar_traza

    cfg = cargar_proyecto()
    aislar_indice(cfg, args.project)
    if args.pipeline == "v2":
        cfg["pipeline"] = "v2"
    elif "pipeline" in cfg:
        cfg["pipeline"] = "v1"
    comienzo = time.perf_counter()
    motor = construir_motor(cfg, cfg_dominio=cargar_dominio())
    registros, latencias, memoria = [], [], []
    try:
        motor.calentar()
        arranque_ms = (time.perf_counter() - comienzo) * 1000
        for ronda in range(args.rounds):
            for caso in preguntas_desde_json(args.questions):
                print(f"Case {caso['id']} (round {ronda + 1})", flush=True)
                with capturar_traza() as traza:
                    inicio = time.perf_counter()
                    try:
                        sesion = f"comparison-{ronda}" if args.conversation else f"comparison-{ronda}-{caso['id']}"
                        resultado = motor.consultar(caso["question"], sesion)
                        registro = entrada_de_registro(caso["question"], resultado)
                        respuesta = resultado.mensaje_usuario
                        registro["automatic_checks"] = {
                            "required": {s: s in respuesta for s in caso.get("required", [])},
                            "forbidden": {s: s not in respuesta for s in caso.get("forbidden", [])},
                        }
                        registro["needs_semantic_review"] = True
                    except Exception as exc:
                        registro = {"pregunta": caso["question"], "estado": "error", "error": type(exc).__name__}
                        registro["traza"] = traza.eventos
                    registro.update(case_id=caso["id"], round=ronda,
                                    wall_ms=(time.perf_counter() - inicio) * 1000)
                    latencias.append(registro["wall_ms"])
                    registros.append(registro)
                    rss = _rss()
                    if rss is not None:
                        memoria.append(rss)
        codigo = hashlib.sha256()
        for path in sorted((args.source_root / "ipsis").rglob("*.py")):
            codigo.update(path.relative_to(args.source_root).as_posix().encode())
            codigo.update(path.read_bytes())
        salida = {"pipeline": args.pipeline, "code_hash": codigo.hexdigest(),
                  "environment": {"python": platform.python_version(), "platform": platform.platform(),
                                  "cpu": platform.processor(), "onnx_threads": args.threads},
                  "configuration": getattr(motor, "metadatos_auditoria", {}),
                  "conversation": args.conversation, "startup_ms": arranque_ms,
                  "p50_ms": statistics.median(latencias),
                  "p95_ms": sorted(latencias)[math.ceil(len(latencias) * .95) - 1],
                  "rss_sampled_max_bytes": max(memoria) if memoria else None,
                  "records": registros}
        args.output.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        motor.cerrar()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frozen-source", type=Path, help="copia de código anterior para v1")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--conversation", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--source-root", type=Path, default=REPO, help=argparse.SUPPRESS)
    parser.add_argument("--pipeline", choices=("v1", "v2"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.project, args.questions, args.output = (p.resolve() for p in (args.project, args.questions, args.output))
    if args.threads < 1 or args.rounds < 1:
        parser.error("threads y rounds deben ser positivos")
    preguntas_desde_json(args.questions)
    if args.worker:
        worker(args)
        return
    # Evitar copiar sobre el proyecto servido o guardar reportes dentro de él.
    if args.output == args.project or args.project in args.output.parents:
        parser.error("output debe estar fuera del proyecto original")
    args.output.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=args.output))
    snapshot = run / "snapshot"
    copiar_proyecto(args.project, snapshot)
    codigo_actual = run / "source-current"
    shutil.copytree(REPO / "ipsis", codigo_actual / "ipsis", ignore=shutil.ignore_patterns("__pycache__"))
    for pipeline in ("v1", "v2"):
        replica = run / pipeline
        copiar_proyecto(snapshot, replica)
        codigo = args.frozen_source.resolve() if pipeline == "v1" and args.frozen_source else codigo_actual
        comando = [sys.executable, str(Path(__file__).resolve()), "--worker", "--pipeline", pipeline,
                   "--project", str(replica), "--questions", str(args.questions), "--output", str(run / f"{pipeline}.json"),
                   "--source-root", str(codigo), "--threads", str(args.threads), "--rounds", str(args.rounds)]
        if args.conversation:
            comando.append("--conversation")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        print(f"Running {pipeline} in isolated replica", flush=True)
        with (run / f"{pipeline}.log").open("w", encoding="utf-8") as log:
            subprocess.run(comando, check=True, stdout=log, stderr=log, env=env)
    a, b = (json.loads((run / f"{p}.json").read_text(encoding="utf-8")) for p in ("v1", "v2"))
    if not a["configuration"].get("hash_corpus") or a["configuration"].get("hash_corpus") != b["configuration"].get("hash_corpus"):
        raise ValueError("los motores no utilizaron el mismo corpus indexado")
    pares = [{"case_id": x["case_id"], "round": x["round"], "question": x["pregunta"],
              "v1": x, "v2": y, "needs_semantic_review": True} for x, y in zip(a["records"], b["records"], strict=True)]
    (run / "comparison.json").write_text(json.dumps(pares, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {run / 'comparison.json'}", flush=True)


if __name__ == "__main__":
    main()
