"""Carril multimedia en la consulta (M2.1): búsqueda por ficha, umbral y su integración con el motor v2."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from ipsis.aplicacion.registro_base import LiteralOffsetsVerifier
from ipsis.configuracion.archivos import interpretar
from ipsis.configuracion.esquemas import MediaConfig
from ipsis.consulta.media import BuscadorMedia
from ipsis.consulta.v2 import MotorV2
from ipsis.indice.qdrant import ColeccionQdrant, cargar_estadisticas
from ipsis.ingesta.indice_media import indexar_fichas, nombre_coleccion_media
from ipsis.nucleo.esquemas import ChunkRecord, RetrievalCandidate, RetrievalSignals

MODELO = "modelo/falso"
CFG_REC = {"coleccion_base": "proyecto", "modelo": MODELO, "version_coleccion": 1, "qdrant_path": "q"}


class CodificadorFalso:
    """Vectores por hash de palabra (64 dimensiones): determinista y sin modelos."""

    dimension = 64

    def _vec(self, texto):
        v = np.zeros(self.dimension, dtype="float32")
        for palabra in texto.lower().replace(".", " ").replace("\n", " ").split():
            v[int(hashlib.md5(palabra.encode()).hexdigest(), 16) % self.dimension] += 1
        return v / (np.linalg.norm(v) or 1.0)

    def codificar_documentos(self, textos):
        return np.array([self._vec(t) for t in textos])

    def codificar_consultas(self, textos):
        return np.array([self._vec(t) for t in textos])


INDUCCION = {
    "title": "Inducción a la plataforma de matrícula", "kind": "video", "url": "https://example.org/induccion",
    "description": "Cómo ingresar, inscribir asignaturas y revisar el horario.", "version": "2026-03", "duration": "14:32",
    "chapters": [{"at": "01:10", "title": "Ingresar con la clave única"},
                 {"at": "06:45", "title": "Inscribir asignaturas", "description": "Elegir secciones y confirmar."}],
}
CHARLA = {"title": "Charla de bienvenida", "kind": "audio", "url": "https://example.org/charla",
          "description": "Presentación del semestre y de los equipos de trabajo."}
BIBLIOTECA = {"title": "Recorrido por la biblioteca", "kind": "video", "url": "https://example.org/biblioteca",
              "description": "Horarios de préstamo, salas de estudio y renovación de libros."}


@pytest.fixture
def carril(tmp_path, monkeypatch):
    """Colección del carril con tres fichas, en un Qdrant local; devuelve una función que crea el buscador."""
    from qdrant_client import QdrantClient

    monkeypatch.chdir(tmp_path)
    media = tmp_path / "media"
    media.mkdir()
    for nombre, datos in (("induccion", INDUCCION), ("charla", CHARLA), ("biblioteca", BIBLIOTECA)):
        (media / f"{nombre}.yaml").write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    codificador = CodificadorFalso()
    cliente = QdrantClient(path=str(tmp_path / "qdrant"))
    resumen = indexar_fichas(modelo=MODELO, coleccion="proyecto", qdrant_path=str(tmp_path / "qdrant"),
                             version_coleccion=1, codificador=codificador, client=cliente, permitir_recrear=True,
                             carpeta=media)
    assert resumen.nombre_coleccion == nombre_coleccion_media("proyecto", MODELO, 1)

    def crear(**opciones):
        coleccion = ColeccionQdrant(client=cliente, codificador=codificador,
                                    estadisticas=cargar_estadisticas(resumen.nombre_coleccion),
                                    nombre=resumen.nombre_coleccion, qdrant_path=str(tmp_path / "qdrant"))
        return BuscadorMedia(coleccion, lambda texto: codificador.codificar_consultas([texto])[0], **opciones)

    yield crear
    cliente.close()


# --- el buscador -------------------------------------------------------------

def test_una_pregunta_sobre_un_capitulo_lleva_al_minuto_exacto(carril):
    candidatos = carril().candidatos_agrupados(["Inscribir asignaturas elegir secciones"])
    primero = candidatos[0]
    assert primero["media_id"] == "induccion" and primero["chapter_title"] == "Inscribir asignaturas"
    assert primero["start_seconds"] == 405 and primero["chapter_description"] == "Elegir secciones y confirmar."
    # texto literal de la ficha, sin nada generado
    assert primero["title"] == INDUCCION["title"] and primero["description"] == INDUCCION["description"]
    assert primero["kind"] == "video" and primero["url"] == INDUCCION["url"] and primero["file"] is None
    assert primero["duration"] == 872 and primero["version"] == "2026-03"
    assert isinstance(primero["score"], float) and primero["fusion_rank"] >= 1


def test_una_pregunta_sobre_el_video_en_general_no_manda_a_un_capitulo(carril):
    """La unidad que se muestra es la de mayor coseno: si la pregunta es sobre toda la ficha, se muestra la ficha."""
    candidatos = carril().candidatos_agrupados(["Cómo ingresar, inscribir asignaturas y revisar el horario."])
    primero = next(c for c in candidatos if c["media_id"] == "induccion")
    assert primero["start_seconds"] is None and primero["chapter_title"] is None


def test_una_ficha_aparece_una_sola_vez_aunque_coincidan_varias_de_sus_unidades(carril):
    ids = [c["media_id"] for c in carril().candidatos_agrupados(["Inducción a la plataforma de matrícula inscribir"])]
    assert ids.count("induccion") == 1


def test_una_ficha_sin_capitulos_se_muestra_por_si_misma(carril):
    candidatos = carril().candidatos_agrupados(["Charla de bienvenida presentación del semestre"])
    charla = next(c for c in candidatos if c["media_id"] == "charla")
    assert charla["start_seconds"] is None and charla["chapter_title"] is None and charla["kind"] == "audio"
    assert charla["duration"] is None


def test_sin_puntaje_minimo_no_se_publica_nada_pero_se_mide(carril):
    buscador = carril()
    assert buscador.puntaje_minimo is None
    assert buscador.buscar(["Recorrido por la biblioteca horarios de préstamo"]) == []
    assert buscador.candidatos_agrupados(["Recorrido por la biblioteca horarios de préstamo"])[0]["media_id"] == "biblioteca"


def test_el_umbral_es_un_coseno_absoluto(carril):
    pregunta = ["Recorrido por la biblioteca horarios de préstamo salas de estudio"]
    mejor = carril().candidatos_agrupados(pregunta)[0]
    assert carril(puntaje_minimo=mejor["score"] - 1e-6).buscar(pregunta)[0]["media_id"] == "biblioteca"
    assert carril(puntaje_minimo=mejor["score"] + 1e-3).buscar(pregunta) == []  # nada llega tan alto: no hay video
    assert carril(puntaje_minimo=0.99).buscar(["zzz qqq xxx"]) == []  # una pregunta ajena no pasa


def test_el_tope_de_resultados_se_respeta(carril):
    pregunta = ["plataforma matrícula biblioteca charla bienvenida horarios inscribir"]
    assert len(carril(puntaje_minimo=-1.0, max_resultados=1).buscar(pregunta)) == 1
    assert 1 < len(carril(puntaje_minimo=-1.0, max_resultados=3).buscar(pregunta)) <= 3


def test_la_variante_ortografica_suma_candidatos_sin_duplicar_fichas(carril):
    una = carril().candidatos_agrupados(["recorido por la bibliotea"])
    dos = carril().candidatos_agrupados(["recorido por la bibliotea", "recorrido por la biblioteca"])
    assert dos[0]["media_id"] == "biblioteca"
    assert [c["media_id"] for c in dos] == list(dict.fromkeys(c["media_id"] for c in dos))
    assert len(dos) >= len(una)


def test_sin_coleccion_del_carril_no_hay_buscador(tmp_path):
    from qdrant_client import QdrantClient

    cliente = QdrantClient(path=str(tmp_path / "q"))
    try:
        recuperador = SimpleNamespace(coleccion=SimpleNamespace(client=cliente, codificador=CodificadorFalso()),
                                      vector_consulta=lambda t: None)
        assert BuscadorMedia.desde_recuperador(recuperador, CFG_REC, {"max_resultados": 1, "puntaje_minimo": None}) is None
    finally:
        cliente.close()


def test_con_coleccion_el_buscador_hereda_las_opciones(carril, tmp_path):
    base = carril()
    recuperador = SimpleNamespace(coleccion=base.coleccion, vector_consulta=base.vector_consulta)
    buscador = BuscadorMedia.desde_recuperador(
        recuperador, {**CFG_REC, "qdrant_path": str(tmp_path / "qdrant")}, {"max_resultados": 2, "puntaje_minimo": 0.5})
    assert buscador.max_resultados == 2 and buscador.puntaje_minimo == 0.5
    assert buscador.coleccion.client is base.coleccion.client  # el candado de Qdrant local es de una sola conexión


# --- la configuración --------------------------------------------------------

def test_la_configuracion_del_carril_esta_apagada_por_defecto():
    assert MediaConfig().model_dump() == {"activo": False, "max_resultados": 1, "puntaje_minimo": None,
                                          "presupuesto_ms": 150}


def test_la_configuracion_se_lee_con_los_nombres_en_ingles_del_archivo():
    datos = interpretar("media:\n  enabled: true\n  max_results: 2\n  min_score: 0.8\n  budget_ms: 200\n", "motor")
    assert MediaConfig.model_validate(datos["media"]).model_dump() == {
        "activo": True, "max_resultados": 2, "puntaje_minimo": 0.8, "presupuesto_ms": 200}


@pytest.mark.parametrize("campo, valor", [("max_resultados", 0), ("max_resultados", 6), ("puntaje_minimo", 1.5),
                                          ("puntaje_minimo", -2), ("presupuesto_ms", 0), ("desconocido", 1)])
def test_la_configuracion_rechaza_valores_fuera_de_rango(campo, valor):
    with pytest.raises(ValueError):
        MediaConfig.model_validate({campo: valor})


# --- el motor v2 --------------------------------------------------------------

def _candidato(texto, cid):
    return RetrievalCandidate(chunk=ChunkRecord(chunk_id=cid, doc_id="reglamento", doc_titulo="Reglamento", version="1",
        texto_fuente=texto, texto_embedding=texto, offset_inicio=100 * len(cid), offset_fin=100 * len(cid) + len(texto),
        seccion_path=["P1"], tipo_contenido="tabla"), signals=RetrievalSignals(fusion_rank=1, fusion_score=.04))


class Recuperador:
    def __init__(self, candidatos):
        self.candidatos = candidatos

    def recuperar(self, consulta, limite, filtro=None):
        return [c.model_copy(deep=True) for c in self.candidatos[:limite]]

    def calentar(self):
        pass

    def n_chunks(self):
        return len(self.candidatos)

    def inventario_entidades(self):
        return set()

    def estadisticas_lexico(self):
        return SimpleNamespace()


class BuscadorFalso:
    def __init__(self, fichas=None, error=None):
        self.fichas, self.error, self.llamadas = fichas if fichas is not None else [{"media_id": "v", "score": 0.9}], error, []

    def buscar(self, preguntas):
        self.llamadas.append(list(preguntas))
        if self.error:
            raise self.error
        return self.fichas


def _motor(n=2, **kwargs):
    candidatos = [_candidato(f"Texto del artículo número {i} sobre matrícula.", f"c{i}") for i in range(n)]
    return MotorV2(retriever=Recuperador(candidatos), verificador=LiteralOffsetsVerifier(),
                   plantillas={"abstencion": {"generico": ["No hay evidencia."], "zona_gris_intro": ["Pasajes:"]}}, **kwargs)


def _sin_ruido(resultado):
    """Lo publicado de documentos, sin latencias ni diagnósticos de tiempo."""
    contrato = dict(resultado.contrato_http)
    contrato.pop("multimedia", None)
    contrato.pop("latencia_ms", None)
    return {"fragmentos": [{k: v for k, v in f.items()} for f in contrato["fragmentos"]],
            "evidencias": [e.model_dump(mode="json") for e in resultado.evidencias],
            "bloques": contrato.get("bloques"), "mensaje": resultado.mensaje if hasattr(resultado, "mensaje") else None}


def test_sin_buscador_no_hay_clave_multimedia():
    resultado = _motor().consultar("¿Cómo me matriculo?", "s")
    assert "multimedia" not in resultado.contrato_http and "multimedia" not in resultado.diagnostico


def test_con_el_carril_las_fuentes_de_documentos_no_cambian():
    sin = _motor().consultar("¿Cómo me matriculo?", "s")
    buscador = BuscadorFalso()
    con = _motor(buscador_media=buscador).consultar("¿Cómo me matriculo?", "s")
    assert _sin_ruido(con) == _sin_ruido(sin)  # mismas fuentes, mismo orden, mismas ventanas, mismos puntajes
    assert con.contrato_http["multimedia"] == [{"media_id": "v", "score": 0.9}]
    assert con.diagnostico["multimedia"]["publicadas"] == 1
    assert buscador.llamadas == [["¿Cómo me matriculo?"]]  # la pregunta (y su variante, si la hubiera)


def test_con_el_carril_encendido_pero_sin_fichas_publicables_la_lista_va_vacia():
    resultado = _motor(buscador_media=BuscadorFalso(fichas=[])).consultar("¿Cómo me matriculo?", "s")
    assert resultado.contrato_http["multimedia"] == []


def test_sin_presupuesto_el_carril_se_omite_y_se_avisa():
    buscador = BuscadorFalso()
    # el motor reserva 150 ms para publicar: con 150 ms de carril ya no cabe en un presupuesto de 200 ms
    motor = _motor(buscador_media=buscador, opciones={"presupuesto_consulta_ms": 200}, opciones_media={"presupuesto_ms": 150})
    resultado = motor.consultar("¿Cómo me matriculo?", "s")
    assert buscador.llamadas == [] and "multimedia" not in resultado.contrato_http
    assert "carril multimedia omitido por presupuesto" in resultado.diagnostico["advertencias"]
    assert resultado.evidencias  # y las fuentes de documentos salen igual


def test_un_fallo_del_carril_nunca_tumba_la_consulta_de_documentos():
    sin = _motor().consultar("¿Cómo me matriculo?", "s")
    con = _motor(buscador_media=BuscadorFalso(error=RuntimeError("Qdrant caído"))).consultar("¿Cómo me matriculo?", "s")
    assert _sin_ruido(con) == _sin_ruido(sin) and "multimedia" not in con.contrato_http
    assert "carril multimedia falló: RuntimeError" in con.diagnostico["advertencias"]


def test_pedir_mas_resultados_no_vuelve_a_buscar_fichas():
    buscador = BuscadorFalso()
    motor = _motor(n=5, buscador_media=buscador)
    primera = motor.consultar("¿Cómo me matriculo?", "s")
    cursor = primera.contrato_http["continuation"]
    assert cursor and len(buscador.llamadas) == 1
    segunda = motor.continuar("¿Cómo me matriculo?", "s", cursor)
    assert len(buscador.llamadas) == 1 and "multimedia" not in segunda.contrato_http


# --- la API pública (M3) ----------------------------------------------------------

FICHA_PUBLICA = {"media_id": "induccion", "title": "Inducción", "kind": "video", "url": "https://example.org/v",
                 "file": None, "start_seconds": 410, "chapter_title": "Inscribir asignaturas",
                 "chapter_description": "Elegir secciones.", "description": "Cómo ingresar.", "duration": 872,
                 "version": "2026-03", "score": 0.83, "fusion_rank": 1}


def _publica(fichas):
    from ipsis.servicio.api import RespuestaConsulta, respuesta_publica

    contrato = _motor(buscador_media=BuscadorFalso(fichas=fichas)).consultar("¿Cómo me matriculo?", "s").contrato_http
    salida = respuesta_publica(contrato)
    RespuestaConsulta.model_validate(salida)
    return salida


def test_la_api_publica_las_fichas_con_los_campos_de_la_ficha_y_sin_puntaje():
    salida = _publica([FICHA_PUBLICA])
    assert salida["media"] == [{"media_id": "induccion", "title": "Inducción", "kind": "video",
        "url": "https://example.org/v", "start_seconds": 410, "chapter_title": "Inscribir asignaturas",
        "chapter_description": "Elegir secciones.", "description": "Cómo ingresar.", "duration": 872, "version": "2026-03"}]


def test_las_fichas_sin_enlace_no_se_publican_hasta_servir_archivos():
    assert "media" not in _publica([{**FICHA_PUBLICA, "url": None, "file": "induccion.mp4"}])


def test_sin_fichas_publicables_no_hay_clave_media_y_los_fragmentos_no_cambian():
    sin_carril = _publica([])
    con_carril = _publica([FICHA_PUBLICA])
    assert "media" not in sin_carril
    assert con_carril["fragments"] == sin_carril["fragments"] and con_carril["answer_blocks"] == sin_carril["answer_blocks"]


def test_la_api_no_publica_media_en_paginas_siguientes():
    from ipsis.servicio.api import respuesta_publica

    motor = _motor(n=5, buscador_media=BuscadorFalso(fichas=[FICHA_PUBLICA]))
    cursor = motor.consultar("¿Cómo me matriculo?", "s").contrato_http["continuation"]
    assert "media" not in respuesta_publica(motor.continuar("¿Cómo me matriculo?", "s", cursor).contrato_http)
