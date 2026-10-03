"""Casos de uso de consulta: construir el motor desde la configuración."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rag.modelos.catalogo import obtener as obtener_modelo
from rag.consulta.etapas.redaccion import cargar_plantillas
from rag.consulta.motor import Motor
from rag.lenguaje.paquete import cargar_paquete
from rag.configuracion.perfiles import perfil_efectivo
from rag.nucleo.registro import RegistroComponentes


def _hash_corpus_indexado(retriever) -> str | None:
    """``hash_corpus`` del manifiesto del índice abierto (``None`` si no hay)."""
    nombre = getattr(getattr(retriever, "coleccion", None), "nombre", None)
    if not nombre:
        return None
    from rag.indice.manifiesto import cargar_manifiesto

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
    from rag.configuracion.carga import (
        cargar_dominio,
        config_recuperacion,
        config_redaccion,
        config_servicio,
    )
    from rag.lenguaje.dominio import cargar_perfil
    from rag.aplicacion.registro_base import registrar_componentes_base
    from rag.consulta.admision import ConfiguracionAdmision, ControlAdmision

    componentes = dict(cfg.get("componentes") or {})
    if not componentes:
        raise ValueError("la configuración no define componentes")
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
            raise ValueError(
                f"el perfil {perfil_instalacion.perfil!r} declara la etapa desconocida {nombre_etapa!r}. "
                f"Revisa ajustes_perfil.etapas en configuracion/motor.yaml. {exc}"
            ) from exc
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
    return motor
