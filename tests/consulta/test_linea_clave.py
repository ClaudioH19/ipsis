"""La línea clave (ADR 0013): se describe una fuente publicada, no se cambia qué se publica ni su orden."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from ipsis.aplicacion.registro_base import LiteralOffsetsVerifier
from ipsis.consulta.v2 import MotorV2
from ipsis.consulta.v2.linea_clave import MAX_LINEAS, SelectorLineaClave, elegir, tramos_de_linea
from ipsis.nucleo.esquemas import ChunkRecord, RetrievalCandidate, RetrievalSignals
from ipsis.servicio.api import RespuestaConsulta, respuesta_publica

PREGUNTA = "cuanto vale el portfolio"
TABLA = "Instrumento | Ponderación\nRúbrica del supervisor | 20%\nPortfolio de diagnóstico | 40%\nEntrevista técnica | 40%"
PALABRAS = ["portfolio", "rubrica", "entrevista", "instrumento", "diagnostico"]


class Codificador:
    """Un vector por línea: una dimensión por palabra conocida. Cuenta cuántas líneas codifica."""

    def __init__(self):
        self.codificadas = []

    def _vector(self, texto):
        bajo = texto.lower().replace("ó", "o").replace("ú", "u")
        v = np.array([float(p in bajo) for p in PALABRAS] + [0.01], dtype=np.float32)
        return v / np.linalg.norm(v)

    def codificar_documentos(self, textos):
        self.codificadas += list(textos)
        return np.stack([self._vector(t) for t in textos])

    def codificar_consultas(self, textos):
        return np.stack([self._vector(t) for t in textos])


def _candidato(cid, texto, rango=1):
    return RetrievalCandidate(chunk=ChunkRecord(chunk_id=cid, doc_id="reglamento", doc_titulo="Reglamento",
        version="1", texto_fuente=texto, texto_embedding=texto, offset_inicio=1000 * rango,
        offset_fin=1000 * rango + len(texto), seccion_path=["Prácticas", cid], tipo_contenido="parrafo"),
        signals=RetrievalSignals(fusion_rank=rango, fusion_score=.04))


class Recuperador:
    def __init__(self, candidatos, codificador=None):
        self.candidatos, self._codificador = candidatos, codificador

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

    @property
    def codificador(self):
        return self._codificador

    def vector_consulta(self, texto):
        return self._codificador.codificar_consultas([texto])[0]


def _motor(candidatos, presentacion=None, codificador="nuevo", **opciones):
    codificador = Codificador() if codificador == "nuevo" else codificador
    opciones = {**({"presentacion": presentacion} if presentacion is not None else {}), **opciones}
    recuperador = Recuperador(candidatos, codificador) if codificador is not None else Recuperador(candidatos)
    return MotorV2(retriever=recuperador, verificador=LiteralOffsetsVerifier(), opciones=opciones,
                   plantillas={"abstencion": {"generico": ["No hay evidencia."], "zona_gris_intro": ["Pasajes:"]}})


ENCENDIDA = {"linea_clave": True}
FUENTES = [_candidato("c1", TABLA, 1), _candidato("c2", "Un párrafo único sin saltos de línea.", 2)]


def test_tramos_de_linea_dan_offsets_sin_bordes_ni_lineas_vacias():
    texto = "  Uno dos  \n\n!!\nTres cuatro\r\n"
    tramos = tramos_de_linea(texto)
    assert [texto[a:b] for a, b in tramos] == ["Uno dos", "Tres cuatro"]


def test_elegir_pide_dos_lineas_y_un_margen():
    assert elegir([0.9], 0.0) is None
    assert elegir([0.5, 0.9, 0.4], 0.01) == (1, pytest.approx(0.4))
    assert elegir([0.5, 0.505], 0.01) is None


def test_el_selector_marca_la_linea_con_offsets_del_documento_y_cachea_vectores():
    codificador = Codificador()
    selector = SelectorLineaClave(codificador)
    vector = codificador.codificar_consultas([PREGUNTA])[0]
    sel = selector.seleccionar(vector, TABLA, base=5000, margen=0.01)
    assert sel["metodo"] == "denso"
    assert TABLA[sel["offset_inicio"] - 5000:sel["offset_fin"] - 5000] == "Portfolio de diagnóstico | 40%"
    antes = len(codificador.codificadas)
    assert selector.lineas_nuevas(TABLA) == 0
    selector.seleccionar(vector, TABLA, base=5000, margen=0.01)
    assert len(codificador.codificadas) == antes  # la segunda vez no codifica nada


def test_el_selector_no_marca_un_pasaje_de_una_linea_ni_uno_enorme():
    selector = SelectorLineaClave(Codificador())
    vector = selector.codificador.codificar_consultas([PREGUNTA])[0]
    assert selector.seleccionar(vector, "Una sola línea de texto", margen=0.0) is None
    assert selector.seleccionar(vector, "\n".join(f"línea número {i}" for i in range(MAX_LINEAS + 1)), margen=0.0) is None


def test_la_cache_es_acotada():
    codificador = Codificador()
    selector = SelectorLineaClave(codificador, capacidad=3)
    vector = codificador.codificar_consultas([PREGUNTA])[0]
    selector.seleccionar(vector, TABLA, margen=0.0)
    assert len(selector._vectores) == 3


def test_apagada_no_deja_ninguna_clave():
    resultado = _motor(FUENTES).consultar(PREGUNTA, "s")
    assert all("linea_clave" not in f for f in resultado.contrato_http["fragmentos"])
    assert "linea_clave" not in resultado.diagnostico
    assert all("key_line" not in f for f in respuesta_publica(resultado.contrato_http)["fragments"])


def test_encendida_marca_la_linea_literal_de_la_fuente_publicada():
    resultado = _motor(FUENTES, presentacion=ENCENDIDA).consultar(PREGUNTA, "s")
    fuente = resultado.contrato_http["fragmentos"][0]
    linea = fuente["linea_clave"]
    inicio = linea["offset_inicio"] - fuente["offset_inicio"]
    assert fuente["texto"][inicio:linea["offset_fin"] - fuente["offset_inicio"]] == "Portfolio de diagnóstico | 40%"
    assert "linea_clave" not in resultado.contrato_http["fragmentos"][1]  # una sola línea: nada que marcar
    assert resultado.diagnostico["linea_clave"]["marcadas"] == 1


def test_encenderla_no_cambia_ni_el_contenido_ni_el_orden():
    def publicado(resultado):
        return ([e.model_dump(mode="json") for e in resultado.evidencias],
                [{k: v for k, v in f.items() if k != "linea_clave"} for f in resultado.contrato_http["fragmentos"]],
                resultado.contrato_http.get("bloques"))

    apagado = _motor(FUENTES).consultar(PREGUNTA, "s")
    encendido = _motor(FUENTES, presentacion=ENCENDIDA).consultar(PREGUNTA, "s")
    assert publicado(encendido) == publicado(apagado)


def test_un_margen_inalcanzable_no_marca_nada():
    resultado = _motor(FUENTES, presentacion={**ENCENDIDA, "margen_linea_clave": 5.0}).consultar(PREGUNTA, "s")
    assert all("linea_clave" not in f for f in resultado.contrato_http["fragmentos"])


def test_sin_presupuesto_se_omite_y_se_avisa():
    resultado = _motor(FUENTES, presentacion=ENCENDIDA, presupuesto_consulta_ms=150).consultar(PREGUNTA, "s")
    assert "línea clave omitida por presupuesto" in resultado.diagnostico["advertencias"]
    assert all("linea_clave" not in f for f in resultado.contrato_http["fragmentos"])


def test_con_las_lineas_en_cache_no_hace_falta_presupuesto():
    motor = _motor(FUENTES, presentacion=ENCENDIDA)
    primera = motor.consultar_con_presupuesto(PREGUNTA, "a", deadline_ms=150)  # sin tiempo y sin caché: se omite
    assert all("linea_clave" not in f for f in primera.contrato_http["fragmentos"])
    motor.consultar(PREGUNTA, "b")  # con tiempo: llena la caché
    segunda = motor.consultar_con_presupuesto(PREGUNTA, "c", deadline_ms=150)
    assert "linea_clave" in segunda.contrato_http["fragmentos"][0]


def test_sin_codificador_denso_no_hace_nada():
    resultado = _motor(FUENTES, presentacion=ENCENDIDA, codificador=None).consultar(PREGUNTA, "s")
    assert all("linea_clave" not in f for f in resultado.contrato_http["fragmentos"])


def test_una_falla_del_codificador_no_tumba_la_consulta():
    class Roto(Codificador):
        def codificar_documentos(self, textos):
            raise RuntimeError("sin memoria")

    resultado = _motor(FUENTES, presentacion=ENCENDIDA, codificador=Roto()).consultar(PREGUNTA, "s")
    assert resultado.evidencias and "línea clave falló: RuntimeError" in resultado.diagnostico["advertencias"]


def test_la_api_publica_key_line():
    contrato = _motor(FUENTES, presentacion=ENCENDIDA).consultar(PREGUNTA, "s").contrato_http
    salida = respuesta_publica(contrato)
    linea = salida["fragments"][0]["key_line"]
    assert linea["method"] == "dense" and linea["offset_end"] > linea["offset_start"]
    assert RespuestaConsulta.model_validate(salida).fragments[0].key_line.offset_start == linea["offset_start"]
    assert "key_line" not in salida["fragments"][1]


def test_seguir_buscando_tambien_marca_las_fuentes_nuevas():
    candidatos = [_candidato(f"c{i}", TABLA, i + 1) for i in range(1, 8)]
    motor = _motor(candidatos, presentacion=ENCENDIDA, resultados_n=3)
    primera = motor.consultar(PREGUNTA, "s")
    segunda = motor.continuar(PREGUNTA, "s", primera.contrato_http["continuation"])
    assert segunda.contrato_http["fragmentos"] and all("linea_clave" in f for f in segunda.contrato_http["fragmentos"])
