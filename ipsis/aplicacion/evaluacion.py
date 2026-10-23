"""Casos de uso de evaluación: ejecutar el motor sobre un banco y comparar."""
from __future__ import annotations

import hashlib
from collections.abc import Callable
import json
import os
import tempfile
from pathlib import Path

from ipsis.configuracion import rutas
from ipsis.configuracion.archivos import escribir, leer
from ipsis.evaluacion.banco import cargar_banco, hash_banco
from ipsis.evaluacion.benchmark import percentil
from ipsis.evaluacion.comparacion import cargar_artefacto, comparar_artefactos
from ipsis.evaluacion.metricas import (
    ArtefactoEvaluacion,
    ObservacionEvaluacion,
    evaluar_observaciones,
)
from ipsis.recursos.mensajes import t


def evaluar_backend_activo(
    ruta_manifiesto: str,
    *,
    k: int | None = None,
    limite_respuesta_chars: int = 500,
) -> ArtefactoEvaluacion:
    """Ejecuta recuperación y motor actuales contra un banco completo."""
    import time
    from pathlib import Path

    from ipsis.evaluacion.banco import cargar_banco
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto
    from ipsis.nucleo.esquemas import QueryAnalysis
    from ipsis.ingesta.parsear import parsear_documento
    from ipsis.aplicacion.consulta import construir_motor

    ruta = Path(ruta_manifiesto).resolve()
    banco = cargar_banco(ruta)
    cfg = cargar_proyecto()
    k = k or cfg["recuperacion"]["top_k"]
    directorio = (ruta.parent / banco.manifiesto.corpus.directorio).resolve()
    documentos = {}
    for archivo in banco.manifiesto.corpus.archivos:
        documento = parsear_documento(
            str(directorio / archivo.ruta),
            doc_id=archivo.doc_id,
            doc_titulo=archivo.doc_id,
            version="1",
        )
        documentos[archivo.doc_id] = documento.texto_completo

    from ipsis.evaluacion.metricas import SenalesObservadas

    cfg_dominio = cargar_dominio()
    idioma = cfg_dominio.get("idioma")
    motor = construir_motor(cfg, cfg_dominio=cfg_dominio)
    etiqueta_backend = (
        f"qdrant_{cfg['recuperacion']['modo']}"
        if motor.backend == "qdrant"
        else motor.backend
    )
    observaciones = []
    try:
        motor.calentar()
        for caso in banco.casos:
            consulta = QueryAnalysis(
                pregunta_original=caso.pregunta,
                pregunta_normalizada=" ".join(caso.pregunta.lower().split()),
            )
            candidatos = motor.retriever.recuperar(consulta, k)
            inicio = time.perf_counter()
            resultado = motor.consultar(caso.pregunta, f"evaluacion:{caso.id}")
            latencia = int((time.perf_counter() - inicio) * 1000)
            observaciones.append(ObservacionEvaluacion(
                caso_id=caso.id,
                backend=etiqueta_backend,
                estado=resultado.estado.value,
                respuesta=resultado.mensaje_usuario,
                candidatos=[candidato.chunk for candidato in candidatos],
                evidencias=resultado.evidencias,
                latencia_ms=latencia,
                etapas_ms=dict(resultado.diagnostico.get("etapas") or {}),
                confianza_top1=float(resultado.confianza.get("top1", 0.0)),
                metodo_confianza=(resultado.diagnostico.get("senales") or {}).get("metodo_confianza"),
                idioma=idioma,
                regla=resultado.diagnostico.get("regla"),
                senales=SenalesObservadas.desde_diagnostico(resultado.diagnostico),
                respuesta_exacta=((resultado.diagnostico.get("contrato_http") or {})
                                  .get("respuesta_exacta") or {}).get("texto"),
            ))
        retriever = motor.retriever
        if hasattr(retriever, "indice"):
            indice = retriever.indice.manifiesto.model_dump(mode="json")
        else:
            indice = {
                "coleccion": getattr(getattr(retriever, "coleccion", None), "nombre", None),
                "modelo": cfg["recuperacion"].get("modelo"),
                "modo": cfg["recuperacion"].get("modo"),
                "version_coleccion": cfg["recuperacion"].get("version_coleccion"),
            }
    finally:
        motor.cerrar()
    reporte = evaluar_observaciones(
        banco,
        observaciones,
        documentos,
        k=k,
        limite_respuesta_chars=limite_respuesta_chars,
    )
    from ipsis.modelos.catalogo import obtener

    cfg = {**cfg, "perfil_resuelto": motor.perfil_instalacion.model_dump(mode="json"),
           "contratos_modelos": {rol: obtener(id_hf).model_dump(mode="json")
                                 for rol, id_hf in motor.perfil_instalacion.modelos.model_dump().items() if id_hf}}
    config_json = json.dumps(cfg, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return ArtefactoEvaluacion(
        schema_version=2,
        backend=etiqueta_backend,
        dataset_id=banco.manifiesto.dataset_id,
        dataset_version=banco.manifiesto.dataset_version,
        dataset_sha256=hash_banco(banco),
        configuracion_sha256=hashlib.sha256(config_json.encode("utf-8")).hexdigest(),
        configuracion=cfg,
        indice=indice,
        reporte=reporte,
        observaciones=observaciones,
        tono=(motor.plantillas or {}).get("tono"),
    )


def ejecutar_benchmark(
    ruta_banco: str,
    directorio_salida: str,
    main: Callable[[list[str]], int],
) -> Path:
    """Evalúa los modos de recuperación sobre un proyecto temporal.

    ``main`` ejecuta un comando de la CLI (``ipsis.cli.main``). Se inyecta para
    que esta capa no dependa de la CLI.
    """
    manifiesto = Path(ruta_banco).resolve()
    banco = cargar_banco(manifiesto)
    corpus = (manifiesto.parent / banco.manifiesto.corpus.directorio).resolve()
    salida = Path(directorio_salida).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    anterior = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="rag_benchmark_") as temporal:
        proyecto = Path(temporal)
        try:
            os.chdir(proyecto)
            if main(["init"]) != 0:
                raise RuntimeError(t("app.init_failed_benchmark"))
            for archivo in banco.manifiesto.corpus.archivos:
                if main(["load", str(corpus / archivo.ruta)]) != 0:
                    raise RuntimeError(t("app.load_failed", file=archivo.ruta))

            ruta_cfg = proyecto / rutas.MOTOR
            cfg = leer(ruta_cfg, "motor")
            artefactos = []
            ejecuciones = [
                ("qdrant", "vectorial", True),
                ("qdrant", "hibrida", False),
            ]
            for retriever, modo, reindexar in ejecuciones:
                cfg["componentes"]["retriever"] = retriever
                cfg["recuperacion"]["modo"] = modo
                escribir(ruta_cfg, cfg, "motor")
                if reindexar and main(["index"]) != 0:
                    raise RuntimeError(t("app.index_failed", what=f"{retriever}/{modo}"))
                etiqueta = f"qdrant_{modo}"
                ruta_artefacto = salida / f"{etiqueta}.json"
                main([
                    "evaluate", "--bank", str(manifiesto),
                    "--output", str(ruta_artefacto),
                ])
                if not ruta_artefacto.is_file():
                    raise RuntimeError(t("app.report_missing", name=etiqueta))
                artefactos.append(cargar_artefacto(ruta_artefacto))

            informe = comparar_artefactos(artefactos)
            ruta_informe = salida / "comparison.json"
            ruta_informe.write_text(informe.model_dump_json(indent=2), encoding="utf-8")
            return ruta_informe
        finally:
            os.chdir(anterior)


