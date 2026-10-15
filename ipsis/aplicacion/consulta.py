"""Casos de uso de consulta: construir el motor desde la configuración."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ipsis.modelos.catalogo import obtener as obtener_modelo
from ipsis.configuracion.glosario import ETAPAS
from ipsis.consulta.etapas.redaccion import cargar_plantillas
# El servicio usa el motor y sus errores a través de esta capa.
from ipsis.consulta.motor import Motor, MotorNoListo, MotorSaturado
from ipsis.consulta.errores import ContinuacionInvalida
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.configuracion.perfiles import perfil_efectivo
from ipsis.nucleo.registro import RegistroComponentes
from ipsis.nucleo.contratos import QueryEngine
from ipsis.recursos.mensajes import t


def _hash_corpus_indexado(retriever) -> str | None:
    """``hash_corpus`` del manifiesto del índice abierto (``None`` si no hay)."""
    nombre = getattr(getattr(retriever, "coleccion", None), "nombre", None)
    if not nombre:
        return None
    from ipsis.indice.manifiesto import cargar_manifiesto

    try:
        return cargar_manifiesto(nombre).hash_corpus
    except (FileNotFoundError, ValueError):
        return None


def construir_motor(
    cfg: dict[str, Any],
    *,
    cfg_dominio: dict[str, Any] | None = None,
    registro: RegistroComponentes | None = None,
) -> QueryEngine:
    """Construye el motor completo desde la selección declarativa.

    Primero valida todos los nombres configurados y solo después crea
    los componentes que participan en consulta. Así un nombre inválido
    falla durante el arranque, incluso si corresponde a otra fase como
    ingesta.
    """
    from ipsis.configuracion.carga import (
        cargar_dominio,
        config_recuperacion,
        config_redaccion,
        config_servicio,
    )
    from ipsis.lenguaje.dominio import cargar_perfil
    from ipsis.aplicacion.registro_base import registrar_componentes_base
    from ipsis.consulta.admision import ConfiguracionAdmision, ControlAdmision
    from ipsis.nucleo.progreso import informar

    informar("configuracion")
    pipeline = cfg.get("pipeline", "v2")
    if pipeline not in {"v1", "v2"}:
        raise ValueError("pipeline debe ser v1 o v2")
    opciones_v2 = None
    if pipeline == "v2":
        from ipsis.configuracion.esquemas import PipelineV2Config

        opciones_v2 = PipelineV2Config.model_validate(cfg.get("v2") or {}).model_dump()
    componentes = dict(cfg.get("componentes") or {})
    if not componentes:
        raise ValueError(t("app.no_components"))
    registro = registrar_componentes_base(registro or RegistroComponentes())
    for tipo, nombre in componentes.items():
        if nombre is not None:
            registro.obtener(tipo, nombre)

    cfg_dominio = cfg_dominio or cargar_dominio()
    ajustes_perfil, candidatos_idioma = cfg.get("ajustes_perfil"), None
    if pipeline == "v2":
        from ipsis.configuracion.perfiles import ajustes_de_idioma

        ajustes_perfil, candidatos_idioma = ajustes_de_idioma(
            cfg_dominio.get("perfil", "light"), ajustes_perfil, cfg_dominio.get("idioma"))
        # 60 es el valor por defecto de v2: significa «el del perfil para este idioma».
        if candidatos_idioma and opciones_v2["rerank_candidatos"] == 60:
            opciones_v2["rerank_candidatos"] = min(candidatos_idioma, opciones_v2["recuperar_n"])
    perfil_instalacion = perfil_efectivo(cfg_dominio.get("perfil", "light"), ajustes_perfil,
        **({"ruta_calibracion": None} if pipeline == "v2" else {}))
    for nombre_etapa in (perfil_instalacion.etapas if pipeline == "v1" else []):
        try:
            registro.obtener("etapa", nombre_etapa)
        except KeyError as exc:
            raise ValueError(t("app.unknown_stage", profile=perfil_instalacion.perfil, stage=nombre_etapa,
                               error=exc)) from exc
    perfil = cargar_perfil()
    idioma = cargar_paquete(cfg_dominio.get("idioma", "es"), proyecto=Path.cwd())
    from ipsis.lenguaje.sinonimos import huella_lexica, indice_automatico

    hash_lexico = huella_lexica(idioma)
    if not idioma.respaldo:
        informar("lexico")
        from ipsis.lenguaje.ortografia import raices_lexico

        if pipeline == "v1":
            indice_automatico(idioma.codigo.split("-")[0], idioma.stemmer)
        raices_lexico(idioma.codigo.split("-")[0], idioma.stemmer)  # la primera errata no espera al léxico
    plantillas = cargar_plantillas(idioma, cfg_dominio)
    cfg_rec = config_recuperacion(cfg)
    cfg_red = config_redaccion(cfg)
    cfg_srv = config_servicio(cfg)

    informar("apertura_indice")
    retriever = registro.crear(
        "retriever",
        componentes["retriever"],
        recuperacion=cfg_rec,
        qdrant=cfg.get("qdrant", {}),
    )
    if pipeline == "v2":
        from ipsis.consulta.v2 import MotorV2
        from ipsis.indice.contextos import envolver_contextos

        retriever = envolver_contextos(retriever)
        if not hasattr(retriever, "ampliar_resultado") and getattr(getattr(retriever, "coleccion", None), "nombre", None):
            from ipsis.indice.contextos import RecuperadorConContextos
            from ipsis.ingesta.ingesta import parsear_corpus
            from ipsis.configuracion import rutas

            documentos = parsear_corpus(rutas.DOCUMENTOS, preparacion="legacy")
            retriever = RecuperadorConContextos(retriever, {}, {d.doc_id: d for d in documentos})
        hash_corpus = _hash_corpus_indexado(retriever)
        motor = MotorV2(
            retriever=retriever,
            verificador=registro.crear("evidence_verifier", componentes["evidence_verifier"]),
            idioma=idioma, perfil=perfil_instalacion, plantillas=plantillas,
            control_admision=ControlAdmision(ConfiguracionAdmision(
                concurrencia_maxima=cfg_srv["concurrencia_maxima"])),
            opciones=opciones_v2,
        )
        motor.backend = componentes["retriever"]
    else:
        analizador = registro.crear("intent_classifier", componentes["intent_classifier"])
        # La calibración solo vale para el corpus con que se calibró: se vuelve a
        # resolver el perfil con el hash del índice recién abierto.
        hash_corpus = _hash_corpus_indexado(retriever)
        if hash_corpus is not None:
            perfil_instalacion = perfil_efectivo(cfg_dominio.get("perfil", "light"), cfg.get("ajustes_perfil"),
                                                 hash_corpus=hash_corpus, hash_lexico=hash_lexico)
        politica = registro.crear(
            "abstention_policy",
            componentes["abstention_policy"],
            umbrales=perfil_instalacion.umbrales_por_defecto,
            paquete=idioma,
            piso_coseno=obtener_modelo(perfil_instalacion.modelos.denso).coseno_piso,
        )
        extractor = registro.crear(
            "answer_extractor",
            componentes["answer_extractor"],
            limite_caracteres=cfg_red["longitud_maxima_fragmento_chars"],
            estadisticas=retriever.estadisticas_lexico(),
        )
        verificador = registro.crear(
            "evidence_verifier", componentes["evidence_verifier"]
        )
        renderer = registro.crear("response_renderer", componentes["response_renderer"])
        motor = Motor(
            retriever=retriever,
            analizador=analizador,
            politica_abstencion=politica,
            extractor=extractor,
            verificador=verificador,
            renderer=renderer,
            control_admision=ControlAdmision(
                ConfiguracionAdmision(concurrencia_maxima=cfg_srv["concurrencia_maxima"])
            ),
            backend=componentes["retriever"],
            perfil=perfil,
            idioma=idioma,
            plantillas=plantillas,
            configuracion_redaccion=cfg_red,
            top_k=cfg_rec["top_k"],
            max_fragmentos_adicionales=(cfg.get("abstencion") or {}).get("max_fragmentos_adicionales", 2),
            abstencion_calibrada=perfil_instalacion.origen_umbrales == "calibracion",
        )
        motor.perfil_instalacion = perfil_instalacion
        from ipsis.consulta.alternativas import ConfigAlternativas
        from ipsis.ingesta.metadata import cargar_taxonomia

        postura = cfg_dominio.get("postura") or {}
        motor.alternativas = ConfigAlternativas(
            modo=postura.get("modo", "proactiva"), max_alternativas=int(postura.get("max_alternativas", 3)),
            umbral=perfil_instalacion.alternativas.umbral, pesos=dict(perfil_instalacion.alternativas.pesos))
        motor.taxonomia = cargar_taxonomia()
        from ipsis.consulta.seguimiento import MemoriaConversacion

        cfg_conv = cfg.get("conversacion") or {}
        motor.seguimiento = MemoriaConversacion(
            max_sesiones=int(cfg_conv.get("max_sesiones", 1024)),
            vencimiento_s=float(cfg_conv.get("vencimiento_minutos", 30)) * 60,
        )
    if perfil_instalacion.modelos.reranker and (pipeline == "v2" or "reranking" in perfil_instalacion.etapas):
        motor.reranker = registro.crear("reranker", "onnx", modelo=perfil_instalacion.modelos.reranker)
        if pipeline == "v2":
            motor.reranker.lote = motor.opciones["lote_reranker"]
            spec = motor.reranker.spec
            motor.reranker.spec = spec.model_copy(update={"max_tokens": min(
                spec.max_tokens, motor.opciones["max_tokens_reranker"])})
    if perfil_instalacion.modelos.lector and (
            motor.opciones["destacar_fragmentos"] if pipeline == "v2" else "lectura" in perfil_instalacion.etapas):
        motor.lector = registro.crear(
            "answer_reader", "onnx", modelo=perfil_instalacion.modelos.lector,
            max_tokens_pasaje=(motor.opciones["max_tokens_pasaje"] if pipeline == "v2"
                               else perfil_instalacion.cascada.max_tokens_pasaje),
            stride=(motor.opciones["stride"] if pipeline == "v2" else perfil_instalacion.cascada.stride),
        )
    if pipeline == "v1":
        motor.etapas = [registro.crear("etapa", nombre, motor) for nombre in perfil_instalacion.etapas]
    from ipsis import __version__

    motor.metadatos_auditoria = {
        "version_ipsis": __version__, "backend": motor.backend, "pipeline": pipeline,
        "componentes": componentes, "perfil_efectivo": perfil_instalacion.model_dump(mode="json"),
        "modelos": {rol: {"id": nombre, "revision": obtener_modelo(nombre).revision,
                           "archivo_onnx": obtener_modelo(nombre).archivo_onnx()}
                    for rol, nombre in perfil_instalacion.modelos.model_dump().items() if nombre},
        "hash_corpus": hash_corpus, "hash_lexico": hash_lexico,
        "etapas_efectivas": (list(motor.etapas_efectivas) if pipeline == "v2"
                            else [e.nombre for e in motor.etapas]),
        "calibracion_aplicada": motor.abstencion_calibrada,
        "hash_configuracion": hashlib.sha256(json.dumps(
            {"motor": cfg, "asistente": cfg_dominio}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
    }
    if pipeline == "v2":
        # Las opciones heredadas describen v1; no son componentes ejecutados por v2.
        motor.metadatos_auditoria["componentes_configurados"] = componentes
        motor.metadatos_auditoria["componentes"] = {
            "retriever": componentes["retriever"], "fusion": componentes["fusion"],
            "reranker": "onnx" if motor.reranker is not None else None,
            "answer_reader": "onnx" if motor.lector is not None else None,
            "evidence_verifier": componentes["evidence_verifier"],
            "response_renderer": "fuentes_ordenadas_v2",
            "abstention_policy": "recuperacion_sin_certificacion_de_respuesta_v2",
        }
        motor.metadatos_auditoria["preparacion_indice"] = getattr(retriever, "preparacion_indice", None)
        motor.metadatos_auditoria["presupuestos_v2"] = dict(motor.opciones)
        if motor.lector is None:
            motor.metadatos_auditoria["modelos"].pop("lector", None)
        if motor.reranker is not None:
            motor.metadatos_auditoria["modelos"]["reranker"].update(
                lote=motor.reranker.lote, max_tokens=motor.reranker.spec.max_tokens)
    motor._marca_presentacion = _marca_presentacion()  # base para recargar_presentacion
    return motor


def construir_motor_del_proyecto() -> QueryEngine:
    """Motor del proyecto del directorio actual (lo que sirve ``ipsis serve``)."""
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto

    return construir_motor(cargar_proyecto(), cfg_dominio=cargar_dominio())


@dataclass(frozen=True)
class DiagnosticoConsulta:
    """Por qué una consulta terminó como terminó, leído del diagnóstico del motor."""

    pregunta: str
    estado: str  # el del contrato HTTP: ok, relacionado, sin_respuesta, conversacional
    respuesta: str
    regla: str | None
    motivo: str
    perfil: str | None
    etapas: list[tuple[str, int]]  # en orden de ejecución, en ms (motor ya calentado)
    senales: dict[str, Any]  # las que vio la política (s_ret, s_oov, s_foco, s_cov, s_rr, s_qa, dominio)
    foco_encontrados: list[str]
    foco_ausentes: list[str]
    ausentes_del_corpus: list[str]
    oracion_foco: str | None
    tramo: dict[str, Any] | None  # respuesta_exacta: texto y offsets, si el lector marcó uno
    evidencias: list[dict[str, Any]]
    advertencias: list[str]
    salto_modelos: bool = False
    nivel_confianza: str | None = None  # alta / media / baja (Motor.nivel_confianza)
    tono: str | None = None
    plantillas: list[str] = field(default_factory=list)  # <tono>.<situación>.<n>
    # Dónde se gana o se pierde cada fragmento: su lugar en el ranking denso, en
    # BM25, en la fusión y en el reranker, y lo que leyó el lector QA.
    candidatos: list[dict[str, Any]] = field(default_factory=list)
    # Las oraciones mejor puntuadas de los candidatos, con el puntaje que usa la selección.
    oraciones: list[dict[str, Any]] = field(default_factory=list)
    # Comprensión de la pregunta: intención y relación, sinónimos, pregunta interpretada
    # (si heredó tema) y qué hizo el turno con la conversación (ADR 0005 y 0006).
    intencion: dict[str, Any] | None = None
    ortografia: dict[str, str] = field(default_factory=dict)
    sinonimos: dict[str, list[str]] = field(default_factory=dict)
    pregunta_interpretada: str | None = None
    conversacion: dict[str, str] | None = None
    recursos_lexicos: list[dict[str, Any]] = field(default_factory=list)
    # Postura proactiva (ADR 0008): alternativas ofrecidas y descartadas, con sus señales.
    alternativas: dict[str, Any] | None = None

    @property
    def total_ms(self) -> int:
        return sum(ms for _, ms in self.etapas)


def diagnosticar_pregunta(pregunta: str, motor: QueryEngine | None = None) -> DiagnosticoConsulta:
    """Ejecuta ``pregunta`` con el motor del proyecto, en este proceso, y devuelve
    su diagnóstico. No pasa por el servicio HTTP, que no publica el diagnóstico.
    ``motor`` se inyecta en las pruebas (motor falso)."""
    propio = motor is None
    motor = construir_motor_del_proyecto() if propio else motor
    try:
        if propio:
            motor.calentar()  # que las latencias sean las de operación, sin la carga de modelos
        resultado = motor.consultar(pregunta, "rag-diagnostico")
        d = resultado.diagnostico or {}
        candidatos, oraciones = _ranking_diagnostico(motor, pregunta, d)
    finally:
        if propio:
            motor.cerrar()
    contrato = d.get("contrato_http") or {}
    lexicas = d.get("senales_lexicas") or {}
    return DiagnosticoConsulta(
        pregunta=pregunta,
        estado=contrato.get("estado", resultado.estado.value),
        respuesta=contrato.get("respuesta", resultado.mensaje_usuario),
        regla=d.get("regla"),
        motivo=resultado.motivo,
        perfil=d.get("perfil"),
        etapas=[(ETAPAS.get(nombre.removesuffix("_ms"), nombre.removesuffix("_ms")), ms)
                for nombre, ms in (d.get("etapas") or {}).items()],
        senales=dict(d.get("senales_politica") or {}),
        foco_encontrados=list(lexicas.get("foco_encontrados") or []),
        foco_ausentes=list(lexicas.get("foco_ausentes") or []),
        ausentes_del_corpus=list(lexicas.get("ausentes_del_corpus") or []),
        oracion_foco=d.get("oracion_foco"),
        tramo=contrato.get("respuesta_exacta"),
        nivel_confianza=contrato.get("nivel_confianza"),
        evidencias=[{k: e.get(k) for k in ("doc_id", "chunk_id", "offset_inicio", "offset_fin", "texto")}
                    for e in d.get("evidencias") or []],
        advertencias=list(d.get("advertencias") or []),
        salto_modelos=bool(d.get("salto_modelos")),
        tono=d.get("tono"),
        plantillas=list(d.get("plantillas") or []),
        candidatos=candidatos,
        oraciones=oraciones,
        intencion=d.get("intencion"),
        ortografia=dict(d.get("ortografia") or {}),
        sinonimos=dict(d.get("sinonimos") or {}),
        pregunta_interpretada=d.get("pregunta_interpretada"),
        conversacion=d.get("conversacion"),
        recursos_lexicos=list(d.get("recursos_lexicos") or []),
        alternativas=d.get("alternativas"),
    )


def _ranking_diagnostico(motor, pregunta: str, d: dict) -> tuple[list[dict], list[dict]]:
    """Ranking por etapa de cada candidato y las oraciones mejor puntuadas.

    Las búsquedas densa y BM25 por separado se hacen solo aquí (el camino normal
    usa la fusión); un retriever sin esos métodos (otro backend, un motor falso)
    deja la tabla con lo que haya."""
    retriever = getattr(motor, "retriever", None)
    rankings = {}
    efectiva = d.get("pregunta_interpretada") or pregunta
    manuales = d.get("sinonimos") or {}
    if manuales:
        efectiva = f"{efectiva.rstrip()} {' '.join(f for fs in manuales.values() for f in fs)}"
    if d.get("pipeline", "v1") == "v1" and retriever is not None and hasattr(retriever, "rankings_diagnostico"):
        try:
            automatica = d.get("pregunta_recuperacion")
            rankings = (retriever.rankings_diagnostico(efectiva, pregunta_bm25=automatica) if automatica
                        else retriever.rankings_diagnostico(efectiva))
        except Exception:  # noqa: BLE001 -- el diagnóstico nunca rompe la consulta
            rankings = {}
    rerank = {r["chunk_id"]: (i, r["score"]) for i, r in enumerate(d.get("rerank") or [], start=1)}
    lecturas = {lec["chunk_id"]: lec for lec in d.get("lecturas") or []}
    candidatos = []
    for c in d.get("candidatos") or []:
        cid = c["chunk_id"]
        posicion = lambda lista: lista.index(cid) + 1 if cid in lista else None  # noqa: E731
        lectura = lecturas.get(cid) or {}
        candidatos.append({
            "chunk_id": cid, "inicio": c.get("inicio", ""),
            "denso": posicion(rankings.get("denso", [])) if rankings else (c.get("signals") or {}).get("dense_rank"),
            "bm25": posicion(rankings.get("bm25", [])) if rankings else (c.get("signals") or {}).get("sparse_rank"),
            "fusion": (c.get("signals") or {}).get("fusion_rank"),
            "rerank": rerank.get(cid, (None, None))[0], "rerank_score": rerank.get(cid, (None, None))[1],
            "qa": lectura.get("prob_respuesta"), "qa_texto": lectura.get("texto"),
        })
    oraciones: list[dict] = []
    if d.get("pipeline", "v1") == "v1" and retriever is not None and hasattr(retriever, "textos_diagnostico") and candidatos:
        from contextlib import nullcontext

        from ipsis.consulta.etapas.seleccion import _puntuar_turno, dividir_en_unidades
        from ipsis.lenguaje.entidades import usar_idioma
        from ipsis.lenguaje.consultas import comprender_consulta
        from ipsis.nucleo.esquemas import QueryAnalysis

        try:
            textos = retriever.textos_diagnostico([c["chunk_id"] for c in candidatos[:3]])
        except Exception:  # noqa: BLE001
            textos = {}
        vistas = set()
        idioma = getattr(motor, "idioma", None)
        consulta = QueryAnalysis(pregunta_original=efectiva, pregunta_normalizada=efectiva,
                                intencion=(d.get("intencion") or {}).get("nombre", "desconocida"))
        comprension = comprender_consulta(consulta, idioma)
        for cid, texto in textos.items():
            unidades = dividir_en_unidades(texto)
            with usar_idioma(idioma) if idioma is not None else nullcontext():  # como en la consulta
                scores = _puntuar_turno(efectiva, unidades,
                    getattr(retriever, "estadisticas_lexico", lambda: None)(),
                    pregunta if d.get("pregunta_interpretada") else None, comprension)
            for unidad, score in zip(unidades, scores, strict=True):
                if unidad.texto not in vistas:
                    vistas.add(unidad.texto)
                    oraciones.append({"chunk_id": cid, "texto": unidad.texto, "score": round(score, 3)})
        oraciones.sort(key=lambda o: -o["score"])
        oraciones = oraciones[:5]
    return candidatos, oraciones


__all__ = ["DiagnosticoConsulta", "Motor", "MotorNoListo", "MotorSaturado", "ContinuacionInvalida", "construir_motor",
           "construir_motor_del_proyecto", "diagnosticar_pregunta", "recargar_presentacion"]


def _marca_presentacion() -> tuple:
    """mtime de los archivos que cambian el texto que redacta el motor."""
    from ipsis.configuracion import rutas

    marcas = []
    for ruta in (rutas.PERSONALIDAD, rutas.IDIOMA, rutas.ASISTENTE):
        try:
            marcas.append(Path(ruta).stat().st_mtime_ns)
        except OSError:
            marcas.append(None)
    return tuple(marcas)


def recargar_presentacion(motor: QueryEngine) -> bool:
    """Si cambió el tono o los textos del proyecto, el motor toma las plantillas
    nuevas sin reiniciar (un ``stat`` por llamada). Las consultas en curso
    terminan con las anteriores: el cambio es una asignación atómica."""
    from ipsis.configuracion.carga import cargar_dominio
    from ipsis.consulta.variantes import SelectorVariantes

    marca = _marca_presentacion()
    anterior = getattr(motor, "_marca_presentacion", None)
    if anterior is None:
        motor._marca_presentacion = marca
        return False
    if marca == anterior or motor.idioma is None:
        return False
    plantillas = cargar_plantillas(motor.idioma, cargar_dominio())
    motor.selector_variantes = SelectorVariantes(tono=plantillas.get("tono") or "cordial",
                                                 fija=plantillas.get("variedad") == "fija")
    motor.plantillas = plantillas
    motor._marca_presentacion = marca
    return True
