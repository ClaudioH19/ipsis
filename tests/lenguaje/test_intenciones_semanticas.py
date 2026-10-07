from types import SimpleNamespace
from pathlib import Path
import json

import numpy as np
import pytest
import yaml

from ipsis.lenguaje.intenciones import RespaldoIntenciones, construir_respaldo, tiene_tema
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.consultas import comprender_consulta, plano
from ipsis.nucleo.esquemas import QueryAnalysis, SenalesRecuperacion


class Codificador:
    spec = SimpleNamespace(id_hf="modelo-prueba")

    def __init__(self):
        self.llamadas = []

    def codificar_consultas(self, textos):
        self.llamadas.append(list(textos))
        return np.array([[3., 0.], [2., 0.], [0., 4.]])


def _paquete():
    return SimpleNamespace(intenciones={
        "inicio": SimpleNamespace(ejemplos=["primer inicio", "segundo inicio"]),
        "fin": SimpleNamespace(ejemplos=["final"]),
    }, respaldo_intencion={"modelo-prueba": SimpleNamespace(similitud=0.8, margen=0.1)})


def test_codifica_una_vez_y_margen_compara_intenciones_distintas():
    codificador = Codificador()
    respaldo = RespaldoIntenciones(_paquete(), codificador, similitud=0.8, margen=0.1)
    for _ in range(3):
        p = respaldo.predecir([5., 0.])
        assert p.nombre == "inicio" and p.margen == pytest.approx(1.0)
        assert p.similitud == pytest.approx(1.0)
    assert len(codificador.llamadas) == 1


def test_rechaza_ambiguedad_y_respeta_ambos_umbrales_estrictos():
    respaldo = RespaldoIntenciones(_paquete(), Codificador(), similitud=0.8, margen=0.1)
    assert respaldo.predecir([1., 1.]).nombre is None
    respaldo.similitud = 1.0
    assert respaldo.predecir([1., 0.]).nombre is None


def test_habilitadas_no_elimina_competidores_ni_infla_el_margen():
    respaldo = RespaldoIntenciones(_paquete(), Codificador(), similitud=0.5, margen=0.1, habilitadas=["inicio"])
    assert respaldo.predecir([0., 1.]).nombre is None
    assert respaldo.predecir([1., 1.]).nombre is None
    assert respaldo.predecir([1., 0.]).nombre == "inicio"
    respaldo.similitud, respaldo.margen = 0.8, 1.0
    assert respaldo.predecir([1., 0.]).nombre is None


@pytest.mark.parametrize("vector", [[0., 0.], [float("nan"), 1.], [1., 2., 3.]])
def test_vectores_invalidos_no_producen_intencion(vector):
    respaldo = RespaldoIntenciones(_paquete(), Codificador(), similitud=0.8, margen=0.1)
    with pytest.raises(ValueError, match="Vector de consulta"):
        respaldo.predecir(vector)


def test_sin_denso_bm25_o_modelo_sin_umbrales_no_carga_ejemplos():
    codificador = Codificador()
    for retriever in (None, SimpleNamespace(modo="dispersa", codificador=codificador),
                      SimpleNamespace(modo="hibrida", codificador=SimpleNamespace(spec=SimpleNamespace(id_hf="otro")))):
        assert construir_respaldo(_paquete(), retriever) is None
    assert codificador.llamadas == []


def test_retriever_codifica_una_vez_para_confianza_y_respaldo(monkeypatch):
    from ipsis.consulta.etapas.recuperacion import RetrieverQdrant

    codificador = Codificador()
    retriever = RetrieverQdrant(SimpleNamespace(codificador=codificador))
    monkeypatch.setattr("ipsis.consulta.etapas.recuperacion.buscar",
                        lambda *a, **k: SimpleNamespace(scores=[0.9, 0.8], payloads=[]))
    consulta = QueryAnalysis(pregunta_original="pregunta", pregunta_normalizada="pregunta")
    retriever.estimar_confianza(consulta)
    vector = retriever.vector_consulta("pregunta")
    retriever.recuperar(consulta, 3)
    assert vector is retriever.vector_consulta("pregunta")
    assert codificador.llamadas == [["pregunta"]]


def test_patrones_tienen_prioridad_y_similitud_no_quita_palabras_de_foco():
    paquete = cargar_paquete("es")
    patron = QueryAnalysis(pregunta_original="¿Cuándo empieza la inscripción?", pregunta_normalizada="cuando empieza la inscripcion", intencion="fin")
    assert comprender_consulta(patron, paquete).intencion == "inicio"
    semantica = QueryAnalysis(pregunta_original="Se abrió la matrícula, ¿desde qué fecha rige?", pregunta_normalizada="matricula", intencion="inicio")
    comprension = comprender_consulta(semantica, paquete)
    assert comprension.pistas and not comprension.terminos_relacion


