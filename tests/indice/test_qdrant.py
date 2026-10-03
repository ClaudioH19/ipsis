"""Tests de las utilidades de indexación Qdrant: vector BM25 disperso,
estadísticas del índice y nombrado versionado de colecciones.

No requieren un servidor Qdrant: son funciones puras de Python. La
integración real (indexar + consultar) la cubren las pruebas marcadas
``slow`` de ``tests/cli/test_cli.py`` y ``tests/integracion/test_portabilidad.py``.
"""
import pytest

from rag.indice.estadisticas import EstadisticasLexicas
from rag.indice.qdrant import (
    cargar_estadisticas,
    crear_cliente_qdrant,
    nombre_coleccion_versionada,
    paquete_del_indice,
    ruta_estadisticas,
    vector_disperso,
)
from rag.lenguaje.lexico import bm25_consulta, bm25_doc, id_termino
from rag.lenguaje.paquete import cargar_paquete
from rag.lenguaje.texto import terminos


# ---------------------------------------------------------------------------
# BM25 disperso con términos del proyecto
# ---------------------------------------------------------------------------

def test_vector_disperso_usa_ids_por_hash_y_tf_saturado():
    est = EstadisticasLexicas.construir(["hola mundo", "hola feliz"])
    pesos = bm25_doc(terminos("hola hola mundo"), est)
    vector = vector_disperso(pesos)
    assert set(vector.indices) == {id_termino("hola"), id_termino("mundo")}
    assert pesos[id_termino("hola")] > pesos[id_termino("mundo")]


def test_consulta_con_terminos_fuera_del_corpus_no_falla():
    vector = vector_disperso(bm25_consulta(terminos("palabra desconocida")))
    assert len(vector.indices) == 2 and set(vector.values) == {1.0}


def test_la_consulta_usa_el_stemmer_con_que_se_indexo():
    es = cargar_paquete("es")
    est = EstadisticasLexicas.construir(["Los documentos vigentes"], es)
    assert terminos("documento", paquete_del_indice(est)) == terminos("documentos", es)


def test_estadisticas_se_guardan_junto_a_la_coleccion(tmp_path):
    est = EstadisticasLexicas.construir(["hola mundo"])
    est.guardar(ruta_estadisticas("col_v1", str(tmp_path)))
    assert cargar_estadisticas("col_v1", str(tmp_path)) == est
    with pytest.raises(FileNotFoundError, match="rag indexar"):
        cargar_estadisticas("otra_v1", str(tmp_path))


# ---------------------------------------------------------------------------
# crear_cliente_qdrant: la elección local/servidor es
# configuración (parámetro > variable de entorno > default), nunca dos
# implementaciones distintas. Se testea la lógica de selección sin requerir
# un servidor Qdrant real levantado (el cliente de la rama "servidor" no
# abre conexión hasta la primera llamada de red).
# ---------------------------------------------------------------------------

def test_crear_cliente_qdrant_modo_local_por_defecto(monkeypatch):
    import shutil
    import tempfile

    monkeypatch.delenv("QDRANT_MODO", raising=False)
    ruta = tempfile.mkdtemp(prefix="qdr_test_")
    try:
        client = crear_cliente_qdrant(qdrant_path=ruta)
        assert client is not None
        client.close()
    finally:
        shutil.rmtree(ruta, ignore_errors=True)


def test_crear_cliente_qdrant_modo_local_sin_path_falla():
    with pytest.raises(ValueError):
        crear_cliente_qdrant(qdrant_path=None, modo="local")


def test_crear_cliente_qdrant_modo_servidor_usa_url_explicita(monkeypatch):
    monkeypatch.delenv("QDRANT_URL", raising=False)
    client = crear_cliente_qdrant(modo="servidor", url_servidor="http://localhost:6333")
    assert client is not None


def test_crear_cliente_qdrant_modo_por_env_var(monkeypatch):
    monkeypatch.setenv("QDRANT_MODO", "servidor")
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    # con QDRANT_MODO=servidor, qdrant_path (aunque apunte a algo inexistente)
    # se ignora -- se usa la URL del servidor, sin abrir el path on-disk.
    client = crear_cliente_qdrant(qdrant_path="ruta/que/no/se/usa")
    assert client is not None


def test_nombre_coleccion_versionada_formato():
    nombre = nombre_coleccion_versionada("biblioteca", "paraphrase-multilingual-MiniLM-L12-v2", 1)
    assert nombre == "biblioteca_paraphrase-multilingual-MiniLM-L12-v2_v1"


def test_nombre_coleccion_versionada_sanitiza_barra_del_modelo():
    """El nombre del modelo puede venir con `/` (namespace de HuggingFace);
    Qdrant no admite `/` en nombres de colección."""
    nombre = nombre_coleccion_versionada("biblioteca", "intfloat/multilingual-e5-small", 1)
    assert "/" not in nombre
    assert nombre == "biblioteca_intfloat-multilingual-e5-small_v1"


def test_nombre_coleccion_versionada_no_mezcla_modelos():
    """Dos modelos distintos SIEMPRE producen nombres de colección distintos
    (regla dura de la sección 3.2: nunca mezclar vectores de modelos
    distintos en la misma colección)."""
    n1 = nombre_coleccion_versionada("biblioteca", "modelo-a", 1)
    n2 = nombre_coleccion_versionada("biblioteca", "modelo-b", 1)
    assert n1 != n2


def test_nombre_coleccion_versionada_con_sufijo():
    nombre = nombre_coleccion_versionada("biblioteca", "modelo-a", 1, sufijo="CH-PAR__header")
    assert nombre == "biblioteca_modelo-a_v1__CH-PAR__header"
