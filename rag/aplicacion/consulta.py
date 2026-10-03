"""Casos de uso de consulta: construir el motor desde la configuración."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rag.configuracion import rutas
from rag.consulta.etapas.redaccion import cargar_plantillas
from rag.consulta.motor import Motor
from rag.lenguaje.paquete import cargar_paquete
from rag.nucleo.registro import RegistroComponentes


def construir_motor(
    cfg: dict[str, Any],
    *,
    cfg_dominio: dict[str, Any] | None = None,
    registro: RegistroComponentes | None = None,
    ruta_plantillas: str | Path | None = None,
) -> Motor:
    """Construye el motor completo desde la selección declarativa.

    Primero valida todos los nombres configurados y solo después crea
    los componentes que participan en consulta. Así un nombre inválido
    falla durante el arranque, incluso si corresponde a otra fase como
    ingesta.
    """
    from rag.configuracion.carga import (
        cargar_dominio,
        config_abstencion,
        config_recuperacion,
        config_redaccion,
        config_servicio,
    )
    from rag.lenguaje.dominio import cargar_perfil
    from rag.aplicacion.registro_base import registrar_componentes_base
    from rag.consulta.admision import ConfiguracionAdmision, ControlAdmision
    from rag.lenguaje.texto import cargar_palabras_generales

    componentes = dict(cfg.get("componentes") or {})
    if not componentes:
        raise ValueError("la configuración no define componentes")
    registro = registrar_componentes_base(registro or RegistroComponentes())
    for tipo, nombre in componentes.items():
        if nombre is not None:
            registro.obtener(tipo, nombre)

    cfg_dominio = cfg_dominio or cargar_dominio()
    perfil = cargar_perfil()
    idioma = cargar_paquete(cfg_dominio.get("idioma", "es"), proyecto=Path.cwd())
    ruta_textos = Path(ruta_plantillas or rutas.TEXTOS).resolve()
    plantillas = cargar_plantillas(ruta_textos, cfg_dominio)
    palabras_generales = cargar_palabras_generales(cfg_dominio.get("idioma", "es"))
    cfg_rec = config_recuperacion(cfg)
    cfg_abs = config_abstencion(cfg, retriever=componentes["retriever"])
    cfg_red = config_redaccion(cfg)
    cfg_srv = config_servicio(cfg)

    retriever = registro.crear(
        "retriever",
        componentes["retriever"],
        recuperacion=cfg_rec,
        qdrant=cfg.get("qdrant", {}),
    )
    analizador = registro.crear("intent_classifier", componentes["intent_classifier"])
    politica = None
    if cfg_abs is not None:
        politica = registro.crear(
            "abstention_policy",
            componentes["abstention_policy"],
            configuracion=cfg_abs,
            inventario_entidades=retriever.inventario_entidades(),
            estadisticas_lexico=retriever.estadisticas_lexico(),
            palabras_generales=palabras_generales,
        )
    extractor = registro.crear(
        "answer_extractor",
        componentes["answer_extractor"],
        limite_caracteres=cfg_red["longitud_maxima_fragmento_chars"],
        metodo=cfg_red["metodo_seleccion"],
        modelo_st=getattr(retriever, "codificador", None),
        prefijo_query=cfg_rec.get("prefijo_query", ""),
    )
    verificador = registro.crear(
        "evidence_verifier", componentes["evidence_verifier"]
    )
    renderer = registro.crear("response_renderer", componentes["response_renderer"])
    return Motor(
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
        max_fragmentos_adicionales=(
            cfg_abs.get("capa_b_premisa", {}).get("max_fragmentos_adicionales", 2)
            if cfg_abs is not None
            else 2
        ),
        abstencion_calibrada=(
            cfg_abs is not None
            and "sin_calibrar" not in str(cfg_abs.get("version", ""))
        ),
    )
