"""Tests de ``ipsis/consulta/etapas/seleccion.py`` (evita respuestas demasiado
largas). Funciones puras, sin modelos ni red: la puntuación por ``s_lex``
cubre todo el algoritmo de selección y expansión."""
from __future__ import annotations

from ipsis.consulta.etapas.seleccion import (
    dividir_en_unidades,
    seleccionar_texto_pertinente,
    recortar_payload_a_texto_pertinente,
    ordenar_por_pertinencia_global,
)


def test_dividir_en_unidades_offsets_exactos_texto_narrativo():
    texto = "Primera oracion aqui. Segunda oracion distinta. Tercera y ultima oracion."
    unidades = dividir_en_unidades(texto)
    assert len(unidades) == 3
    for u in unidades:
        assert texto[u.offset_inicio:u.offset_fin] == u.texto
        assert not u.es_fila_tabla


def test_dividir_en_unidades_no_parte_filas_de_tabla():
    texto = "Semana | Actividad | Responsable\n1 | Induccion | AEP\n2 | Terreno | Supervisor"
    unidades = dividir_en_unidades(texto)
    assert len(unidades) == 3
    assert all(u.es_fila_tabla for u in unidades)
    for u in unidades:
        assert texto[u.offset_inicio:u.offset_fin] == u.texto
        assert " | " in u.texto


def test_dividir_en_unidades_offsets_exactos_con_filas_y_narrativo_mezclado():
    texto = "Introduccion del capitulo.\nSemana | Actividad\n1 | Induccion\nCierre del capitulo aqui."
    unidades = dividir_en_unidades(texto)
    for u in unidades:
        assert texto[u.offset_inicio:u.offset_fin] == u.texto


def test_seleccionar_texto_pertinente_devuelve_completo_si_ya_entra_en_el_limite():
    texto = "Una oracion corta."
    resultado = seleccionar_texto_pertinente("cualquier pregunta", texto, offset_chunk_inicio=100,
                                              limite_caracteres=1000)
    assert resultado.texto == texto
    assert resultado.recortado is False
    assert resultado.offset_inicio == 100
    assert resultado.offset_fin == 100 + len(texto)


def test_seleccionar_texto_pertinente_elige_la_oracion_mas_relevante():
    """Caso real (parafraseado): el chunk trae
    varias oraciones, solo una responde la pregunta directamente -- debe
    quedar dentro del recorte."""
    texto = (
        "La bitacora se organiza por semanas relativas desde el inicio de la practica. "
        "La garantía del equipo X100 dura dieciocho meses desde la compra. "
        "Cada entrada debe incluir fecha, actividad realizada y horas dedicadas. "
        "El supervisor revisa la bitacora de forma periodica durante el proceso."
    )
    resultado = seleccionar_texto_pertinente(
        "¿Cuánto dura la garantía del equipo X100?", texto, offset_chunk_inicio=0,
        limite_caracteres=90,
    )
    assert "dieciocho meses" in resultado.texto
    assert len(resultado.texto) <= 200  # se expande con contexto, pero no explota el límite arbitrariamente
    assert resultado.recortado is True


def test_seleccionar_texto_pertinente_nunca_excede_mucho_el_limite():
    texto = " ".join([f"Esta es la oracion numero {i} del texto de prueba." for i in range(30)])
    resultado = seleccionar_texto_pertinente("oracion numero quince", texto, 0, limite_caracteres=100)
    # el algoritmo solo agrega una unidad completa si CABE dentro del límite;
    # la unidad ancla sola puede superarlo levemente si ninguna cabe, pero
    # nunca debe expandirse de largo sin control.
    assert len(resultado.texto) <= 150


def test_seleccionar_texto_pertinente_offsets_son_substring_exacto_del_chunk():
    texto = (
        "Primer párrafo sobre requisitos generales del equipo. "
        "El plazo para inscribir la practica es de quince dias habiles antes del inicio. "
        "Segundo parrafo sobre evaluacion y notas finales del proceso completo."
    )
    resultado = seleccionar_texto_pertinente("¿Cuál es el plazo para inscribir la práctica?", texto, 500,
                                              limite_caracteres=95)
    # offset_inicio incluye el desplazamiento del chunk (500); se resta para
    # comparar contra el texto local.
    ini_local = resultado.offset_inicio - 500
    fin_local = resultado.offset_fin - 500
    assert texto[ini_local:fin_local] == resultado.texto


