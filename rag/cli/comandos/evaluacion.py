"""Grupo evaluación: evaluar, calibrar, comparar y benchmark."""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from rag.aplicacion.benchmark import benchmark_perfiles
from rag.aplicacion.evaluacion import (
    ErrorCalibracion,
    calibrar_proyecto,
    comparar_reportes,
    ejecutar_benchmark,
    evaluar_backend_activo,
    medir_latencia,
)
from rag.cli.base import Comando

MANIFIESTO_GOLDEN = "golden/banco/manifiesto.json"


def _porcentaje(valor) -> str:
    return "—" if valor is None else f"{valor:.1%}"


class ComandoEvaluar(Comando):
    nombre = "evaluar"
    ayuda = "Corre una evaluación rápida si hay golden set."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--banco", default=MANIFIESTO_GOLDEN,
                            help="Manifiesto versionado del banco (por defecto: golden/banco/manifiesto.json).")
        parser.add_argument("--salida", default=None, help="Ruta opcional para guardar el reporte JSON.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        ruta = Path(args.banco)
        if not ruta.exists():
            print("No hay golden set en golden/banco/ todavía -- no se puede evaluar.")
            print("El formato versionado usa manifiesto.json + golden.jsonl con pregunta, "
                  "categoría, split, estado esperado y evidencia literal con offsets.")
            print("Consulta README.md para el formato y las recomendaciones de evaluación.")
            return 0

        print(f"Evaluando el backend activo contra {ruta}...")
        try:
            artefacto = evaluar_backend_activo(str(ruta))
        except Exception as e:  # noqa: BLE001 -- CLI convierte el fallo en mensaje
            print(f"No se pudo evaluar: {e}")
            return 1
        reporte = artefacto.reporte
        print(f"N={reporte.n_casos} Recall@{reporte.k}={reporte.recall_at_k:.3f} "
              f"MRR={reporte.mrr:.3f} exactitud_estado={reporte.exactitud_estado:.3f}")
        print(f"falsos_ok={reporte.tasa_falsos_ok:.3f} "
              f"precision_abstencion={reporte.precision_abstencion:.3f} "
              f"literalidad={reporte.exactitud_literal:.3f} offsets={reporte.exactitud_offsets:.3f}")
        print(f"respuestas_excesivas={reporte.tasa_respuestas_excesivas:.3f} "
              f"latencia_media={reporte.latencia_media_ms:.1f}ms p95={reporte.latencia_p95_ms:.1f}ms")
        if args.salida:
            salida = Path(args.salida)
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_text(artefacto.model_dump_json(indent=2), encoding="utf-8")
            print(f"Reporte escrito en {salida}")
        veredicto = "CUMPLE" if reporte.guardia_falsos_ok else "BLOQUEADO"
        print(f"Guardia de falsos ok (debe ser 0): {veredicto}")
        return 0 if reporte.guardia_falsos_ok else 1


class ComandoCalibrar(Comando):
    nombre = "calibrar"
    ayuda = "Elige umbrales con el golden importado, con control de riesgo."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--alfa", type=float, default=0.05,
                            help="Riesgo máximo de respuestas directas incorrectas, entre 0 y 1 (por defecto: 0.05).")
        parser.add_argument("--aplicar", action="store_true",
                            help="Guarda el resultado en configuracion/calibracion.yaml "
                                 "(solo se usa si queda calibrado).")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            calibracion = calibrar_proyecto(alfa=args.alfa, aplicar=args.aplicar)
        except ErrorCalibracion as e:
            print("No se pudo calibrar:")
            for error in e.errores:
                print(f"  - {error}")
            return 1
        r, procedencia = calibracion.resultado, calibracion.procedencia
        estado = r.estado.value
        print(f"Calibración: {estado.upper()}  (riesgo objetivo ≤ {r.alfa:.1%}, confianza {r.confianza:.0%})")
        print(f"Perfil {procedencia.perfil}, banco {procedencia.banco}, corpus {procedencia.hash_corpus[:19]}…")
        dev = r.dev
        print(f"Dev (elige los umbrales): {dev.riesgo.n} respuestas directas, {dev.riesgo.x} incorrectas, "
              f"cota superior {_porcentaje(dev.riesgo.cota_superior)}")
        print(f"  cobertura directa {_porcentaje(dev.cobertura_directa)} "
              f"(exactas {_porcentaje(dev.cobertura_exacta)}, paráfrasis {_porcentaje(dev.cobertura_parafrasis)}); "
              f"falsos ok {dev.falsos_ok} (trampas {dev.falsos_ok_trampas})")
        if estado == "calibrado":
            print("Umbrales (perfil → calibrado):")
            for nombre in r.calibrables:
                antes, despues = r.umbrales_perfil[nombre], r.umbrales[nombre]
                marca = "" if antes == despues else "   (cambia)"
                print(f"  {nombre:8} {antes:.4f} → {despues:.4f}{marca}")
        elif estado == "muestra_insuficiente":
            print("Todavía no se puede certificar el riesgo (no significa que el perfil sea inseguro):")
            print(f"  respuestas aceptadas sin error: {r.aceptadas_sin_error_max_dev}")
            print(f"  necesarias para α={r.alfa} al {r.confianza:.0%}: {r.n_minimo_sin_errores}")
            print(f"  faltan al menos: {r.faltan_aceptadas}")
            print("Siguen vigentes los umbrales del perfil.")
        else:
            print(f"Hay muestra suficiente (hasta {r.aceptadas_max_dev} respuestas directas en dev), pero ninguna "
                  f"combinación de umbrales deja la cota ≤ {r.alfa:.1%}.")
            print("Siguen vigentes los umbrales del perfil.")
        if r.test is not None:
            t = r.test
            print(f"Test (solo verifica): {r.verificacion_test}; {t.riesgo.n} respuestas directas, {t.riesgo.x} "
                  f"incorrectas, cota {_porcentaje(t.riesgo.cota_superior)}; cobertura directa "
                  f"{_porcentaje(t.cobertura_directa)}")
        if calibracion.ruta is not None:
            if estado == "calibrado":
                print(f"Calibración guardada y habilitada en {calibracion.ruta}.")
            else:
                print(f"Resultado guardado para auditoría en {calibracion.ruta}. "
                      "Los umbrales del perfil siguen activos.")
        elif estado == "calibrado":
            print("No se guardó nada: usa 'rag calibrar --aplicar' para habilitar estos umbrales.")
        return 1 if estado == "sin_umbral_seguro" else 0