def test_respaldo_no_actua_con_solo_unidades_o_tema_ausente():
    from ipsis.indice.estadisticas import EstadisticasLexicas

    paquete = cargar_paquete("es")
    est = EstadisticasLexicas.construir(["El permiso dura diez días. La biblioteca abre el lunes."], paquete)
    assert not tiene_tema("¿Cuántos días son?", paquete, est)
    assert not tiene_tema("¿Cuál es la capital de Mongolia?", paquete, est)
    assert tiene_tema("¿Cuántos días dura el permiso?", paquete, est)


def test_diagnostico_puntua_con_las_mismas_pistas_semanticas_de_la_seleccion():
    from ipsis.aplicacion.consulta import _ranking_diagnostico
    from ipsis.indice.estadisticas import EstadisticasLexicas

    paquete = cargar_paquete("es")
    texto = "El permiso de visita se tramita en ventanilla. Primero presente el formulario del permiso de visita."
    est = EstadisticasLexicas.construir([texto], paquete)
    motor = SimpleNamespace(idioma=paquete, retriever=SimpleNamespace(
        textos_diagnostico=lambda ids: {"c": texto}, estadisticas_lexico=lambda: est))
    _, oraciones = _ranking_diagnostico(motor, "permiso de visita", {
        "candidatos": [{"chunk_id": "c"}],
        "intencion": {"nombre": "procedimiento", "origen": "similitud", "aceptada": True},
    })
    assert oraciones[0]["texto"].startswith("Primero")


def test_confianza_reutiliza_vector_y_patron_no_llama_al_respaldo():
    from ipsis.consulta.contexto import ContextoConsulta
    from ipsis.consulta.etapas.recuperacion import EtapaSenales
    from ipsis.indice.estadisticas import EstadisticasLexicas

    paquete = cargar_paquete("es")
    est = EstadisticasLexicas.construir(["La matrícula abre después de aprobar el permiso."], paquete)
    vector = [1., 0.]
    llamadas = []
    respaldo = SimpleNamespace(predecir=lambda v: llamadas.append(v) or SimpleNamespace(
        nombre="inicio", candidato="inicio", similitud=0.95, margen=0.1, ejemplo="ejemplo"))
    retriever = SimpleNamespace(estimar_confianza=lambda *a: SenalesRecuperacion(confianza_top1=0.9, margen_top1_top2=0.1),
                               vector_consulta=lambda q: vector, estadisticas_lexico=lambda: est)
    motor = SimpleNamespace(retriever=retriever, top_k=3, idioma=paquete, respaldo_intenciones=respaldo,
                            _confianza=lambda s: {})
    ctx = ContextoConsulta("fecha de matrícula", "s", consulta=QueryAnalysis(pregunta_original="fecha de matrícula", pregunta_normalizada="fecha de matricula"))
    EtapaSenales(motor).ejecutar(ctx)
    assert ctx.consulta.intencion == "inicio" and llamadas == [vector]
    assert ctx.diagnostico["intencion"]["origen"] == "similitud"
    llamadas.clear()
    ctx.consulta = ctx.consulta.model_copy(update={"intencion": "fin"})
    EtapaSenales(motor).ejecutar(ctx)
    assert llamadas == [] and ctx.consulta.intencion == "fin"


def test_ejemplos_y_etiquetas_cubren_tres_idiomas_sin_copiar_bancos():
    raiz = Path(__file__).resolve().parents[2]
    etiquetas = yaml.safe_load((raiz / "tests/datos/banco_consultas/intenciones.yaml").read_text(encoding="utf-8"))
    for idioma in ("es", "en", "pt"):
        paquete = cargar_paquete(idioma)
        casos = [json.loads(l) for l in (raiz / f"tests/datos/banco_consultas/{idioma}/banco.jsonl").read_text(encoding="utf-8").splitlines()]
        assert {c["id"].split("-", 1)[1] for c in casos} == set(etiquetas)
        assert all(e is None or e in paquete.intenciones for e in etiquetas.values())
        preguntas = {plano(c["pregunta"]) for c in casos}
        for banco in ("banco_universal", "banco_conversaciones"):
            ruta = raiz / f"tests/datos/{banco}/{idioma}"
            if banco == "banco_universal":
                preguntas.update(plano(json.loads(l)["pregunta"]) for l in (ruta / "banco.jsonl").read_text(encoding="utf-8").splitlines())
            else:
                preguntas.update(plano(t["pregunta"]) for c in yaml.safe_load((ruta / "conversaciones.yaml").read_text(encoding="utf-8")) for t in c["turnos"])
        for intencion in paquete.intenciones.values():
            assert 5 <= len(intencion.ejemplos) <= 10
            assert len({plano(e) for e in intencion.ejemplos}) == len(intencion.ejemplos)
            assert not preguntas.intersection(plano(e) for e in intencion.ejemplos)