def medir_latencia(
    ruta_banco: str,
    perfiles: list[str],
    main: Callable[[list[str]], int],
    repeticiones: int = 20,
) -> dict:
    """p50 y p95 por etapa y totales de cada perfil, con las preguntas del banco.

    Crea un proyecto temporal por perfil (con su propio índice),
    calienta el motor y repite cada pregunta ``repeticiones`` veces.
    """
    from ipsis.aplicacion.consulta import construir_motor
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto
    from ipsis.configuracion.perfiles import cargar_perfil_instalacion

    manifiesto = Path(ruta_banco).resolve()
    banco = cargar_banco(manifiesto)
    corpus = (manifiesto.parent / banco.manifiesto.corpus.directorio).resolve()
    preguntas = [caso.pregunta for caso in banco.casos]
    informe: dict = {"banco": banco.manifiesto.dataset_id, "repeticiones": repeticiones, "perfiles": {}}
    anterior = Path.cwd()
    for perfil in perfiles:
        with tempfile.TemporaryDirectory(prefix=f"rag_latencia_{perfil}_") as temporal:
            try:
                os.chdir(temporal)
                if main(["init", "--profile", perfil]) != 0:
                    raise RuntimeError(t("app.init_failed_profile", profile=perfil))
                for archivo in banco.manifiesto.corpus.archivos:
                    main(["load", str(corpus / archivo.ruta)])
                if main(["index"]) != 0:
                    raise RuntimeError(t("app.index_failed", what=perfil))
                motor = construir_motor(cargar_proyecto(), cfg_dominio=cargar_dominio())
                motor.calentar()
                totales: list[float] = []
                por_etapa: dict[str, list[float]] = {}
                for _ in range(repeticiones):
                    for pregunta in preguntas:
                        resultado = motor.consultar(pregunta, "latencia")
                        totales.append(resultado.diagnostico["contrato_http"]["latencia_ms"])
                        for etapa, ms in resultado.diagnostico.get("etapas", {}).items():
                            por_etapa.setdefault(etapa.removesuffix("_ms"), []).append(ms)
                motor.cerrar()
            finally:
                os.chdir(anterior)
        presupuesto = cargar_perfil_instalacion(perfil).presupuesto_p95_ms
        p95 = percentil(totales, 0.95)
        informe["perfiles"][perfil] = {
            "presupuesto_p95_ms": presupuesto,
            "total": {"p50": round(percentil(totales, 0.5), 1), "p95": round(p95, 1)},
            "etapas": {e: {"p50": round(percentil(v, 0.5), 1), "p95": round(percentil(v, 0.95), 1)}
                       for e, v in por_etapa.items()},
            "cumple_presupuesto": p95 <= presupuesto,
        }
    return informe



def comparar_reportes(rutas_artefactos: list[str], salida: str | Path):
    """Compara artefactos de ``ipsis evaluate`` y escribe el informe en ``salida``."""
    informe = comparar_artefactos([cargar_artefacto(ruta) for ruta in rutas_artefactos])
    destino = Path(salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(informe.model_dump_json(indent=2), encoding="utf-8")
    return informe, destino
