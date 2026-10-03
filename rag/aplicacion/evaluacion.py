"""Casos de uso de evaluación: ejecutar el motor sobre un banco y comparar."""
from __future__ import annotations

import hashlib
from collections.abc import Callable
import json
import os
import tempfile
from pathlib import Path

import yaml

from rag.evaluacion.banco import cargar_banco, hash_banco
from rag.evaluacion.comparacion import cargar_artefacto, comparar_artefactos
from rag.evaluacion.metricas import (
    ArtefactoEvaluacion,
    ObservacionEvaluacion,
    calibrar_observaciones_dev,
    evaluar_observaciones,
)


def evaluar_backend_activo(
    ruta_manifiesto: str,
    *,
    k: int | None = None,
    limite_respuesta_chars: int = 500,
) -> ArtefactoEvaluacion:
    """Ejecuta recuperación y motor actuales contra un banco completo."""
    import time
    from pathlib import Path

    from rag.evaluacion.banco import cargar_banco
    from rag.configuracion.carga import cargar_dominio, cargar_proyecto
    from rag.nucleo.esquemas import QueryAnalysis
    from rag.ingesta.parsear import parsear_documento
    from rag.aplicacion.consulta import construir_motor

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

    motor = construir_motor(cfg, cfg_dominio=cargar_dominio())
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
    calibracion = calibrar_observaciones_dev(banco, observaciones)
    config_json = json.dumps(cfg, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return ArtefactoEvaluacion(
        backend=etiqueta_backend,
        dataset_id=banco.manifiesto.dataset_id,
        dataset_version=banco.manifiesto.dataset_version,
        dataset_sha256=hash_banco(banco),
        configuracion_sha256=hashlib.sha256(config_json.encode("utf-8")).hexdigest(),
        configuracion=cfg,
        indice=indice,
        calibracion_dev=calibracion,
        reporte=reporte,
        observaciones=observaciones,
    )


def ejecutar_benchmark(
    ruta_banco: str,
    directorio_salida: str,
    main: Callable[[list[str]], int],
) -> Path:
    """Evalúa los modos de recuperación sobre un proyecto temporal.

    ``main`` ejecuta un comando de la CLI (``rag.cli.main``). Se inyecta para
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
                raise RuntimeError("falló rag init durante el benchmark")
            for archivo in banco.manifiesto.corpus.archivos:
                if main(["cargar", str(corpus / archivo.ruta)]) != 0:
                    raise RuntimeError(f"falló la carga de {archivo.ruta}")

            ruta_cfg = proyecto / "configuracion" / "motor.yaml"
            cfg = yaml.safe_load(ruta_cfg.read_text(encoding="utf-8"))
            artefactos = []
            ejecuciones = [
                ("qdrant", "vectorial", True),
                ("qdrant", "hibrida", False),
            ]
            for retriever, modo, reindexar in ejecuciones:
                cfg["componentes"]["retriever"] = retriever
                cfg["recuperacion"]["modo"] = modo
                ruta_cfg.write_text(
                    yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                if reindexar and main(["indexar"]) != 0:
                    raise RuntimeError(f"falló la indexación de {retriever}/{modo}")
                etiqueta = f"qdrant_{modo}"
                ruta_artefacto = salida / f"{etiqueta}.json"
                main([
                    "evaluar", "--banco", str(manifiesto),
                    "--salida", str(ruta_artefacto),
                ])
                if not ruta_artefacto.is_file():
                    raise RuntimeError(f"no se produjo el artefacto {etiqueta}")
                artefactos.append(cargar_artefacto(ruta_artefacto))

            informe = comparar_artefactos(artefactos)
            ruta_informe = salida / "comparacion.json"
            ruta_informe.write_text(informe.model_dump_json(indent=2), encoding="utf-8")
            return ruta_informe
        finally:
            os.chdir(anterior)


def _percentil(valores: list[float], q: float) -> float:
    ordenados = sorted(valores)
    if not ordenados:
        return 0.0
    posicion = (len(ordenados) - 1) * q
    abajo = int(posicion)
    arriba = min(abajo + 1, len(ordenados) - 1)
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * (posicion - abajo)


def medir_latencia(
    ruta_banco: str,
    perfiles: list[str],
    main: Callable[[list[str]], int],
    repeticiones: int = 20,
) -> dict:
    """p50 y p95 por etapa y totales de cada perfil, con las preguntas del banco.

    Crea un proyecto temporal por perfil (heavy usa otro modelo denso e índice),
    calienta el motor y repite cada pregunta ``repeticiones`` veces.
    """
    from rag.aplicacion.consulta import construir_motor
    from rag.configuracion.carga import cargar_dominio, cargar_proyecto
    from rag.configuracion.perfiles import cargar_perfil_instalacion

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
                if main(["init", "--perfil", perfil]) != 0:
                    raise RuntimeError(f"falló rag init --perfil {perfil}")
                for archivo in banco.manifiesto.corpus.archivos:
                    main(["cargar", str(corpus / archivo.ruta)])
                if main(["indexar"]) != 0:
                    raise RuntimeError(f"falló la indexación del perfil {perfil}")
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
        p95 = _percentil(totales, 0.95)
        informe["perfiles"][perfil] = {
            "presupuesto_p95_ms": presupuesto,
            "total": {"p50": round(_percentil(totales, 0.5), 1), "p95": round(p95, 1)},
            "etapas": {e: {"p50": round(_percentil(v, 0.5), 1), "p95": round(_percentil(v, 0.95), 1)}
                       for e, v in por_etapa.items()},
            "cumple_presupuesto": p95 <= presupuesto,
        }
    return informe

