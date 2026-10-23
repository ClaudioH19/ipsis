"""Glosario: el disco usa nombres en inglés y el código los internos, sin pérdida en la ida y vuelta."""
from __future__ import annotations

import pytest

from ipsis.configuracion.archivos import interpretar, volcar
from ipsis.configuracion.glosario import ARCHIVOS, a_externo, a_interno, nombres_externos
from ipsis.recursos import leer_plantilla

PLANTILLAS = {"assistant.yaml": "asistente", "engine.yaml": "motor", "styles.yaml": "estilos",
              "personality.yaml": "personalidad", "domain.yaml": "dominio"}


def _claves(espec, prefijo=""):
    for regla in espec.values():
        yield prefijo + regla.externa
        if regla.hijos:
            yield from _claves(regla.hijos, prefijo + regla.externa + ".")


@pytest.mark.parametrize("archivo", sorted(ARCHIVOS))
def test_sin_nombres_externos_repetidos(archivo):
    claves = list(_claves(ARCHIVOS[archivo]))
    assert len(claves) == len(set(claves))


@pytest.mark.parametrize("nombre", sorted(PLANTILLAS))
def test_plantillas_ida_y_vuelta(nombre):
    archivo = PLANTILLAS[nombre]
    interno = interpretar(leer_plantilla(nombre), archivo)
    assert a_interno(a_externo(interno, archivo), archivo) == interno
    assert interpretar(volcar(interno, archivo), archivo) == interno


def test_traduce_claves_anidadas_listas_y_valores():
    interno = {"recuperacion": {"modo": "hibrida", "top_k": 5},
               "conversacion": {"vencimiento_minutos": 30}, "clave_propia": {"modo": "x"}}
    externo = a_externo(interno, "motor")
    assert externo == {"retrieval": {"mode": "hybrid", "top_k": 5},
                       "conversation": {"expiry_minutes": 30}, "clave_propia": {"modo": "x"}}
    assert a_interno(externo, "motor") == interno

    catalogo = {"documentos": [{"archivo": "a.md", "vigente": False}]}
    assert a_externo(catalogo, "catalogo") == {"documents": [{"file": "a.md", "active": False}]}


def test_un_archivo_en_espanol_se_sigue_leyendo():
    """Las claves desconocidas pasan tal cual: un proyecto sin migrar se interpreta igual."""
    assert a_interno({"nombre_asistente": "Demo", "idioma": "es"}, "asistente") == \
        {"nombre_asistente": "Demo", "idioma": "es"}


def test_nombres_externos_en_mensajes():
    texto = nombres_externos("recuperacion.modo inválido", "motor")
    assert "retrieval" in texto and "recuperacion" not in texto
