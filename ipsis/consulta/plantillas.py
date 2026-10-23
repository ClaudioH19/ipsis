"""Textos fijos del asistente: tono, conectores, abstención y respuestas conversacionales.

Nunca genera texto: carga los textos declarados por el idioma, el tono y el proyecto.
"""
from __future__ import annotations

from copy import deepcopy


def cargar_plantillas(paquete, dominio: dict | None = None, tono=None) -> dict:
    """Textos fijos del asistente: los del tono más los estructurales del idioma.

    Devuelve conectores, mensajes de abstención y textos conversacionales.
    ``tono`` es un ``PaqueteTono``; si falta, el tono por defecto con las
    sobrescrituras del proyecto del directorio actual. Con ``dominio``
    (``config/assistant.yaml``) sustituye ``{assistant_name}`` y
    ``{domain_description}`` en las respuestas conversacionales y aplica las
    contracciones del idioma («de el manual» -> «del manual»).
    """
    from pathlib import Path

    from ipsis.configuracion.personalidad import cargar_personalidad
    from ipsis.lenguaje.tonos import cargar_tono

    personalidad = cargar_personalidad(Path.cwd())
    if tono is None:
        tono = cargar_tono(paquete.codigo, personalidad.tono.activo, proyecto=Path.cwd(),
                           sobrescrituras=paquete.plantillas_legado)
    conectores = deepcopy(paquete.mensajes.conectores)  # secuencia y contraste_version
    for categoria in ("opening", "addition", "condition", "exception"):
        conectores[categoria] = tono.variantes(categoria)
    datos = {
        "tono": tono.tono,
        "variedad": personalidad.tono.variedad,
        "conectores": conectores,
        "abstencion": {
            "generico": tono.variantes("no_answer"),
            "premisa_no_encontrada": tono.variantes("premise_not_found"),
            "aclaracion": tono.variantes("needs_clarification"),
            "zona_gris_intro": tono.variantes("related_intro"),
            "zona_gris_cierre": tono.variantes("related_check"),
            "foco_ausente": tono.variantes("missing_focus"),
            "alternativas_intro": tono.variantes("alternatives_intro"),
        },
        "citas": {
            "breve": paquete.mensajes.cita_breve,
            "completa": paquete.mensajes.cita_completa,
            "sin_seccion": paquete.mensajes.sin_seccion,
        },
        "conversacional": {
            **paquete.conversacional.model_dump(mode="python"),
            "respuestas": {c: tono.variantes(c) for c in ("greeting", "thanks", "farewell", "capability")},
        },
    }
    if dominio is None:
        return datos
    variables = {
        "assistant_name": dominio.get("nombre_asistente", paquete.interfaz.get("default_assistant_name", "")),
        "domain_description": dominio.get("descripcion_dominio", paquete.interfaz.get("default_domain_description", "")),
    }

    def sustituir(texto: str) -> str:
        salida = texto.format(**variables)
        for forma, contraccion in paquete.contracciones.items():
            salida = salida.replace(forma, contraccion)
        return salida

    respuestas = datos["conversacional"].get("respuestas", {})
    for categoria, valor in respuestas.items():
        # Cada categoría puede declarar un texto suelto o varias variantes.
        respuestas[categoria] = sustituir(valor) if isinstance(valor, str) else [sustituir(t) for t in valor]
    return datos
