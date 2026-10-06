"""Catálogo de mensajes de la interfaz (CLI y servicio).

Los textos viven en ``ipsis/recursos/mensajes/<idioma>.yaml``, nunca en el
código: inglés por defecto y español con ``IPSIS_LANG=es``. Una clave que
falte en un idioma cae al inglés; una que falte en inglés es un error de
programación (las pruebas verifican que ambos catálogos tengan las mismas
claves y las mismas variables).
"""
from __future__ import annotations

import os
from functools import lru_cache
from importlib.resources import files

import yaml

IDIOMAS = ("en", "es")
POR_DEFECTO = "en"


def idioma_interfaz() -> str:
    """``es`` si ``IPSIS_LANG`` empieza por ``es`` (``es``, ``es_CL``…); si no, ``en``."""
    valor = os.environ.get("IPSIS_LANG", "").strip().lower()
    return next((idioma for idioma in IDIOMAS if valor.startswith(idioma)), POR_DEFECTO)


def _aplanar(datos: dict, prefijo: str = "") -> dict[str, str]:
    plano: dict[str, str] = {}
    for clave, valor in datos.items():
        ruta = f"{prefijo}{clave}"
        if isinstance(valor, dict):
            plano.update(_aplanar(valor, ruta + "."))
        else:
            plano[ruta] = str(valor)
    return plano


@lru_cache(maxsize=None)
def catalogo(idioma: str) -> dict[str, str]:
    """Todas las claves de un idioma, aplanadas (``load.done``)."""
    texto = files(__package__).joinpath("mensajes", f"{idioma}.yaml").read_text(encoding="utf-8")
    return _aplanar(yaml.safe_load(texto) or {})


def t(clave: str, **valores) -> str:
    """El mensaje ``clave`` en el idioma de la interfaz, con ``valores`` sustituidos (``str.format``)."""
    texto = catalogo(idioma_interfaz()).get(clave)
    if texto is None:
        texto = catalogo(POR_DEFECTO)[clave]
    return texto.format(**valores)


__all__ = ["IDIOMAS", "catalogo", "idioma_interfaz", "t"]
