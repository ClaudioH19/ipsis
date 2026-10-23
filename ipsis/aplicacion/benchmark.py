"""``ipsis benchmark --profiles``: cada perfil sobre los mismos bancos y corpus.

Por perfil y banco crea un proyecto temporal (``ipsis init`` en el idioma del
banco, ``cargar``, ``indexar``), evalúa con ``evaluar_backend_activo`` (el
motor se calienta antes de medir) y junta las observaciones. Las métricas y
el reporte son puros (``ipsis.evaluacion.benchmark``).

"""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path


from ipsis.evaluacion.benchmark import (
    BancoUsado,
    ModeloCargado,
    ReporteBenchmark,
    ResultadoPerfil,
    latencia_de,
    nota_de,
    percentil,
)
from ipsis.recursos.mensajes import t

PERFILES_BENCHMARK = ("bm25", "light", "medium")


def _modelos(perfil) -> list[ModeloCargado]:
    from ipsis.modelos.catalogo import obtener
    from ipsis.modelos.descarga import ruta_local

    salida = []
    for rol in ("denso", "reranker", "lector"):
        id_hf = getattr(perfil.modelos, rol)
        if not id_hf:
            continue
        spec = obtener(id_hf)
        try:
            carpeta = ruta_local(spec)
            archivo = carpeta / spec.archivo_onnx()
            onnx = [archivo, *(carpeta / p for p in spec.datos_onnx())]
            mb = round(sum(p.stat().st_size for p in onnx if p.is_file()) / 1e6, 1) if archivo.is_file() else None
        except FileNotFoundError:
            mb = None
        salida.append(ModeloCargado(rol=rol, id_hf=id_hf, parametros=spec.parametros, onnx_mb=mb))
    return salida


def _fijar_perfil(perfil: str) -> None:
    """bm25 no se ofrece en ``ipsis init``: se fija en el proyecto temporal."""
    from ipsis.configuracion import rutas

    from ipsis.configuracion.archivos import escribir, leer

    datos = leer(rutas.ASISTENTE, "asistente")
    datos["perfil"] = perfil
    escribir(rutas.ASISTENTE, datos, "asistente")


def _evaluar_en_proyecto(perfil: str, manifiesto: Path, banco, main, ajustes: dict | None = None):
    """Proyecto temporal del perfil para un banco: el artefacto de la evaluación y los segundos que tardó el índice."""
    from ipsis.aplicacion.evaluacion import evaluar_backend_activo
    from ipsis.lenguaje.entidades import configurar_idioma, configurar_perfil, idioma_activo, perfil_activo

    corpus = (manifiesto.parent / banco.manifiesto.corpus.directorio).resolve()
    anterior, idioma_previo, perfil_previo = Path.cwd(), idioma_activo(), perfil_activo()
    # ignore_cleanup_errors: en Windows un cliente Qdrant aún abierto bloquea
    # el índice y, sin esto, el error de limpieza taparía el error real.
    with tempfile.TemporaryDirectory(prefix=f"rag_benchmark_{perfil}_", ignore_cleanup_errors=True) as temporal:
        try:
            os.chdir(temporal)
            with contextlib.redirect_stdout(io.StringIO()):
                init = ["init", "--profile", "light" if perfil == "bm25" else perfil]
                if banco.manifiesto.idioma:
                    init += ["--language", banco.manifiesto.idioma]
                if main(init) != 0:
                    raise RuntimeError(t("app.init_failed_for", profile=perfil))
                if perfil == "bm25":
                    _fijar_perfil("bm25")
                if ajustes:
                    from ipsis.configuracion import rutas
                    from ipsis.configuracion.archivos import leer, escribir

                    config = leer(rutas.MOTOR, "motor")
                    config["ajustes_perfil"] = ajustes
                    escribir(rutas.MOTOR, config, "motor")
                for archivo in banco.manifiesto.corpus.archivos:
                    if main(["load", str(corpus / archivo.ruta)]) != 0:
                        raise RuntimeError(t("app.load_failed", file=archivo.ruta))
                inicio = time.perf_counter()
                if main(["index"]) != 0:
                    raise RuntimeError(t("app.index_failed", what=perfil))
                indexado = time.perf_counter() - inicio
                artefacto = evaluar_backend_activo(str(manifiesto))
        finally:
            os.chdir(anterior)
            # ipsis index fija el idioma y el perfil del proceso: se restauran.
            configurar_idioma(idioma_previo)
            configurar_perfil(perfil_previo)
    return artefacto, indexado


