from concurrent.futures import ThreadPoolExecutor

import pytest

from ipsis.nucleo.progreso import informar, observar_progreso


def test_los_avisos_son_locales_al_contexto_y_se_restauran_al_fallar():
    eventos, internos = [], []
    informar("sin_observador")
    with observar_progreso(lambda etapa, **datos: eventos.append((etapa, datos))):
        informar("documento", archivo="manual.pdf")
        with pytest.raises(ValueError), observar_progreso(lambda etapa, **datos: internos.append(etapa)):
            informar("lectura")
            raise ValueError("prueba")
        informar("verificacion")
        # Un trabajo de otra sesión no produce avisos en nuestra terminal.
        with ThreadPoolExecutor(max_workers=1) as hilos:
            hilos.submit(informar, "otra_sesion").result()
    informar("ya_cerrado")
    assert eventos == [("documento", {"archivo": "manual.pdf"}), ("verificacion", {})]
    assert internos == ["lectura"]
