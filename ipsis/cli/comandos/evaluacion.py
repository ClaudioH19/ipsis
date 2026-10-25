"""Grupo evaluación: evaluar, comparar y benchmark."""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ipsis.aplicacion.benchmark import benchmark_perfiles
from ipsis.aplicacion.evaluacion import (
    comparar_reportes,
    ejecutar_benchmark,
    evaluar_backend_activo,
    medir_latencia,
)
from ipsis.cli.base import Comando
from ipsis.recursos.mensajes import t

MANIFIESTO_GOLDEN = "golden/bank/manifest.json"
SALIDA_BENCHMARK = "reports/benchmark"


def _porcentaje(valor) -> str:
    return t("cli.none") if valor is None else f"{valor:.1%}"


class ComandoEvaluar(Comando):
    nombre = "evaluate"
    ayuda = "evaluate.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--bank", dest="banco", default=MANIFIESTO_GOLDEN, help=t("evaluate.opt_bank"))
        parser.add_argument("--output", dest="salida", default=None, help=t("evaluate.opt_output"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        ruta = Path(args.banco)
        if not ruta.exists():
            print(t("evaluate.no_golden"))
            print(t("evaluate.format"))
            print(t("evaluate.see_docs"))
            return 0

        print(t("evaluate.running", path=ruta))
        try:
            artefacto = evaluar_backend_activo(str(ruta))
        except Exception as e:  # noqa: BLE001 -- CLI convierte el fallo en mensaje
            print(t("evaluate.failed", error=e))
            return 1
        r = artefacto.reporte
        print(t("evaluate.line1", n=r.n_casos, k=r.k, recall=r.recall_at_k, mrr=r.mrr, status=r.exactitud_estado))
        print(t("evaluate.line2", false_ok=r.tasa_falsos_ok, abstention=r.precision_abstencion,
                literal=r.exactitud_literal, offsets=r.exactitud_offsets))
        print(t("evaluate.line3", excessive=r.tasa_respuestas_excesivas, mean=r.latencia_media_ms,
                p95=r.latencia_p95_ms))
        c = r.cobertura.total
        riesgo = r.cobertura.riesgo_aceptadas
        print(t("evaluate.answers", correct=c.directas_con_literal, direct=c.directas,
                coverage=_porcentaje(c.cobertura_literal), errors=riesgo.x, criterion=r.criterio_respuesta))
        print(t("evaluate.qa", n=c.tramos_qa_evaluados, incomplete=c.tramos_qa_sin_literal,
                accuracy=_porcentaje(c.exactitud_tramo_qa)))
        if args.salida:
            salida = Path(args.salida)
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_text(artefacto.model_dump_json(indent=2), encoding="utf-8")
            print(t("evaluate.written", path=salida))
        print(t("evaluate.guard", verdict=t("evaluate.pass" if r.guardia_respuestas else "evaluate.blocked")))
        return 0 if r.guardia_respuestas else 1


class ComandoComparar(Comando):
    nombre = "compare"
    ayuda = "compare.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("artefactos", metavar="reports", nargs="+", help=t("compare.arg_reports"))
        parser.add_argument("--output", dest="salida", default="reports/comparison.json",
                            help=t("compare.opt_output"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            informe, salida = comparar_reportes(args.artefactos, args.salida)
        except Exception as e:  # noqa: BLE001
            print(t("compare.failed", error=e))
            return 1
        print(t("compare.dataset", id=informe.dataset_id, version=informe.dataset_version, k=informe.k))
        for fila in informe.filas:
            print(t("compare.row", backend=fila.backend, recall=fila.recall_at_k, mrr=fila.mrr,
                    false_ok=fila.tasa_falsos_ok, status=fila.exactitud_estado, p95=fila.latencia_p95_ms))
            print(t("compare.answer_quality", literal=_porcentaje(fila.exactitud_literal),
                    qa=_porcentaje(fila.exactitud_tramo_qa), criterion=informe.criterio_respuesta))
        print(t("compare.written", path=salida))
        return 0


class ComandoBenchmark(Comando):
    """Tres modos: perfiles (``--profiles``), solo latencia o modos de recuperación.
    Los modos que crean proyectos temporales reciben ``main`` para ejecutar comandos."""

    nombre = "benchmark"
    ayuda = "benchmark.help"

    def __init__(self, ejecutar_cli: Callable[[list[str]], int]) -> None:
        self.ejecutar_cli = ejecutar_cli

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--bank", dest="banco", required=True, action="append", help=t("benchmark.opt_bank"))
        parser.add_argument("--latency-only", dest="solo_latencia", action="store_true",
                            help=t("benchmark.opt_latency_only"))
        parser.add_argument("--profiles", dest="perfiles", default=None, help=t("benchmark.opt_profiles"))
        parser.add_argument("--repetitions", dest="repeticiones", type=int, default=20,
                            help=t("benchmark.opt_repetitions"))
        parser.add_argument("--output", dest="salida", default=None, help=t("benchmark.opt_output"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        if args.perfiles and not args.solo_latencia:
            return self._perfiles(args)
        if args.solo_latencia:
            return self._solo_latencia(args)
        try:
            ruta = ejecutar_benchmark(args.banco[0], args.salida or SALIDA_BENCHMARK, self.ejecutar_cli)
        except Exception as e:  # noqa: BLE001
            print(t("benchmark.failed", error=e))
            return 1
        print(t("benchmark.written", path=ruta))
        print(t("benchmark.no_decisions"))
        return 0

    def _perfiles(self, args: argparse.Namespace) -> int:
        perfiles = [p.strip() for p in args.perfiles.split(",") if p.strip()]
        try:
            reporte, ruta_json, ruta_md, salida, codigo = benchmark_perfiles(
                args.banco, perfiles, self.ejecutar_cli, args.salida)
        except (ValueError, RuntimeError) as e:
            print(t("benchmark.failed", error=e))
            return 1
        print(reporte.nota)
        for p in reporte.perfiles:
            c = p.cobertura.total
            marca = t("benchmark.within" if p.cumple_presupuesto else "benchmark.over")
            print(t("benchmark.profile_row", name=p.nombre, coverage=c.cobertura_directa or 0, false_ok=c.falsos_ok,
                    unanswerable=c.no_respondibles, p50=p.latencia.p50, p95=p.latencia.p95,
                    budget=p.presupuesto_p95_ms, mark=marca))
            print(t("evaluate.answers", correct=c.directas_con_literal, direct=c.directas,
                    coverage=_porcentaje(c.cobertura_literal), errors=p.cobertura.riesgo_aceptadas.x,
                    criterion=p.cobertura.criterio_respuesta))
            print(t("evaluate.qa", n=c.tramos_qa_evaluados, incomplete=c.tramos_qa_sin_literal,
                    accuracy=_porcentaje(c.exactitud_tramo_qa)))
        print(t("benchmark.reports", md=ruta_md, json=ruta_json, folder=salida))
        return codigo

    def _solo_latencia(self, args: argparse.Namespace) -> int:
        perfiles = [p.strip() for p in (args.perfiles or "light,medium").split(",") if p.strip()]
        informe = medir_latencia(args.banco[0], perfiles, self.ejecutar_cli, repeticiones=args.repeticiones)
        salida = Path(args.salida or SALIDA_BENCHMARK)
        salida.mkdir(parents=True, exist_ok=True)
        (salida / "latency.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
        for perfil, datos in informe["perfiles"].items():
            marca = t("benchmark.ok" if datos["cumple_presupuesto"] else "benchmark.over_short")
            print(t("benchmark.latency_row", profile=perfil, p50=datos["total"]["p50"], p95=datos["total"]["p95"],
                    budget=datos["presupuesto_p95_ms"], mark=marca))
            for etapa, valores in datos["etapas"].items():
                print(t("benchmark.stage_row", stage=etapa, p50=valores["p50"], p95=valores["p95"]))
        return 0 if all(d["cumple_presupuesto"] for d in informe["perfiles"].values()) else 1


__all__ = ["ComandoBenchmark", "ComandoCalibrar", "ComandoComparar", "ComandoEvaluar"]