def ejecutar_benchmark_perfiles(
    manifiestos: list[str],
    perfiles: list[str],
    main: Callable[[list[str]], int],
    salida: str | Path,
    *,
    evaluar_perfil: Callable | None = None,
) -> ReporteBenchmark:
    """Evalúa cada perfil, en el orden pedido, sobre todos los bancos.

    ``main`` es ``ipsis.cli.main`` (se inyecta para no depender de la CLI).
    ``evaluar_perfil(perfil, manifiesto, banco)`` reemplaza la evaluación real en las
    pruebas y devuelve ``(artefacto, indexado_s)``.
    """
    from ipsis.configuracion.perfiles import perfil_efectivo
    from ipsis.evaluacion.banco import cargar_banco
    from ipsis.evaluacion.metricas import reporte_cobertura

    desconocidos = [p for p in perfiles if p not in PERFILES_BENCHMARK]
    if desconocidos:
        raise ValueError(t("app.unknown_profiles", profiles=desconocidos, valid=", ".join(PERFILES_BENCHMARK)))
    rutas_bancos = [Path(m).resolve() for m in manifiestos]
    bancos = [cargar_banco(m) for m in rutas_bancos]
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    evaluar = evaluar_perfil or (lambda p, m, b: _evaluar_en_proyecto(p, m, b, main))

    resultados: list[ResultadoPerfil] = []
    artefactos: list[str] = []
    for perfil in perfiles:
        pares, observaciones, indexado, tono = [], [], 0.0, None
        for manifiesto, banco in zip(rutas_bancos, bancos):
            artefacto, segundos = evaluar(perfil, manifiesto, banco)
            # ipsis compare exige una etiqueta de backend por ejecución: la del perfil.
            artefacto = artefacto.model_copy(update={"backend": f"{perfil}:{artefacto.backend}"})
            indexado += segundos
            ruta = salida / f"benchmark-{perfil}-{banco.manifiesto.dataset_id}.json"
            ruta.write_text(artefacto.model_dump_json(indent=2), encoding="utf-8")
            artefactos.append(str(ruta))
            por_id = {o.caso_id: o for o in artefacto.observaciones}
            if set(por_id) != {c.id for c in banco.casos}:
                raise RuntimeError(t("app.cases_mismatch", profile=perfil, bank=banco.manifiesto.dataset_id))
            pares += [(c, por_id[c.id]) for c in banco.casos]
            observaciones += list(artefacto.observaciones)
            tono = artefacto.tono or tono
        instalacion = perfil_efectivo(perfil)
        latencia = latencia_de(observaciones)
        resultados.append(ResultadoPerfil(
            nombre=perfil, perfil=perfil, presupuesto_p95_ms=instalacion.presupuesto_p95_ms, latencia=latencia,
            cumple_presupuesto=latencia.p95 <= instalacion.presupuesto_p95_ms,
            cobertura=reporte_cobertura(pares), modelos=_modelos(instalacion),
            recuperacion=instalacion.recuperacion_modo or "hibrida",
            tiempo_indexado_s=round(indexado, 1),
            tono=tono,
        ))

    usados = [BancoUsado(dataset_id=b.manifiesto.dataset_id, dataset_version=b.manifiesto.dataset_version,
                         uso=b.manifiesto.uso, idioma=b.manifiesto.idioma, n_casos=len(b.casos)) for b in bancos]
    from ipsis.evaluacion.metricas import CRITERIO_RESPUESTA

    return ReporteBenchmark(schema_version=3, criterio_respuesta=CRITERIO_RESPUESTA,
                            bancos=usados, nota=nota_de(usados), perfiles=resultados, artefactos=artefactos)


def escribir_reporte_benchmark(reporte: ReporteBenchmark, salida: str | Path) -> tuple[Path, Path]:
    from ipsis.evaluacion.benchmark import markdown
    from ipsis.evaluacion.golden import escribir_atomico

    salida = Path(salida)
    json_ruta, md_ruta = salida / "benchmark-profiles.json", salida / "benchmark-profiles.md"
    escribir_atomico(json_ruta, reporte.model_dump_json(indent=2) + "\n")
    escribir_atomico(md_ruta, markdown(reporte))
    return json_ruta, md_ruta


def benchmark_perfiles(manifiestos: list[str], perfiles: list[str], main, salida: str | Path | None = None):
    """``ipsis benchmark --profiles``: ejecuta, escribe los reportes y decide la
    salida. Devuelve ``(reporte, ruta_json, ruta_md, carpeta, codigo)``."""
    from ipsis.configuracion import rutas
    from ipsis.evaluacion.benchmark import codigo_salida

    carpeta = Path(salida or rutas.GOLDEN_REPORTES)
    reporte = ejecutar_benchmark_perfiles(manifiestos, perfiles, main, carpeta)
    ruta_json, ruta_md = escribir_reporte_benchmark(reporte, carpeta)
    return reporte, ruta_json, ruta_md, carpeta, codigo_salida(reporte)


__all__ = ["PERFILES_BENCHMARK", "benchmark_perfiles", "ejecutar_benchmark_perfiles",
           "escribir_reporte_benchmark"]
