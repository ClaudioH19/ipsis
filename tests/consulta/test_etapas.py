"""Pruebas de redacción, admisión, conversación y verificación de ``rag/consulta``.

Funciones puras, sin Qdrant ni modelos reales.
"""
from __future__ import annotations

from rag.consulta.admision import ConfiguracionAdmision, ControlAdmision
from rag.consulta.etapas.redaccion import redactar, redactar_zona_gris, construir_mensaje_abstencion
from rag.consulta.etapas.verificacion import verificar_fidelidad
from rag.consulta.etapas.conversacional import detectar_conversacional, respuesta_conversacional
from rag.consulta.etapas.politica import (
    separar_entidades_ausentes,
    verificar_premisa_textos,
)


def verificar_premisa(pregunta, fragmentos):
    return verificar_premisa_textos(pregunta, [f["texto"] for f in fragmentos])


# ---------------------------------------------------------------------------
# Admisión
# ---------------------------------------------------------------------------

def test_control_admision_admite_hasta_el_limite_y_luego_rechaza():
    control = ControlAdmision(ConfiguracionAdmision(concurrencia_maxima=2))
    assert control.intentar_admitir() is True
    assert control.intentar_admitir() is True
    assert control.intentar_admitir() is False
    control.liberar()
    assert control.intentar_admitir() is True


# ---------------------------------------------------------------------------
# Capa (b): premisa determinista
# ---------------------------------------------------------------------------

def test_verificar_premisa_entidad_respaldada_es_valida():
    fragmentos = [{"texto": "El artículo 8 define el mantenimiento preventivo."}]
    resultado = verificar_premisa("¿Qué establece el artículo 8?", fragmentos)
    assert resultado.premisa_valida is True
    assert resultado.entidades_ausentes == []


def test_verificar_premisa_entidad_no_respaldada():
    fragmentos = [{"texto": "El artículo 8 define el mantenimiento preventivo."}]
    resultado = verificar_premisa("¿Qué establece el artículo 9?", fragmentos)
    assert resultado.premisa_valida is False
    assert any(e["valor_norm"] == "articulo_9" for e in resultado.entidades_ausentes)


def test_verificar_premisa_sin_entidades_en_la_pregunta_es_valida_por_defecto():
    """Si la pregunta no menciona ninguna entidad cerrada, esta capa no
    tiene nada que objetar (no es lo mismo que "bien respaldada" -- de eso
    se encarga la zona gris, no esta capa)."""
    fragmentos = [{"texto": "Texto cualquiera sin relación aparente."}]
    resultado = verificar_premisa("¿Cómo funciona el proceso de evaluación en general?", fragmentos)
    assert resultado.premisa_valida is True


def test_verificar_premisa_articulo_no_respaldado():
    fragmentos = [{"texto": "El artículo 5 regula los plazos de inscripción."}]
    resultado = verificar_premisa("¿Qué dice el artículo 40 sobre las excepciones?", fragmentos)
    assert resultado.premisa_valida is False
    assert any("articulo_40" == e["valor_norm"] for e in resultado.entidades_ausentes)


# ---------------------------------------------------------------------------
# Mensajes de abstención SIEMPRE son texto listo para mostrar (nunca vacíos)
# ---------------------------------------------------------------------------

def test_construir_mensaje_abstencion_generico_no_esta_vacio():
    msg = construir_mensaje_abstencion("fuera_dominio")
    assert isinstance(msg, str) and len(msg) > 0


def test_construir_mensaje_abstencion_premisa_incluye_la_entidad_literal():
    msg = construir_mensaje_abstencion("premisa", entidad_texto="artículo 99")
    assert "artículo 99" in msg


# ---------------------------------------------------------------------------
# Redacción (plan único + zona gris) y guardia
# ---------------------------------------------------------------------------

def _fragmento(texto, doc="Manual X100", seccion=("Capítulo 1",), excepcion=False,
               condicion=False, chunk_id="c1", score=1.0):
    return {"doc_titulo": doc, "seccion_path": list(seccion), "texto": texto,
            "tiene_excepcion": excepcion, "tiene_condicion": condicion,
            "chunk_id": chunk_id, "score": score}


def test_redactar_texto_literal_con_cita():
    """El texto del documento se copia literal y la cita nombra el documento."""
    frag = _fragmento("El plazo es de quince días hábiles.")
    texto = redactar([frag])
    assert "El plazo es de quince días hábiles." in texto
    assert "Manual X100" in texto