def test_ordenar_por_pertinencia_global_prioriza_respuesta_directa():
    """El fragmento con mejor score de recuperación puede ser lateral,
    mientras otro contiene la oración que responde directamente.
    Después de reordenar por pertinencia de la oración ancla, el segundo
    debe quedar primero."""
    pregunta = "¿Cuánto dura la garantía del equipo X100?"
    payload_lateral = {
        "chunk_id": "manual__c0010", "doc_titulo": "Manual X100", "seccion_path": ["Componentes"],
        "version": "1", "tiene_excepcion": False, "tiene_condicion": False,
        "texto": "Los capítulos 3 y 4 describen los componentes internos del equipo.",
        "offset_inicio": 0, "offset_fin": 68,
    }
    payload_directo = {
        "chunk_id": "manual__c0020", "doc_titulo": "Manual X100", "seccion_path": ["Garantía"],
        "version": "1", "tiene_excepcion": False, "tiene_condicion": False,
        "texto": "La garantía del equipo X100 dura dieciocho meses desde la compra.",
        "offset_inicio": 100, "offset_fin": 187,
    }
    # simula: el fragmento "lateral" llegó primero por score de recuperación
    recortados = [
        recortar_payload_a_texto_pertinente(payload_lateral, pregunta, limite_caracteres=500),
        recortar_payload_a_texto_pertinente(payload_directo, pregunta, limite_caracteres=500),
    ]
    scores_recuperacion = [0.90, 0.80]  # el lateral tenía MEJOR score de recuperación

    ordenados, scores_ordenados = ordenar_por_pertinencia_global(recortados, scores_recuperacion)

    assert ordenados[0]["chunk_id"] == "manual__c0020"  # el directo queda primero
    assert "dieciocho meses" in ordenados[0]["texto"]
    assert scores_ordenados[0] == 0.80  # el score de RECUPERACIÓN real viaja con su fragmento, no se recalcula


def test_ordenar_por_pertinencia_global_no_pierde_fragmentos():
    payloads = [
        {"chunk_id": f"c{i}", "doc_titulo": "D", "seccion_path": [], "version": "1",
         "tiene_excepcion": False, "tiene_condicion": False, "texto": f"Texto {i}.",
         "offset_inicio": 0, "offset_fin": 10, "_score_ancla": float(i)}
        for i in range(4)
    ]
    ordenados, scores = ordenar_por_pertinencia_global(payloads, [1.0, 2.0, 3.0, 4.0])
    assert {p["chunk_id"] for p in ordenados} == {"c0", "c1", "c2", "c3"}
    assert [p["chunk_id"] for p in ordenados] == ["c3", "c2", "c1", "c0"]  # score_ancla descendente
    assert scores == [4.0, 3.0, 2.0, 1.0]  # los scores de recuperación viajan alineados


def test_seleccionar_texto_pertinente_prioriza_oracion_con_entidad_literal():
    """Caso real: "3,9" tokeniza a fragmentos de 1
    carácter para el solapamiento léxico (ambos números son < 4 caracteres,
    el mínimo de ipsis/lenguaje/texto.py::palabras_contenido), así que el score de
    similitud NUNCA prioriza de forma confiable la oración con "3,9" -- hace
    falta la entidad exacta."""
    texto = (
        "La calificación final se expresa en la escala de 1,0 a 7,0 para todos los estudiantes. "
        "Si uno o más instrumentos obtienen nota inferior a 4,0, el estudiante reprobará la práctica con nota final 3,9. "
        "El AEP registra la calificación en el sistema institucional correspondiente."
    )
    entidades = [{"tipo": "nota", "texto": "3,9", "valor_norm": "3.9"}]
    resultado = seleccionar_texto_pertinente(
        "¿Qué pasa si saco un 3,9?", texto, offset_chunk_inicio=0, limite_caracteres=100,
        entidades_pregunta=entidades,
    )
    assert resultado.tiene_entidad_pregunta is True
    assert resultado.texto.startswith("Si uno o más instrumentos obtienen nota inferior a 4,0")
    assert "3,9" in resultado.texto.split(".")[0] + "."  # la entidad está en la PRIMERA oración


