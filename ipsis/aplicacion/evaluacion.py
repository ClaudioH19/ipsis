"""Casos de uso de evaluación: ejecutar el motor sobre un banco y comparar."""
from __future__ import annotations

import hashlib
from collections.abc import Callable
import json
import os
import tempfile
from pathlib import Path

import yaml

from ipsis.evaluacion.banco import cargar_banco, hash_banco
from ipsis.evaluacion.benchmark import percentil
from ipsis.evaluacion.comparacion import cargar_artefacto, comparar_artefactos
from ipsis.evaluacion.metricas import (
    ArtefactoEvaluacion,
    ObservacionEvaluacion,
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
    config_json = json.dumps(cfg, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return ArtefactoEvaluacion(
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
                raise RuntimeError("falló ipsis init durante el benchmark")
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
                if main(["init", "--perfil", perfil]) != 0:
                    raise RuntimeError(f"falló ipsis init --perfil {perfil}")
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
        p95 = percentil(totales, 0.95)
        informe["perfiles"][perfil] = {
            "presupuesto_p95_ms": presupuesto,
            "total": {"p50": round(percentil(totales, 0.5), 1), "p95": round(p95, 1)},
            "etapas": {e: {"p50": round(percentil(v, 0.5), 1), "p95": round(percentil(v, 0.95), 1)}
                       for e, v in por_etapa.items()},
            "cumple_presupuesto": p95 <= presupuesto,
        }
    return informe



# ---------------------------------------------------------------------------
# ipsis calibrar
# ---------------------------------------------------------------------------
class ErrorCalibracion(ValueError):
    """La calibración no puede correr; ``errores`` dice qué hacer."""

    def __init__(self, errores: list[str]) -> None:
        super().__init__("\n".join(errores))
        self.errores = errores


class CalibracionProyecto:
    """Resultado de ``ipsis calibrar`` para el proyecto activo."""

    def __init__(self, resultado, procedencia, ruta: Path | None) -> None:
        self.resultado = resultado  # ipsis.evaluacion.calibracion.ResultadoCalibracion
        self.procedencia = procedencia  # ProcedenciaCalibracion
        self.ruta = ruta  # configuracion/calibracion.yaml si se aplicó


def hash_corpus_del_indice(cfg: dict) -> str:
    """``hash_corpus`` del manifiesto del índice que abre el proyecto: la
    identidad oficial del corpus indexado (la misma que comprueba el motor)."""
    from ipsis.configuracion.carga import config_recuperacion
    from ipsis.indice.manifiesto import cargar_manifiesto
    from ipsis.indice.qdrant import nombre_coleccion_versionada

    cfg_rec = config_recuperacion(cfg)
    nombre = nombre_coleccion_versionada(cfg_rec["coleccion_base"], cfg_rec["modelo"], cfg_rec["version_coleccion"])
    try:
        return cargar_manifiesto(nombre).hash_corpus
    except FileNotFoundError as e:
        raise ErrorCalibracion([f"no hay un índice válido para el proyecto ({nombre}). Ejecuta 'ipsis indexar' "
                                "antes de calibrar"]) from e


def calibrar_proyecto(
    alfa: float = 0.05,
    aplicar: bool = False,
    evaluar: Callable[[str], ArtefactoEvaluacion] | None = None,
) -> CalibracionProyecto:
    """Evalúa el perfil sobre el golden importado y calibra sus umbrales.

    No entrena nada: ``calibrar`` elige umbrales escalares en ``dev`` y
    verifica en ``test`` (P10.2). Con ``aplicar`` escribe
    ``configuracion/calibracion.yaml`` en cualquier estado, para auditoría;
    el motor solo usa sus umbrales si el estado es ``calibrado`` y la
    procedencia coincide. ``evaluar`` se inyecta en las pruebas (motor falso).
    """
    from ipsis.aplicacion.golden import _cargar_banco_vigente
    from ipsis.configuracion import rutas
    from ipsis.configuracion.calibracion import ProcedenciaCalibracion
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto
    from ipsis.configuracion.perfiles import perfil_efectivo
    from ipsis.evaluacion.banco import exigir_calibrable
    from ipsis.evaluacion.calibracion import calibrar, escribir_calibracion
    from ipsis.evaluacion.golden import ErrorGolden

    if not 0.0 < alfa < 1.0:
        raise ErrorCalibracion([f"--alfa debe estar entre 0 y 1, sin incluirlos (se recibió {alfa})"])
    cfg = cargar_proyecto()
    nombre_perfil = cargar_dominio().get("perfil", "light")
    # Umbrales del perfil sin calibración previa: son la base de la búsqueda.
    perfil = perfil_efectivo(nombre_perfil, cfg.get("ajustes_perfil"))
    hash_corpus = hash_corpus_del_indice(cfg)
    try:
        banco, _textos, manifiesto = _cargar_banco_vigente()
    except ErrorGolden as e:
        errores = list(e.errores)
        if any("corpus cambió" in m for m in errores):
            errores.append("Ejecuta 'ipsis golden validar' y vuelve a importar el golden si corresponde")
        raise ErrorCalibracion(errores) from e
    try:
        exigir_calibrable(banco)
    except ValueError as e:
        raise ErrorCalibracion([str(e)]) from e

    artefacto = (evaluar or evaluar_backend_activo)(str(manifiesto))
    resultado = calibrar(banco, artefacto.observaciones, perfil.umbrales_por_defecto, alfa)
    procedencia = ProcedenciaCalibracion(
        perfil=perfil.perfil, modelos=perfil.modelos.model_dump(), hash_corpus=hash_corpus,
        banco=f"{banco.manifiesto.dataset_id}@{banco.manifiesto.dataset_version}", hash_banco=hash_banco(banco),
    )
    ruta = escribir_calibracion(resultado, procedencia, rutas.CALIBRACION) if aplicar else None
    return CalibracionProyecto(resultado, procedencia, ruta)


def comparar_reportes(rutas_artefactos: list[str], salida: str | Path):
    """Compara artefactos de ``ipsis evaluar`` y escribe el informe en ``salida``."""
    informe = comparar_artefactos([cargar_artefacto(ruta) for ruta in rutas_artefactos])
    destino = Path(salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(informe.model_dump_json(indent=2), encoding="utf-8")
    return informe, destino
