"""Tests unitarios de ``rag/servicio/seguridad.py``:
clave de widget y *token bucket* del límite de peticiones. Sin FastAPI, sin
red, sin índice -- solo la lógica determinista, para que corran siempre
(no dependen del corpus real ni de Qdrant)."""
from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from rag.servicio.seguridad import LimitadorPeticiones, identificador_limitador, verificar_clave_widget


# ---------------------------------------------------------------------------
# verificar_clave_widget
# ---------------------------------------------------------------------------

def test_sin_claves_configuradas_pasa_cualquier_cosa():
    """Comportamiento por defecto EXPLÍCITO (ver docstring del módulo): sin
    claves en configuracion/asistente.yaml, no se exige autenticación."""
    verificar_clave_widget(None, [])
    verificar_clave_widget("cualquier-cosa", [])


def test_clave_valida_pasa():
    verificar_clave_widget("clave-sitio-a", ["clave-sitio-a", "clave-sitio-b"])


def test_clave_invalida_lanza_401():
    with pytest.raises(HTTPException) as exc_info:
        verificar_clave_widget("clave-que-no-existe", ["clave-sitio-a"])
    assert exc_info.value.status_code == 401


def test_clave_ausente_con_claves_configuradas_lanza_401():
    """Si hay claves configuradas y la petición no trae ninguna, se rechaza
    -- no es lo mismo que "sin claves configuradas"."""
    with pytest.raises(HTTPException) as exc_info:
        verificar_clave_widget(None, ["clave-sitio-a"])
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# identificador_limitador
# ---------------------------------------------------------------------------

def test_identificador_distingue_clave_e_ip():
    a = identificador_limitador("clave-1", "1.2.3.4")
    b = identificador_limitador("clave-2", "1.2.3.4")
    c = identificador_limitador("clave-1", "5.6.7.8")
    assert len({a, b, c}) == 3


def test_identificador_sin_clave_ni_ip_no_lanza():
    assert identificador_limitador(None, None) == "sin-clave:desconocida"


# ---------------------------------------------------------------------------
# LimitadorPeticiones (token bucket)
# ---------------------------------------------------------------------------

def test_primera_peticion_siempre_se_admite():
    lim = LimitadorPeticiones(capacidad=1, tasa_por_segundo=0.001)
    assert lim.permitir("x") is True


def test_dispara_despues_de_agotar_la_capacidad():
    """N=capacidad peticiones se admiten; la N+1, con una tasa de recarga
    despreciable, se rechaza -- el corazón del criterio de cierre 2."""
    capacidad = 5
    lim = LimitadorPeticiones(capacidad=capacidad, tasa_por_segundo=1e-9)
    admitidas = [lim.permitir("misma-clave-ip") for _ in range(capacidad)]
    assert all(admitidas), "las primeras 'capacidad' peticiones deben admitirse"
    assert lim.permitir("misma-clave-ip") is False, "la petición número capacidad+1 debe rechazarse"


def test_identificadores_distintos_no_comparten_bucket():
    lim = LimitadorPeticiones(capacidad=1, tasa_por_segundo=1e-9)
    assert lim.permitir("cliente-a") is True
    assert lim.permitir("cliente-a") is False  # cliente-a ya agotó su bucket
    assert lim.permitir("cliente-b") is True   # cliente-b tiene el suyo propio, sin tocar


def test_recarga_con_el_tiempo():
    """Con una tasa de recarga alta, tras esperar lo suficiente el bucket
    vuelve a admitir -- verifica la aritmética de recarga, no solo el
    agotamiento inicial."""
    lim = LimitadorPeticiones(capacidad=1, tasa_por_segundo=1000.0)  # recarga casi instantánea
    assert lim.permitir("x") is True
    assert lim.permitir("x") is False
    time.sleep(0.02)  # 1000 tokens/s * 0.02s = 20 tokens de sobra para 1 de capacidad
    assert lim.permitir("x") is True


def test_reiniciar_vacia_los_buckets():
    lim = LimitadorPeticiones(capacidad=1, tasa_por_segundo=1e-9)
    lim.permitir("x")
    assert lim.permitir("x") is False
    lim.reiniciar()
    assert lim.permitir("x") is True


def test_capacidad_o_tasa_no_positivas_lanzan_value_error():
    with pytest.raises(ValueError):
        LimitadorPeticiones(capacidad=0, tasa_por_segundo=1.0)
    with pytest.raises(ValueError):
        LimitadorPeticiones(capacidad=1.0, tasa_por_segundo=0)


# ---------------------------------------------------------------------------
# Normalización de la configuración: una clave vacía NO puede abrir el servicio
# ---------------------------------------------------------------------------

def test_clave_escrita_sin_valor_cae_a_lista_vacia(tmp_path):
    """``cors_origenes:`` a secas es ``None`` para YAML, no lista vacía.

    Consume: un ``configuracion/asistente.yaml`` con las dos claves de seguridad
    escritas sin valor. Produce: la confirmación de que ``cargar_dominio``
    las entrega como listas vacías.

    Sin esta normalización, ``CORSMiddleware`` recibía ``None`` y el
    servicio moría al arrancar con un ``TypeError`` que no nombra el
    problema. El valor de repuesto es la lista vacía -- falla CERRADO: una
    configuración a medio escribir nunca debe terminar abriendo el servicio.
    """
    from rag.configuracion import cargar_dominio

    ruta = tmp_path / "dominio.yaml"
    ruta.write_text(
        "nombre_asistente: X\ndescripcion_dominio: y\nidioma: es\n"
        "perfil: _generico\ncors_origenes:\nclaves_widget:\n",
        encoding="utf-8",
    )
    cfg = cargar_dominio(str(ruta))
    assert cfg["cors_origenes"] == []
    assert cfg["claves_widget"] == []
    assert cfg["perfil"] == "_generico"
