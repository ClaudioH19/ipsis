"""Regresión documental reproducible: formatos, temas, calidad y variantes de modelos."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import time

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "tests/datos/banco_general"
sys.path.insert(0, str(RAIZ))


def aciertos(casos):
    return {c["caso_id"] for c in casos if c["directa"] and not c["falso_ok"] and not c["directa_sin_literal"]}


def errores(casos):
    return {c["caso_id"] for c in casos if c["falso_ok"] or c["directa_sin_literal"]}


def negativos_resueltos(casos):
    return {c["caso_id"] for c in casos if c.get("respondible") is False
            and c.get("estado") == c.get("estado_esperado")}


def comparar(actual, base):
    """Perder un acierto o introducir un error falla aunque el total no cambie."""
    if base.get("criterio") != actual["criterio"]:
        return ["Criterios de evaluación incompatibles; volver a medir la línea base"]
    anteriores = {(r["nombre"], r["dataset_id"]): r for r in base["resultados"]}
    fallos = []
    if not actual["resultados"]:
        return ["La evaluación no produjo resultados"]
    if len(anteriores) != len(base["resultados"]):
        return ["Referencia con trabajos duplicados"]
    for fila in actual["resultados"]:
        llave = (fila["nombre"], fila["dataset_id"])
        previo = anteriores.get(llave)
        if previo is None:
            fallos.append(f"Sin referencia para {llave}")
            continue
        if fila["dataset_sha256"] != previo["dataset_sha256"]:
            fallos.append(f"Cambió el banco de {llave}; revisar y versionar la referencia")
            continue
        if {c["caso_id"] for c in fila["casos"]} != {c["caso_id"] for c in previo["casos"]}:
            fallos.append(f"Cambió el conjunto de casos de {llave}")
            continue
        perdidos = aciertos(previo["casos"]) - aciertos(fila["casos"])
        nuevos = errores(fila["casos"]) - errores(previo["casos"])
        negativos_perdidos = negativos_resueltos(previo["casos"]) - negativos_resueltos(fila["casos"])
        if perdidos:
            fallos.append(f"{llave}: perdió aciertos {sorted(perdidos)}")
        if nuevos:
            fallos.append(f"{llave}: nuevos errores aceptados {sorted(nuevos)}")
        if negativos_perdidos:
            fallos.append(f"{llave}: perdió abstenciones/aclaraciones/conversación correctas {sorted(negativos_perdidos)}")
        if actual.get("hardware") == base.get("hardware"):
            limite = max(fila["presupuesto_p95_ms"], previo["latencia"]["p95"] * 1.25)
            if fila["latencia"]["p95"] > limite:
                fallos.append(f"{llave}: p95 {fila['latencia']['p95']} ms supera {limite:.1f} ms")
    return fallos


def markdown(reporte):
    lineas = ["# Regresión documental general", "", f"Criterio: `{reporte['criterio']}`.", "",
        "Corpus sintético. Los errores conocidos de la referencia no son una garantía de precisión.", "",
        "| Perfil / variante | Banco | Correctas / respondibles | Errores / directas | Negativas sin directa | Estados negativos esperados | QA completas / evaluadas | p95 ms | Presupuesto p95 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for fila in reporte["resultados"]:
        c = fila["cobertura"]
        qa = "—" if not c["tramos_qa_evaluados"] else f"{c['tramos_qa_evaluados']-c['tramos_qa_sin_literal']}/{c['tramos_qa_evaluados']}"
        negativos = sum(caso["respondible"] is False for caso in fila["casos"])
        rechazos = sum(caso["respondible"] is False and not caso["directa"] for caso in fila["casos"])
        cumple = "sí" if fila["latencia"]["p95"] <= fila["presupuesto_p95_ms"] else "NO"
        lineas.append(f"| {fila['nombre']} | {fila['dataset_id']} | {c['directas_con_literal']}/{c['respondibles']} | "
                      f"{len(errores(fila['casos']))}/{c['directas']} | {rechazos}/{negativos} | {len(negativos_resueltos(fila['casos']))}/{negativos} | "
                      f"{qa} | {fila['latencia']['p95']} | {cumple} ({fila['presupuesto_p95_ms']} ms) |")
    lineas += ["", "## Fallos de ejecución o regresión", ""]
    lineas += [f"- {f}" for f in reporte["fallos"]] or ["Ninguno."]
    lineas += ["", "## Errores de contenido observados", ""]
    for fila in reporte["resultados"]:
        for caso in fila["casos"]:
            if caso["caso_id"] in errores(fila["casos"]):
                lineas.append(f"- {fila['nombre']} / {fila['dataset_id']} / `{caso['caso_id']}`: {caso['pregunta']}")
    return "\n".join(lineas) + "\n"


def ejecutar(perfiles, variantes, manifiestos, salida, descargar=False, condiciones=None):
    from ipsis.aplicacion.benchmark import _evaluar_en_proyecto
    from ipsis.cli import main
    from ipsis.configuracion.perfiles import perfil_efectivo
    from ipsis.configuracion.variantes_modelos import ajustes_variante
    from ipsis.evaluacion.banco import cargar_banco, validar_evidencias_contra_corpus
    from ipsis.evaluacion.benchmark import latencia_de
    from ipsis.ingesta.parsear import parsear_documento
    from ipsis.modelos.catalogo import obtener
    from ipsis.modelos.descarga import descargar as bajar, ruta_local

    bancos = [(p.resolve(), cargar_banco(p)) for p in manifiestos]
    if len({b.manifiesto.dataset_id for _, b in bancos}) != len(bancos):
        raise ValueError("No se permiten bancos con dataset_id duplicado")
    for p, banco in bancos:
        textos = {a.doc_id: parsear_documento(str(p.parent / banco.manifiesto.corpus.directorio / a.ruta),
                  doc_id=a.doc_id, doc_titulo=a.doc_id, version="1").texto_completo for a in banco.manifiesto.corpus.archivos}
        validar_evidencias_contra_corpus(banco, textos)
    trabajos = [(p, p, None) for p in perfiles] + [("medium+"+v, "medium", ajustes_variante(v)) for v in variantes]
    import onnxruntime

    reporte = {"schema_version": 1, "criterio": "respuesta_completa_v2",
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "trabajos_esperados": len(trabajos) * len(bancos),
        "hardware": {"sistema": platform.system(), "maquina": platform.machine(), "cpu": platform.processor(),
                     "hilos": os.environ.get("IPSIS_ONNX_THREADS", "2"), "onnxruntime": onnxruntime.__version__},
        "fuentes_sha256": {str(p.relative_to(RAIZ)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted((RAIZ / "ipsis").rglob("*"))
                           if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"},
        "resultados": [], "fallos": []}
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, perfil, ajustes in trabajos:
        efectivo = perfil_efectivo(perfil, ajustes, ruta_calibracion=None)
        try:
            for id_hf in efectivo.modelos.model_dump().values():
                if id_hf:
                    bajar(obtener(id_hf)) if descargar else ruta_local(obtener(id_hf))
        except Exception as exc:
            reporte["fallos"].append(f"{nombre}: modelos no disponibles: {exc}")
            print(reporte["fallos"][-1], flush=True)
            continue
        for manifiesto, banco in bancos:
            print(f"Midiendo {nombre} / {banco.manifiesto.dataset_id} ({len(banco.casos)} casos)...", flush=True)
            inicio = time.perf_counter()
            try:
                artefacto, indexado, _ = _evaluar_en_proyecto(perfil, manifiesto, banco, main, False, ajustes, condiciones)
                artefacto = artefacto.model_copy(update={"backend": nombre})
                ruta = salida / f"{nombre.replace('+', '-')}-{banco.manifiesto.dataset_id}.json"
                ruta.write_text(artefacto.model_dump_json(indent=2)+"\n", encoding="utf-8")
                c = artefacto.reporte.cobertura
                fila = {"nombre": nombre, "dataset_id": banco.manifiesto.dataset_id,
                    "dataset_sha256": artefacto.dataset_sha256, "configuracion_sha256": artefacto.configuracion_sha256,
                    "modelos": {rol: obtener(m).model_dump(mode="json") for rol, m in efectivo.modelos.model_dump().items() if m},
                    "perfil_resuelto": efectivo.model_dump(mode="json"),
                    "presupuesto_p95_ms": efectivo.presupuesto_p95_ms,
                    "latencia": latencia_de(artefacto.observaciones).model_dump(), "indexado_s": round(indexado, 2),
                    "cobertura": c.total.model_dump(), "casos": [f.model_dump() for f in c.casos], "artefacto": ruta.name}
                reporte["resultados"].append(fila)
                print(f"  Correctas {c.total.directas_con_literal}/{c.total.respondibles}; errores {c.riesgo_aceptadas.x}; "
                      f"p95 {fila['latencia']['p95']} ms; total {time.perf_counter()-inicio:.1f} s", flush=True)
            except Exception as exc:
                reporte["fallos"].append(f"{nombre} / {banco.manifiesto.dataset_id}: {type(exc).__name__}: {exc}")
                print(reporte["fallos"][-1], flush=True)
            finally:
                gc.collect()
            (salida / "general.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return reporte


def cli(argv=None):
    from ipsis.configuracion.variantes_modelos import VARIANTES_MODELOS

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profiles", default="light,medium")
    p.add_argument("--variants", default="", help="all o nombres de variantes separados por coma")
    p.add_argument("--qualities", default="bueno,medio,malo", help="bueno,medio,malo; none para medir solo --extra-bank")
    p.add_argument("--extra-bank", type=Path, action="append", default=[])
    p.add_argument("--output", type=Path, default=RAIZ / ".cache/regresion-general")
    p.add_argument("--baseline", type=Path, default=BANCO / "linea_base.json")
    p.add_argument("--no-baseline", action="store_true", help="Medición exploratoria; no exige la referencia")
    p.add_argument("--record-baseline", action="store_true", help="Guardar una referencia nueva, tras revisar resultados")
    p.add_argument("--strict", action="store_true", help="Exigir cero errores aceptados y presupuesto absoluto")
    p.add_argument("--download", action="store_true", help="Descargar los modelos requeridos antes de medir")
    args = p.parse_args(argv)
    perfiles = [x for x in args.profiles.split(",") if x]
    variantes = list(VARIANTES_MODELOS) if args.variants == "all" else [x for x in args.variants.split(",") if x]
    calidades = [] if args.qualities == "none" else [x for x in args.qualities.split(",") if x]
    if (not perfiles and not variantes) or set(perfiles)-{"light", "medium"} or set(variantes)-set(VARIANTES_MODELOS):
        p.error("Perfil o variante inválidos")
    if set(calidades)-{"bueno", "medio", "malo"} or (not calidades and not args.extra_bank):
        p.error("Calidades permitidas: bueno,medio,malo; none requiere --extra-bank")
    if any(len(xs) != len(set(xs)) for xs in (perfiles, variantes, calidades)):
        p.error("No se permiten selecciones duplicadas")
    if not args.no_baseline and not args.record_baseline and not args.baseline.is_file():
        p.error("Falta la referencia; usa --no-baseline para explorar y revisa antes de --record-baseline")
    os.environ.setdefault("IPSIS_ONNX_THREADS", "2")
    manifiestos = [BANCO / c / "manifiesto.json" for c in calidades] + args.extra_bank
    salida = args.output.resolve()
    reporte = ejecutar(perfiles, variantes, manifiestos, salida, args.download)
    if not args.no_baseline and not args.record_baseline:
        reporte["fallos"] += comparar(reporte, json.loads(args.baseline.read_text(encoding="utf-8")))
    if args.strict:
        for r in reporte["resultados"]:
            if errores(r["casos"]) or r["latencia"]["p95"] > r["presupuesto_p95_ms"]:
                reporte["fallos"].append(f"{r['nombre']} / {r['dataset_id']}: incumple modo estricto")
    reporte["modo"] = "referencia_nueva" if args.record_baseline else "exploratorio" if args.no_baseline else "regresion"
    for extension, contenido in (("json", json.dumps(reporte, ensure_ascii=False, indent=2)+"\n"), ("md", markdown(reporte))):
        (salida / f"general.{extension}").write_text(contenido, encoding="utf-8")
    if args.record_baseline:
        if reporte["fallos"]:
            print("No se guarda una referencia con fallos de ejecución o validación", flush=True)
        else:
            args.baseline.parent.mkdir(parents=True, exist_ok=True)
            args.baseline.write_text(json.dumps(reporte, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Reporte: {salida / 'general.md'}; fallos: {len(reporte['fallos'])}", flush=True)
    return int(bool(reporte["fallos"]))


if __name__ == "__main__":
    raise SystemExit(cli())
