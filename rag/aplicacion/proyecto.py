"""Casos de uso del proyecto: configurar el asistente."""
from __future__ import annotations

from pathlib import Path

import yaml

from rag.configuracion.carga import (
    CLAVES_DOMINIO_VALIDAS,
    RUTA_DOMINIO,
    _CLAVES_LISTA_SEPARADA_POR_COMA,
    _encabezado_comentarios,
    cargar_dominio,
)


def actualizar_dominio(pares: dict[str, str], ruta: str = RUTA_DOMINIO) -> dict:
    desconocidas = set(pares) - CLAVES_DOMINIO_VALIDAS
    if desconocidas:
        raise ValueError(
            f"clave(s) desconocida(s) para 'rag configurar': {sorted(desconocidas)}. "
            f"Válidas: {sorted(CLAVES_DOMINIO_VALIDAS)}"
        )

    ruta_p = Path(ruta)
    nuevo = cargar_dominio(ruta)
    for clave, valor in pares.items():
        if clave in _CLAVES_LISTA_SEPARADA_POR_COMA:
            nuevo[clave] = [v.strip() for v in valor.split(",") if v.strip()]
        else:
            nuevo[clave] = valor

    if "idioma" in pares:
        from rag.lenguaje.paquete import idiomas_disponibles

        if nuevo["idioma"] not in idiomas_disponibles():
            raise ValueError(
                f"no hay paquete de idioma {nuevo['idioma']!r} (disponibles: {idiomas_disponibles()})"
            )

    ruta_p.parent.mkdir(parents=True, exist_ok=True)
    ruta_p.write_text(
        _encabezado_comentarios(ruta_p)
        + yaml.safe_dump(nuevo, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return nuevo