def test_estilo_de_cita_en_el_texto(monkeypatch):
    """`redaccion.cita_en_texto` decide cuánto se repite la cita DENTRO de la
    prosa. La ruta de sección solo aparece en el estilo "completa"; en los
    tres estilos la cita exacta sigue viajando en el campo `fragmentos` de
    la respuesta HTTP, que este test no toca."""
    import rag.consulta.etapas.redaccion as pipeline

    frag = _fragmento("El plazo es de quince días hábiles.")

    def con_estilo(estilo, apertura=False):
        monkeypatch.setattr(pipeline, "config_redaccion", None, raising=False)
        monkeypatch.setattr(
            "rag.configuracion.carga.config_redaccion",
            lambda *a, **k: {"cita_en_texto": estilo, "incluir_apertura": apertura,
                             "max_fragmentos_en_respuesta": 2, "score_relativo_minimo": 0.6},
        )
        return redactar([frag])

    completa = con_estilo("completa")
    assert "Manual X100" in completa and "Capítulo 1" in completa

    breve = con_estilo("breve")
    assert "Manual X100" in breve and "Capítulo 1" not in breve

    ninguna = con_estilo("ninguna")
    assert "Fuente" not in ninguna
    assert "El plazo es de quince días hábiles." in ninguna


def test_conector_entre_fragmentos_no_repite_la_misma_frase(monkeypatch):
    """Dos fragmentos que se suman al primero no deben abrir los dos con el
    mismo conector: `_elegir_variante` desplaza al siguiente candidato."""
    monkeypatch.setattr(
        "rag.configuracion.carga.config_redaccion",
        lambda *a, **k: {"cita_en_texto": "ninguna", "incluir_apertura": False,
                         "max_fragmentos_en_respuesta": 3, "score_relativo_minimo": 0.0},
    )
    frags = [_fragmento("Primero.", chunk_id="a"),
             _fragmento("Segundo.", chunk_id="b"),
             _fragmento("Tercero.", chunk_id="c")]
    texto = redactar(frags)
    from rag.consulta.etapas.redaccion import _cargar_plantillas
    usados = [c for c in _cargar_plantillas()["conectores"]["complemento"] if c in texto]
    assert len(usados) == 2, f"se esperaban dos conectores distintos, hubo {usados}"


def test_ningun_conector_es_subordinante(monkeypatch):
    """Regresión de un defecto real: los conectores eran subordinantes
    ("Siempre que", "Salvo que") y producían frases rotas del tipo
    "Siempre que, El equipo X100 tiene..." al anteponerlos a una
    cita literal. Ahora todos cierran en dos puntos."""
    from rag.consulta.etapas.redaccion import _cargar_plantillas
    conectores = _cargar_plantillas()["conectores"]
    for categoria in ("apertura", "complemento", "condicion", "excepcion"):
        for frase in conectores[categoria]:
            assert frase.rstrip().endswith(":"), (categoria, frase)


def test_max_fragmentos_y_score_relativo_acotan_la_prosa(monkeypatch):
    """Un fragmento posterior al primero entra solo si su score alcanza la
    fracción configurada, y con un tope duro de cuántos caben."""
    monkeypatch.setattr(
        "rag.configuracion.carga.config_redaccion",
        lambda *a, **k: {"cita_en_texto": "ninguna", "incluir_apertura": False,
                         "max_fragmentos_en_respuesta": 3, "score_relativo_minimo": 0.6},
    )
    frags = [_fragmento("Pertinente.", chunk_id="a", score=1.0),
             _fragmento("Algo pertinente.", chunk_id="b", score=0.8),
             _fragmento("Ruido de otra seccion.", chunk_id="c", score=0.2)]
    texto = redactar(frags)
    assert "Pertinente." in texto and "Algo pertinente." in texto
    assert "Ruido de otra seccion." not in texto

    monkeypatch.setattr(
        "rag.configuracion.carga.config_redaccion",
        lambda *a, **k: {"cita_en_texto": "ninguna", "incluir_apertura": False,
                         "max_fragmentos_en_respuesta": 1, "score_relativo_minimo": 0.0},
    )
    solo_uno = redactar(frags)
    assert "Pertinente." in solo_uno and "Algo pertinente." not in solo_uno


def test_redactar_zona_gris_incluye_la_frase_de_encabezado_fija():
    frag = _fragmento("Texto de contexto general sobre el tema.")
    texto = redactar_zona_gris([frag])
    assert texto.startswith("No encontré una respuesta directa")
    assert "Texto de contexto general sobre el tema." in texto


def test_verificar_fidelidad_pasa_si_la_respuesta_es_literal():
    frag = _fragmento("El plazo es de quince días hábiles según el artículo 5.")
    respuesta = redactar([frag])
    resultado = verificar_fidelidad(respuesta, [frag])
    assert resultado.fiel is True


def test_verificar_fidelidad_falla_si_aparece_una_entidad_no_respaldada():
    frag = _fragmento("El plazo es de quince días hábiles.")
    respuesta_inventada = "El plazo es de treinta días hábiles."  # "30" no está en el fragmento
    resultado = verificar_fidelidad(respuesta_inventada, [frag])
    assert resultado.fiel is False


# ---------------------------------------------------------------------------
# Etapa C, punto 1: separar entidades ausentes del top-k en "existe en el
# corpus" (candidata a recuperación dirigida) vs "genuinamente ausente".
# ---------------------------------------------------------------------------

