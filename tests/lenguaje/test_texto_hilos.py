"""``terminos()`` en varios hilos: el servicio atiende peticiones en paralelo."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from ipsis.lenguaje.texto import terminos


def test_terminos_es_estable_con_hilos_simultaneos():
    paquete = SimpleNamespace(stemmer="spanish")
    textos = [f"Las solicitudes de reposición llegan dentro de {n} días hábiles al encargado de bodega"
              for n in range(400)]
    esperado = [terminos(t, paquete) for t in textos]
    with ThreadPoolExecutor(8) as pool:
        obtenido = list(pool.map(lambda t: terminos(t, paquete), textos * 5))
    assert obtenido == esperado * 5