def test_seleccionar_texto_pertinente_sin_entidades_pregunta_usa_score():
    texto = "Primera oracion irrelevante. Segunda oracion sobre bitacora y supervisores del proceso."
    resultado = seleccionar_texto_pertinente(
        "¿bitácora supervisor?", texto, offset_chunk_inicio=0, limite_caracteres=40,
        entidades_pregunta=[],
    )
    assert resultado.tiene_entidad_pregunta is False


def test_ordenar_por_pertinencia_global_prioriza_fragmento_con_entidad_sobre_score_alto():
    """Un fragmento con score de recuperación MÁS ALTO
    pero SIN la entidad literal debe quedar DESPUÉS del fragmento que sí la
    contiene, aunque su propio score_ancla sea más bajo."""
    con_entidad = {"chunk_id": "c1", "_score_ancla": 0.1, "_tiene_entidad_pregunta": True}
    sin_entidad_score_alto = {"chunk_id": "c2", "_score_ancla": 0.9, "_tiene_entidad_pregunta": False}
    ordenados, _scores = ordenar_por_pertinencia_global(
        [sin_entidad_score_alto, con_entidad], [0.95, 0.10],
    )
    assert ordenados[0]["chunk_id"] == "c1"


def test_recortar_payload_a_texto_pertinente_conserva_el_resto_de_campos():
    payload = {
        "chunk_id": "manual__c0001",
        "doc_titulo": "Manual del Equipo X100",
        "seccion_path": ["Capítulo 3", "Plazos"],
        "version": "3.0",
        "tiene_excepcion": True,
        "tiene_condicion": False,
        "texto": "Primera oracion. Segunda oracion mas relevante sobre plazos. Tercera oracion final.",
        "offset_inicio": 1000,
        "offset_fin": 1000 + len("Primera oracion. Segunda oracion mas relevante sobre plazos. Tercera oracion final."),
    }
    nuevo = recortar_payload_a_texto_pertinente(payload, "plazos", limite_caracteres=40)
    assert nuevo["doc_titulo"] == payload["doc_titulo"]
    assert nuevo["seccion_path"] == payload["seccion_path"]
    assert nuevo["tiene_excepcion"] is True
    assert nuevo["chunk_id"] == payload["chunk_id"]
    assert nuevo["texto"] != payload["texto"]  # sí se recortó
    assert nuevo["texto"] in payload["texto"]  # pero es substring literal
    assert payload["texto"][nuevo["offset_inicio"] - 1000:nuevo["offset_fin"] - 1000] == nuevo["texto"]


def test_la_oracion_ancla_va_primera_y_el_contexto_solo_despues():
    """Con contexto a la izquierda, otra cifra («5 días») podía parecer la respuesta."""
    texto = ("La empresa responde dentro de 5 días hábiles. "
             "El reembolso se paga en un plazo de 10 días hábiles. "
             "Se transfiere a la cuenta registrada.")
    resultado = seleccionar_texto_pertinente("¿En cuántos días hábiles se paga el reembolso?", texto,
                                              offset_chunk_inicio=0, limite_caracteres=90)
    assert resultado.texto.startswith("El reembolso se paga")
    assert "5 días" not in resultado.texto
    assert texto[resultado.offset_inicio:resultado.offset_fin] == resultado.texto


def test_ventana_centrada_para_el_lector_incluye_contexto_previo():
    texto = ("Artículo 3. La empresa responde dentro de 5 días hábiles. "
             "Artículo 4. Se cobra un recargo del 15% sobre la tarifa de visita.")
    pregunta = "¿Qué recargo se cobra?"
    mostrada = seleccionar_texto_pertinente(pregunta, texto, 0, limite_caracteres=200)
    lector = seleccionar_texto_pertinente(pregunta, texto, 0, limite_caracteres=200, centrada=True)
    assert mostrada.texto.startswith("Artículo 4. Se cobra un recargo")  # el rótulo va con su oración
    assert lector.texto == texto