def test_separar_entidades_ausentes_distingue_corpus_de_genuinamente_ausente():
    ausentes = [
        {"tipo": "practica", "texto": "Práctica II", "valor_norm": "practica_2"},
        {"tipo": "practica", "texto": "Práctica III", "valor_norm": "practica_3"},
    ]
    inventario = {"practica_1", "practica_2"}  # la III no existe en el corpus
    en_corpus, genuinamente_ausentes = separar_entidades_ausentes(ausentes, inventario)
    assert [e["valor_norm"] for e in en_corpus] == ["practica_2"]
    assert [e["valor_norm"] for e in genuinamente_ausentes] == ["practica_3"]


def test_separar_entidades_ausentes_todas_en_corpus():
    ausentes = [{"tipo": "nota", "texto": "3,9", "valor_norm": "3.9"}]
    en_corpus, genuinamente_ausentes = separar_entidades_ausentes(ausentes, {"3.9"})
    assert len(en_corpus) == 1 and genuinamente_ausentes == []


# ---------------------------------------------------------------------------
# Etapa C, punto 4: estado "conversacional" (saludos, sin tocar Qdrant).
# ---------------------------------------------------------------------------

def test_detectar_conversacional_saludo():
    assert detectar_conversacional("hola") == "saludo"
    assert detectar_conversacional("Buenos días, ¿cómo estás?") == "saludo"


def test_detectar_conversacional_agradecimiento():
    assert detectar_conversacional("muchas gracias por la ayuda") == "agradecimiento"


def test_detectar_conversacional_despedida():
    assert detectar_conversacional("chao, nos vemos") == "despedida"


def test_detectar_conversacional_capacidad():
    assert detectar_conversacional("¿qué puedes hacer?") == "capacidad"


def test_detectar_conversacional_pregunta_del_corpus_no_matchea():
    """Una pregunta documental nunca debe caer en conversacional,
    aunque comparta alguna palabra suelta."""
    assert detectar_conversacional("¿Cuánto dura la garantía del equipo X100?") is None
    assert detectar_conversacional("¿Qué pasa si saco un 3,9?") is None


def test_respuesta_conversacional_no_esta_vacia_para_cada_categoria():
    for categoria in ("saludo", "agradecimiento", "despedida", "capacidad"):
        texto = respuesta_conversacional(categoria)
        assert isinstance(texto, str) and len(texto) > 0


def test_respuesta_conversacional_varia_entre_preguntas_pero_es_determinista():
    """Varias formulaciones fijas por categoría, elegidas con un hash de la
    pregunta: la MISMA pregunta devuelve siempre el mismo texto (testeable),
    pero distintos saludos no contestan todos lo mismo (suena menos a
    máquina). Nada de esto lo redacta un modelo."""
    assert respuesta_conversacional("saludo", "hola") == respuesta_conversacional("saludo", "hola")
    variantes = {respuesta_conversacional("saludo", p)
                 for p in ("hola", "buenas", "qué tal", "buenos días", "hey", "buenas tardes")}
    assert len(variantes) > 1, "todos los saludos contestan exactamente lo mismo"


def test_respuesta_conversacional_sin_pregunta_sigue_funcionando():
    """La firma acepta la pregunta como opcional: /config pide el saludo sin
    tener ninguna pregunta que pasarle."""
    texto = respuesta_conversacional("saludo")
    assert texto and isinstance(texto, str)


def test_zona_gris_no_apila_dos_encabezados():
    """Regresión de un defecto real: el estado `relacionado` ya trae su
    encabezado fijo ("No encontré una respuesta directa..."), así que la
    frase de apertura no debe agregarse encima. Antes producía "No encontré
    una respuesta directa. Esto es lo que dicen los documentos sobre el
    tema: Encontré esto en el documento:"."""
    from rag.consulta.etapas.redaccion import _cargar_plantillas
    frag = _fragmento("Texto pertinente sobre el tema.")
    texto = redactar_zona_gris([frag])
    for apertura in _cargar_plantillas()["conectores"]["apertura"]:
        assert apertura not in texto, f"la apertura {apertura!r} se apiló sobre el encabezado"


def test_contraccion_castellana_en_los_textos_conversacionales():
    """Regresión de un defecto real: `descripcion_dominio` la escribe el
    usuario y puede empezar con artículo ("el manual de..."), así que
    una plantilla que diga "de {descripcion_dominio}" producía "de el
    manual"."""
    from rag.consulta.etapas.redaccion import _cargar_plantillas
    respuestas = _cargar_plantillas()["conversacional"]["respuestas"]
    for categoria, valor in respuestas.items():
        textos = [valor] if isinstance(valor, str) else valor
        for t in textos:
            assert " de el " not in t, (categoria, t)
            assert " a el " not in t, (categoria, t)
