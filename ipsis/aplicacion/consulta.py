"""Casos de uso de consulta: construir el motor desde la configuración."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ipsis.modelos.catalogo import obtener as obtener_modelo
from ipsis.configuracion.glosario import ETAPAS
from ipsis.consulta.etapas.redaccion import cargar_plantillas
# El servicio usa el motor y sus errores a través de esta capa.
from ipsis.consulta.motor import Motor, MotorNoListo, MotorSaturado
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.configuracion.perfiles import perfil_efectivo
from ipsis.nucleo.registro import RegistroComponentes
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
) -> Motor:
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

    componentes = dict(cfg.get("componentes") or {})
    if not componentes:
        raise ValueError(t("app.no_components"))
    registro = registrar_componentes_base(registro or RegistroComponentes())
    for tipo, nombre in componentes.items():
        if nombre is not None:
            registro.obtener(tipo, nombre)

    cfg_dominio = cfg_dominio or cargar_dominio()
    perfil_instalacion = perfil_efectivo(cfg_dominio.get("perfil", "light"), cfg.get("ajustes_perfil"))
    for nombre_etapa in perfil_instalacion.etapas:
        try:
            registro.obtener("etapa", nombre_etapa)
        except KeyError as exc:
            raise ValueError(t("app.unknown_stage", profile=perfil_instalacion.perfil, stage=nombre_etapa,
                               error=exc)) from exc
    perfil = cargar_perfil()
    idioma = cargar_paquete(cfg_dominio.get("idioma", "es"), proyecto=Path.cwd())
    plantillas = cargar_plantillas(idioma, cfg_dominio)
    cfg_rec = config_recuperacion(cfg)
    cfg_red = config_redaccion(cfg)
    cfg_srv = config_servicio(cfg)

    retriever = registro.crear(
        "retriever",
        componentes["retriever"],
        recuperacion=cfg_rec,
        qdrant=cfg.get("qdrant", {}),
    )
    analizador = registro.crear("intent_classifier", componentes["intent_classifier"])
    # La calibración solo vale para el corpus con que se calibró: se vuelve a
    # resolver el perfil con el hash del índice recién abierto.
    hash_corpus = _hash_corpus_indexado(retriever)
    if hash_corpus is not None:
        perfil_instalacion = perfil_efectivo(cfg_dominio.get("perfil", "light"), cfg.get("ajustes_perfil"),
                                             hash_corpus=hash_corpus)
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
    if perfil_instalacion.modelos.reranker and "reranking" in perfil_instalacion.etapas:
        motor.reranker = registro.crear("reranker", "onnx", modelo=perfil_instalacion.modelos.reranker)
    if perfil_instalacion.modelos.lector and "lectura" in perfil_instalacion.etapas:
        motor.lector = registro.crear(
            "answer_reader", "onnx", modelo=perfil_instalacion.modelos.lector,
            max_tokens_pasaje=perfil_instalacion.cascada.max_tokens_pasaje,
            stride=perfil_instalacion.cascada.stride,
        )
    motor.etapas = [registro.crear("etapa", nombre, motor) for nombre in perfil_instalacion.etapas]
    motor._marca_presentacion = _marca_presentacion()  # base para recargar_presentacion
    return motor


def construir_motor_del_proyecto() -> Motor:
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
    tono: str | None = None
    plantillas: list[str] = field(default_factory=list)  # <tono>.<situación>.<n>
    # Dónde se gana o se pierde cada fragmento: su lugar en el ranking denso, en
    # BM25, en la fusión y en el reranker, y lo que leyó el lector QA.
    candidatos: list[dict[str, Any]] = field(default_factory=list)
    # Las oraciones mejor puntuadas de los candidatos, con el puntaje que usa la selección.
    oraciones: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_ms(self) -> int:
        return sum(ms for _, ms in self.etapas)


def diagnosticar_pregunta(pregunta: str, motor: Motor | None = None) -> DiagnosticoConsulta:
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
        evidencias=[{k: e.get(k) for k in ("doc_id", "chunk_id", "offset_inicio", "offset_fin", "texto")}
                    for e in d.get("evidencias") or []],
        advertencias=list(d.get("advertencias") or []),
        salto_modelos=bool(d.get("salto_modelos")),
        tono=d.get("tono"),
        plantillas=list(d.get("plantillas") or []),
        candidatos=candidatos,
        oraciones=oraciones,
    )


def _ranking_diagnostico(motor, pregunta: str, d: dict) -> tuple[list[dict], list[dict]]:
    """Ranking por etapa de cada candidato y las oraciones mejor puntuadas.

    Las búsquedas densa y BM25 por separado se hacen solo aquí (el camino normal
    usa la fusión); un retriever sin esos métodos (otro backend, un motor falso)
    deja la tabla con lo que haya."""
    retriever = getattr(motor, "retriever", None)
    rankings = {}
    if retriever is not None and hasattr(retriever, "rankings_diagnostico"):
        try:
            rankings = retriever.rankings_diagnostico(pregunta)
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
            "denso": posicion(rankings.get("denso", [])), "bm25": posicion(rankings.get("bm25", [])),
            "fusion": (c.get("signals") or {}).get("fusion_rank"),
            "rerank": rerank.get(cid, (None, None))[0], "rerank_score": rerank.get(cid, (None, None))[1],
            "qa": lectura.get("prob_respuesta"), "qa_texto": lectura.get("texto"),
        })
    oraciones: list[dict] = []
    if retriever is not None and hasattr(retriever, "textos_diagnostico") and candidatos:
        from contextlib import nullcontext

        from ipsis.consulta.etapas.seleccion import _puntuar, dividir_en_unidades
        from ipsis.lenguaje.entidades import usar_idioma

        try:
            textos = retriever.textos_diagnostico([c["chunk_id"] for c in candidatos[:3]])
        except Exception:  # noqa: BLE001
            textos = {}
        vistas = set()
        idioma = getattr(motor, "idioma", None)
        for cid, texto in textos.items():
            unidades = dividir_en_unidades(texto)
            with usar_idioma(idioma) if idioma is not None else nullcontext():  # como en la consulta
                scores = _puntuar(pregunta, unidades, getattr(retriever, "estadisticas_lexico", lambda: None)())
            for unidad, score in zip(unidades, scores, strict=True):
                if unidad.texto not in vistas:
                    vistas.add(unidad.texto)
                    oraciones.append({"chunk_id": cid, "texto": unidad.texto, "score": round(score, 3)})
        oraciones.sort(key=lambda o: -o["score"])
        oraciones = oraciones[:5]
    return candidatos, oraciones


__all__ = ["DiagnosticoConsulta", "Motor", "MotorNoListo", "MotorSaturado", "construir_motor",
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


def recargar_presentacion(motor: Motor) -> bool:
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
