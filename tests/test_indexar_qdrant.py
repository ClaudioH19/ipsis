"""Tests de las utilidades de indexación Qdrant: vocabulario BM25 disperso y
nombrado versionado de colecciones.

No requieren un servidor Qdrant: son funciones puras de Python. La
integración real (indexar + consultar) la cubren las pruebas marcadas
``slow`` de ``tests/test_cli.py`` y ``tests/test_portabilidad.py``.
"""
import pytest

from rag.corpus import (
    tokenizar_bm25,
    construir_vocabulario_bm25,
    texto_a_vector_sparse,
    nombre_coleccion_versionada,
    crear_cliente_qdrant,
)


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


def test_tokenizar_bm25_basico():
    assert tokenizar_bm25("El plazo es de 15 días hábiles.") == ["el", "plazo", "es", "de", "15", "días", "hábiles"]


def test_construir_vocabulario_bm25_orden_determinista():
    textos = ["hola mundo", "mundo feliz", "hola feliz mundo"]
    vocab = construir_vocabulario_bm25(textos)
    assert vocab == {"hola": 0, "mundo": 1, "feliz": 2}


def test_construir_vocabulario_bm25_reproducible():
    textos = ["a b c", "c d e", "e f a"]
    v1 = construir_vocabulario_bm25(textos)
    v2 = construir_vocabulario_bm25(textos)
    assert v1 == v2


def test_texto_a_vector_sparse_conteos():
    vocab = {"hola": 0, "mundo": 1, "feliz": 2}
    sparse = texto_a_vector_sparse("hola hola mundo", vocab)
    pares = dict(zip(sparse.indices, sparse.values))
    assert pares[vocab["hola"]] == 2.0
    assert pares[vocab["mundo"]] == 1.0
    assert vocab["feliz"] not in pares


def test_texto_a_vector_sparse_ignora_oov():
    """Tokens fuera del vocabulario del índice se descartan (limitación
    documentada del diseño, no un error)."""
    vocab = {"hola": 0}
    sparse = texto_a_vector_sparse("hola palabra_desconocida", vocab)
    assert sparse.indices == [0]
    assert sparse.values == [1.0]


def test_texto_a_vector_sparse_vacio_sin_coincidencias():
    vocab = {"hola": 0}
    sparse = texto_a_vector_sparse("otra cosa distinta", vocab)
    assert sparse.indices == []
    assert sparse.values == []


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