def test_lo_que_se_muestra_no_corta_la_salvedad_siguiente():
    """Si la oración que sigue a la respuesta es una excepción y no cabe por
    poco, entra igual: mostrar «se reembolsa en 30 días» sin «salvo que…» engaña."""
    respuesta = "El cliente puede pedir el reembolso dentro de 30 días corridos desde la compra."
    salvedad = "Salvo que el equipo ya haya sido instalado por el servicio técnico."
    texto = f"{respuesta} {salvedad} El horario de atención es de lunes a viernes."
    pregunta = "¿En cuántos días puedo pedir el reembolso?"
    mostrado = seleccionar_texto_pertinente(pregunta, texto, 0, limite_caracteres=len(respuesta) + 20)
    assert mostrado.texto == f"{respuesta} {salvedad}"
    assert mostrado.texto == texto[mostrado.offset_inicio:mostrado.offset_fin]  # sigue siendo literal
    # Para el lector QA no cambia nada, y una oración común no se cuela.
    qa = seleccionar_texto_pertinente(pregunta, texto, 0, limite_caracteres=len(respuesta) + 20, centrada=True)
    assert qa.texto == respuesta
    comun = f"{respuesta} El equipo se entrega con su manual impreso y su garantía."
    assert seleccionar_texto_pertinente(pregunta, comun, 0, limite_caracteres=len(respuesta) + 20).texto == respuesta


def test_si_el_chunk_cruza_de_seccion_el_tramo_se_queda_en_la_del_ancla():
    """Se busca por chunk, pero se muestra y se cita por sección."""
    garantia = "La garantía dura dos años desde la compra."
    titulo = "Mantenimiento"
    mantenimiento = "Descalcifique la cafetera cada tres meses."
    texto = f"{garantia}\n{titulo}\n{mantenimiento}"
    secciones = [(0, len(garantia), ["Garantía"]),
                 (len(garantia) + len(titulo) + 2, len(texto), ["Mantenimiento"])]
    r = seleccionar_texto_pertinente("¿Cada cuánto se descalcifica la cafetera?", texto, 1000, 500,
                                     secciones=secciones)
    assert r.texto == mantenimiento and r.seccion_path == ["Mantenimiento"]
    assert r.offset_inicio == 1000 + texto.index(mantenimiento)
    r = seleccionar_texto_pertinente("¿Cuánto dura la garantía?", texto, 1000, 500, secciones=secciones)
    assert r.texto == garantia and r.seccion_path == ["Garantía"]  # no arrastra el título ni la otra sección


def test_un_titulo_no_ancla_la_respuesta_aunque_puntue_mas():
    """«6.3 Procedimiento de Compra» calza mejor con la pregunta que la oración, pero no responde."""
    previa = "El formulario se envía al Departamento de Compras."
    titulo = "6.3 Procedimiento de Compra"
    respuesta = "Una vez aprobado el formulario, se realizará la compra."
    texto = f"{previa}\n{titulo}\n{respuesta}"
    secciones = [(0, len(previa), ["6.2 Formulario"]),
                 (len(previa) + len(titulo) + 2, len(texto), ["6.3 Procedimiento de Compra"])]
    r = seleccionar_texto_pertinente("¿cuál es el procedimiento de compra?", texto, 0, 500, secciones=secciones)
    assert titulo not in r.texto.split("\n")[0]


def test_dos_chunks_solapados_no_repiten_el_mismo_tramo():
    from ipsis.consulta.etapas.seleccion import quitar_tramos_repetidos

    a = {"doc_id": "d", "offset_inicio": 10, "offset_fin": 50, "texto": "x" * 40}
    b = {"doc_id": "d", "offset_inicio": 10, "offset_fin": 50, "texto": "x" * 40}  # el mismo, de otro chunk
    c = {"doc_id": "d", "offset_inicio": 60, "offset_fin": 90, "texto": "y" * 30}
    assert quitar_tramos_repetidos([a, b, c], [0.9, 0.8, 0.7]) == ([a, c], [0.9, 0.7])
