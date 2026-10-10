"""``ipsis benchmark --profiles``: cada perfil sobre los mismos bancos y corpus.

Por perfil y banco crea un proyecto temporal (``ipsis init`` en el idioma del
banco, ``cargar``, ``indexar``), evalúa con ``evaluar_backend_activo`` (el
motor se calienta antes de medir) y junta las observaciones. Las métricas y
el reporte son puros (``ipsis.evaluacion.benchmark``).

Variantes experimentales (``--experiments``), sin tocar el pipeline:

- ``medium+ok0.85``: re-decide las observaciones de medium con ``τ_ok = 0,85``
  (``redecidir``, la misma regla que producción). Cambiar un umbral no cambia
  el costo: la latencia es la de medium.
- ``light+acuerdo``: con el índice de light, calcula ``acuerdo`` (top-3 solo
  denso vs. solo BM25) con dos búsquedas extra por pregunta, mide su costo y
  exige ``acuerdo ≥ 0,5`` para un ok léxico.
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
OK_EXPERIMENTAL_MEDIUM = 0.85


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


def _acuerdo_por_caso(banco) -> tuple[dict[str, float], dict[str, float]]:
    """Con el índice del proyecto actual: ``acuerdo`` y el costo de sus dos
    búsquedas extra (ms) por caso. El vector de la pregunta se reutiliza, como
    lo haría producción."""
    from ipsis.aplicacion.consulta import construir_motor
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto
    from ipsis.indice.qdrant import buscar
    from ipsis.lenguaje.lexico import acuerdo

    motor = construir_motor(cargar_proyecto(), cfg_dominio=cargar_dominio())
    try:
        motor.calentar()
        coleccion = motor.retriever.coleccion
        valores, costo = {}, {}
        for caso in banco.casos:
            vector = motor.retriever._codificar(caso.pregunta)
            inicio = time.perf_counter()
            denso = buscar(coleccion, caso.pregunta, "vectorial", 3, vector_precomputado=vector)
            disperso = buscar(coleccion, caso.pregunta, "dispersa", 3, vector_precomputado=vector)
            costo[caso.id] = (time.perf_counter() - inicio) * 1000
            valores[caso.id] = acuerdo(denso.ids_ordenados, disperso.ids_ordenados)
        return valores, costo
    finally:
        motor.cerrar()


def _evaluar_en_proyecto(perfil: str, manifiesto: Path, banco, main, experimentos: bool,
                         ajustes: dict | None = None):
    """Proyecto temporal del perfil para un banco: artefacto, indexado y acuerdo."""
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
                acuerdo = _acuerdo_por_caso(banco) if experimentos and perfil == "light" else None
        finally:
            os.chdir(anterior)
            # ipsis index fija el idioma y el perfil del proceso: se restauran.
            configurar_idioma(idioma_previo)
            configurar_perfil(perfil_previo)
    return artefacto, indexado, acuerdo


def ejecutar_benchmark_perfiles(
    manifiestos: list[str],
    perfiles: list[str],
    main: Callable[[list[str]], int],
    salida: str | Path,
    *,
    experimentos: bool = False,
    evaluar_perfil: Callable | None = None,
) -> ReporteBenchmark:
    """Evalúa cada perfil, en el orden pedido, sobre todos los bancos.

    ``main`` es ``ipsis.cli.main`` (se inyecta para no depender de la CLI).
    ``evaluar_perfil(perfil, manifiesto, banco, experimentos)`` reemplaza la
    evaluación real en las pruebas y devuelve ``(artefacto, indexado_s, acuerdo)``.
    """
    from ipsis.configuracion.perfiles import perfil_efectivo
    from ipsis.evaluacion.banco import cargar_banco
    from ipsis.evaluacion.calibracion import NUNCA, redecidir, redecidir_pares
    from ipsis.evaluacion.metricas import reporte_cobertura

    desconocidos = [p for p in perfiles if p not in PERFILES_BENCHMARK]
    if desconocidos:
        raise ValueError(t("app.unknown_profiles", profiles=desconocidos, valid=", ".join(PERFILES_BENCHMARK)))
    rutas_bancos = [Path(m).resolve() for m in manifiestos]
    bancos = [cargar_banco(m) for m in rutas_bancos]
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    evaluar = evaluar_perfil or (lambda p, m, b, e: _evaluar_en_proyecto(p, m, b, main, e))

    resultados: list[ResultadoPerfil] = []
    artefactos: list[str] = []
    pares_de: dict[str, list] = {}
    acuerdos: dict[str, float] = {}
    costo_acuerdo: dict[str, float] = {}
    for perfil in perfiles:
        pares, observaciones, indexado, tono = [], [], 0.0, None
        for manifiesto, banco in zip(rutas_bancos, bancos):
            artefacto, segundos, acuerdo = evaluar(perfil, manifiesto, banco, experimentos)
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
            if acuerdo is not None:
                acuerdos.update(acuerdo[0])
                costo_acuerdo.update(acuerdo[1])
        pares_de[perfil] = pares
        instalacion = perfil_efectivo(perfil)
        latencia = latencia_de(observaciones)
        resultados.append(ResultadoPerfil(
            nombre=perfil, perfil=perfil, presupuesto_p95_ms=instalacion.presupuesto_p95_ms, latencia=latencia,
            cumple_presupuesto=latencia.p95 <= instalacion.presupuesto_p95_ms,
            cobertura=reporte_cobertura(pares), modelos=_modelos(instalacion),
            cascada={"recuperar_n": instalacion.cascada.recuperar_n, "rerank_k": instalacion.cascada.rerank_k,
                     "leer_m": instalacion.cascada.leer_m, "concordancia": instalacion.cascada.concordancia,
                     "recuperacion": instalacion.recuperacion_modo or "hibrida"},
            tiempo_indexado_s=round(indexado, 1),
            tono=tono,
        ))

    if experimentos and "medium" in pares_de:
        base = next(r for r in resultados if r.nombre == "medium")
        umbrales = {**perfil_efectivo("medium").umbrales_por_defecto, "ok": OK_EXPERIMENTAL_MEDIUM}
        resultados.append(base.model_copy(update={
            "nombre": f"medium+ok{OK_EXPERIMENTAL_MEDIUM}",
            "variante": t("evaluation.variant_medium_ok", value=OK_EXPERIMENTAL_MEDIUM,
                          profile_value=perfil_efectivo("medium").umbrales_por_defecto["ok"]),
            "cobertura": reporte_cobertura(redecidir_pares(pares_de["medium"], umbrales)),
        }))
    if experimentos and "light" in pares_de and acuerdos:
        base = next(r for r in resultados if r.nombre == "light")
        umbrales = perfil_efectivo("light").umbrales_por_defecto
        pares = []
        for caso, obs in pares_de["light"]:
            nueva = redecidir(obs, umbrales)
            if nueva.regla == "ok_lexico" and acuerdos.get(caso.id, 1.0) < 0.5:
                nueva = redecidir(obs, {**umbrales, "ok": NUNCA})  # sin ok: relacionado o sin respuesta
            pares.append((caso, nueva))
        latencia = latencia_de([o for _c, o in pares_de["light"]], extra_ms=costo_acuerdo)
        extra = list(costo_acuerdo.values())
        resultados.append(base.model_copy(update={
            "nombre": "light+acuerdo",
            "variante": t("evaluation.variant_light_agreement"),
            "latencia": latencia, "cumple_presupuesto": latencia.p95 <= base.presupuesto_p95_ms,
            "cobertura": reporte_cobertura(pares),
            "costo_extra": {t("evaluation.extra_p50"): round(percentil(extra, 0.5), 1),
                            t("evaluation.extra_p95"): round(percentil(extra, 0.95), 1)},
        }))

    usados = [BancoUsado(dataset_id=b.manifiesto.dataset_id, dataset_version=b.manifiesto.dataset_version,
                         uso=b.manifiesto.uso, idioma=b.manifiesto.idioma, n_casos=len(b.casos)) for b in bancos]
    from ipsis.evaluacion.metricas import CRITERIO_RESPUESTA

    return ReporteBenchmark(schema_version=2, criterio_respuesta=CRITERIO_RESPUESTA,
                            bancos=usados, nota=nota_de(usados), perfiles=resultados, artefactos=artefactos)


def escribir_reporte_benchmark(reporte: ReporteBenchmark, salida: str | Path) -> tuple[Path, Path]:
    from ipsis.evaluacion.benchmark import markdown
    from ipsis.evaluacion.golden import escribir_atomico

    salida = Path(salida)
    json_ruta, md_ruta = salida / "benchmark-profiles.json", salida / "benchmark-profiles.md"
    escribir_atomico(json_ruta, reporte.model_dump_json(indent=2) + "\n")
    escribir_atomico(md_ruta, markdown(reporte))
    return json_ruta, md_ruta


def benchmark_perfiles(manifiestos: list[str], perfiles: list[str], main, salida: str | Path | None = None, *,
                       experimentos: bool = False):
    """``ipsis benchmark --profiles``: ejecuta, escribe los reportes y decide la
    salida. Devuelve ``(reporte, ruta_json, ruta_md, carpeta, codigo)``."""
    from ipsis.configuracion import rutas
    from ipsis.evaluacion.benchmark import codigo_salida

    carpeta = Path(salida or rutas.GOLDEN_REPORTES)
    reporte = ejecutar_benchmark_perfiles(manifiestos, perfiles, main, carpeta, experimentos=experimentos)
    ruta_json, ruta_md = escribir_reporte_benchmark(reporte, carpeta)
    return reporte, ruta_json, ruta_md, carpeta, codigo_salida(reporte)


__all__ = ["OK_EXPERIMENTAL_MEDIUM", "PERFILES_BENCHMARK", "benchmark_perfiles", "ejecutar_benchmark_perfiles",
           "escribir_reporte_benchmark"]