class ComandoComparar(Comando):
    nombre = "comparar"
    ayuda = "Compara artefactos producidos por 'rag evaluar'."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("artefactos", nargs="+", help="Dos o más reportes JSON comparables.")
        parser.add_argument("--salida", default="reportes/comparacion.json", help="Ruta del informe consolidado.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            informe, salida = comparar_reportes(args.artefactos, args.salida)
        except Exception as e:  # noqa: BLE001
            print(f"No se pudo comparar: {e}")
            return 1
        print(f"Dataset {informe.dataset_id}@{informe.dataset_version}, k={informe.k}")
        for fila in informe.filas:
            print(f"{fila.backend}: Recall={fila.recall_at_k:.3f} MRR={fila.mrr:.3f} "
                  f"falsos_ok={fila.tasa_falsos_ok:.3f} estado={fila.exactitud_estado:.3f} "
                  f"latencia_p95={fila.latencia_p95_ms:.1f}ms")
        print(f"Informe comparativo escrito en {salida}")
        return 0


class ComandoBenchmark(Comando):
    """Tres modos: perfiles (``--perfiles``), solo latencia o modos de recuperación.
    Los modos que crean proyectos temporales reciben ``main`` para ejecutar comandos."""

    nombre = "benchmark"
    ayuda = "Compara perfiles (calidad, seguridad, latencia y costo), modos de recuperación o solo la latencia."

    def __init__(self, ejecutar_cli: Callable[[list[str]], int]) -> None:
        self.ejecutar_cli = ejecutar_cli

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--banco", required=True, action="append",
                            help="Manifiesto versionado a evaluar; repetible (p. ej. un banco por idioma).")
        parser.add_argument("--solo-latencia", action="store_true",
                            help="Mide p50/p95 por etapa de cada perfil frente a su presupuesto.")
        parser.add_argument("--perfiles", default=None,
                            help="Perfiles a comparar (bm25,light,medium,heavy). Con --solo-latencia, "
                                 "por defecto light,medium.")
        parser.add_argument("--experimentos", action="store_true",
                            help="Agrega variantes experimentales (medium con τ_ok 0,85; light con acuerdo).")
        parser.add_argument("--repeticiones", type=int, default=20,
                            help="Veces que se repite cada pregunta con --solo-latencia (por defecto: 20).")
        parser.add_argument("--salida", default=None,
                            help="Directorio de salida (por defecto: golden/reportes con --perfiles, "
                                 "si no reportes/benchmark).")

    def ejecutar(self, args: argparse.Namespace) -> int:
        if args.perfiles and not args.solo_latencia:
            return self._perfiles(args)
        if args.solo_latencia:
            return self._solo_latencia(args)
        try:
            ruta = ejecutar_benchmark(args.banco[0], args.salida or "reportes/benchmark", self.ejecutar_cli)
        except Exception as e:  # noqa: BLE001
            print(f"No se pudo ejecutar el benchmark: {e}")
            return 1
        print(f"Benchmark reproducible escrito en {ruta}")
        print("El informe no toma decisiones; revísalo antes de cambiar defaults o umbrales.")
        return 0

    def _perfiles(self, args: argparse.Namespace) -> int:
        perfiles = [p.strip() for p in args.perfiles.split(",") if p.strip()]
        try:
            reporte, ruta_json, ruta_md, salida, codigo = benchmark_perfiles(
                args.banco, perfiles, self.ejecutar_cli, args.salida, experimentos=args.experimentos)
        except (ValueError, RuntimeError) as e:
            print(f"No se pudo ejecutar el benchmark: {e}")
            return 1
        print(reporte.nota)
        for p in reporte.perfiles:
            c = p.cobertura.total
            marca = "" if p.variante else (" [cumple]" if p.cumple_presupuesto else " [EXCEDE el presupuesto]")
            print(f"{p.nombre:16} cobertura directa {c.cobertura_directa or 0:.1%}  falsos ok {c.falsos_ok}/"
                  f"{c.no_respondibles}  p50 {p.latencia.p50} ms  p95 {p.latencia.p95} ms "
                  f"(presupuesto {p.presupuesto_p95_ms}){marca}")
        print(f"Reporte en {ruta_md} y {ruta_json}; artefactos por perfil para 'rag comparar' en {salida}.")
        return codigo

    def _solo_latencia(self, args: argparse.Namespace) -> int:
        perfiles = [p.strip() for p in (args.perfiles or "light,medium").split(",") if p.strip()]
        informe = medir_latencia(args.banco[0], perfiles, self.ejecutar_cli, repeticiones=args.repeticiones)
        salida = Path(args.salida or "reportes/benchmark")
        salida.mkdir(parents=True, exist_ok=True)
        (salida / "latencia.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
        for perfil, datos in informe["perfiles"].items():
            marca = "ok" if datos["cumple_presupuesto"] else "EXCEDE"
            print(f"{perfil}: p50 {datos['total']['p50']} ms, p95 {datos['total']['p95']} ms "
                  f"(presupuesto {datos['presupuesto_p95_ms']} ms) [{marca}]")
            for etapa, valores in datos["etapas"].items():
                print(f"    {etapa:15} p50 {valores['p50']:7} ms   p95 {valores['p95']:7} ms")
        return 0 if all(d["cumple_presupuesto"] for d in informe["perfiles"].values()) else 1


__all__ = ["ComandoBenchmark", "ComandoCalibrar", "ComandoComparar", "ComandoEvaluar"]
