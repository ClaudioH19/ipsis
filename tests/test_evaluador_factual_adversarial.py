"""Banco de pruebas ADVERSARIALES del evaluador factual (E6, sección 5).

Los casos se escriben a mano y no dependen de un generador de perturbaciones,
para evitar una validación circular del evaluador.

Casos exigidos por el encargo:
  - cifra inventada agregada                      -> debe RECHAZAR
  - organismo inventado agregado                   -> debe RECHAZAR
  - plazo inventado agregado                       -> debe RECHAZAR
  - doble negación que invierte el sentido          -> debe RECHAZAR
  - respuesta truncada a la mitad                   -> debe RECHAZAR
  - respuesta vacía                                 -> debe RECHAZAR
  - control: respuesta idéntica                     -> debe ACEPTAR
  - control: paráfrasis fiel                        -> debe ACEPTAR
"""
from rag.metricas import evaluar_exactitud_factual, _valores_precision_amplios

# Referencia base, redactada a mano para este archivo (no proviene de
# ningún golden set ni plantilla externa), con contenido
# de dos tipos de entidad determinista (organismo y plazo) para poder probar
# la precisión de hechos contra fragmentos fuente explícitos.
FRAGMENTO_FUENTE = (
    "El CDP confirma la inscripción del estudiante y coordina con la "
    "empresa receptora. El estudiante debe completar el formulario dentro "
    "de 5 días hábiles siguientes a la notificación."
)
REFERENCIA = (
    "El CDP confirma la inscripción del estudiante. "
    "El estudiante debe completar el formulario dentro de 5 días hábiles."
)


def test_cifra_inventada_agregada_se_rechaza():
    candidata = REFERENCIA + " Además, el arancel asociado es de 45 UF."
    r = evaluar_exactitud_factual(
        respuesta_candidata=candidata,
        respuesta_referencia=REFERENCIA,
        hechos_clave=[{"tipo": "organismo", "valor_norm": "cdp"}],
        hechos_prohibidos=[],
        fragmentos=[FRAGMENTO_FUENTE],
    )
    assert not r.correcta, "una cifra monetaria inventada agregada al final debe rechazarse"
    assert any("no respaldadas" in m or "inventad" in m for m in r.motivos)


def test_organismo_inventado_agregado_se_rechaza():
    candidata = REFERENCIA + " Esto lo resuelve la Contraloría General de la República."
    r = evaluar_exactitud_factual(
        respuesta_candidata=candidata,
        respuesta_referencia=REFERENCIA,
        hechos_clave=[{"tipo": "organismo", "valor_norm": "cdp"}],
        hechos_prohibidos=[],
        fragmentos=[FRAGMENTO_FUENTE],
    )
    assert not r.correcta, "un organismo ajeno al dominio, agregado sin respaldo, debe rechazarse"


def test_plazo_inventado_agregado_se_rechaza():
    candidata = REFERENCIA + " El trámite demora 90 días hábiles."
    r = evaluar_exactitud_factual(
        respuesta_candidata=candidata,
        respuesta_referencia=REFERENCIA,
        hechos_clave=[{"tipo": "organismo", "valor_norm": "cdp"}],
        hechos_prohibidos=[],
        fragmentos=[FRAGMENTO_FUENTE],
    )
    assert not r.correcta, "un plazo (90 días hábiles) que no está en la fuente debe rechazarse"
    assert any("no respaldadas" in m or "inventad" in m for m in r.motivos)


def test_plazo_inventado_se_rechaza_incluso_sin_fragmentos_explicitos():
    # Sin ``fragmentos``, la precisión de hechos cae al respaldo por
    # referencia (compatibilidad hacia atrás): el plazo agregado tampoco
    # está en la referencia, así que se debe rechazar igual.
    candidata = REFERENCIA + " El trámite demora 90 días hábiles."
    r = evaluar_exactitud_factual(
        respuesta_candidata=candidata,
        respuesta_referencia=REFERENCIA,
        hechos_clave=[{"tipo": "organismo", "valor_norm": "cdp"}],
        hechos_prohibidos=[],
    )
    assert not r.correcta


def test_doble_negacion_que_invierte_el_sentido_se_rechaza():
    # Oración escrita a mano: dos
    # negaciones en cláusulas distintas invierten el sentido de "debe" y de
    # "puede" pero la paridad GLOBAL de negaciones no cambia (por eso el
    # diseño anterior, basado en paridad global, la aceptaba: 84.5% medido).
    referencia = (
        "El estudiante debe entregar el informe final antes del cierre; "
        "el supervisor puede autorizar una extensión si hay justificación."
    )
    candidata = (
        "El estudiante no debe entregar el informe final antes del cierre; "
        "el supervisor no puede autorizar una extensión si hay justificación."
    )
    r = evaluar_exactitud_factual(
        respuesta_candidata=candidata,
        respuesta_referencia=referencia,
        hechos_clave=[],
        hechos_prohibidos=[],
    )
    assert not r.correcta, "invertir el sentido con doble negación debe rechazarse aunque la paridad global no cambie"
    assert any("cláusula" in m for m in r.motivos)


def test_respuesta_truncada_a_la_mitad_se_rechaza():
    referencia = (
        "El estudiante debe completar el formulario dentro de 5 días hábiles. "
        "Luego el CDP valida la inscripción y notifica a la empresa receptora. "
        "Finalmente el AEP registra la calificación en el sistema."
    )
    # truncada literalmente a la mitad de los caracteres, cortando a medio
    # texto (no en un punto de frase "limpio"): simula una respuesta cortada
    # por un límite de longitud, no una paráfrasis breve deliberada.
    mitad = len(referencia) // 2
    candidata = referencia[:mitad]
    r = evaluar_exactitud_factual(
        respuesta_candidata=candidata,
        respuesta_referencia=referencia,
        hechos_clave=[{"tipo": "organismo", "valor_norm": "cdp"}],
        hechos_prohibidos=[],
    )
    assert not r.correcta, "una respuesta cortada a la mitad debe rechazarse"


def test_respuesta_vacia_se_rechaza():
    r = evaluar_exactitud_factual(
        respuesta_candidata="",
        respuesta_referencia=REFERENCIA,
        hechos_clave=[{"tipo": "organismo", "valor_norm": "cdp"}],
        hechos_prohibidos=[],
    )
    assert not r.correcta, "una respuesta vacía nunca puede marcarse correcta"


def test_control_respuesta_identica_se_acepta():
    r = evaluar_exactitud_factual(
        respuesta_candidata=REFERENCIA,
        respuesta_referencia=REFERENCIA,
        hechos_clave=[{"tipo": "organismo", "valor_norm": "cdp"}],
        hechos_prohibidos=[],
        fragmentos=[FRAGMENTO_FUENTE],
    )
    assert r.correcta, f"la respuesta idéntica a la referencia debe aceptarse; motivos={r.motivos}"


def test_control_parafrasis_fiel_se_acepta():
    # Reescritura de mano, con reordenamiento y sinónimos, que conserva
    # entidades, cláusulas y polaridad de negación intactas.
    parafrasis = (
        "Es el CDP quien confirma la inscripción del estudiante; "
        "dentro de 5 días hábiles, el estudiante tiene que completar el formulario."
    )
    r = evaluar_exactitud_factual(
        respuesta_candidata=parafrasis,
        respuesta_referencia=REFERENCIA,
        hechos_clave=[{"tipo": "organismo", "valor_norm": "cdp"}],
        hechos_prohibidos=[],
        fragmentos=[FRAGMENTO_FUENTE],
    )
    assert r.correcta, f"una paráfrasis fiel debe aceptarse; motivos={r.motivos}"


def test_organismo_generico_mismo_valor_norm_con_y_sin_articulo_inicial_mayuscula():
    """Etapa 2, tarea 1 (bug reportado por el revisor sobre
    ``_RE_ORGANISMO_GENERICO``): el mismo organismo debe normalizar al mismo
    ``valor_norm`` tanto si el artículo queda en mayúscula por ir al inicio
    de la oración, como si va en minúscula a mitad de frase. Antes de la
    reparación, "La Dirección de Escuela" -> "la_direccion_de_escuela" (el
    artículo quedaba pegado) y "la Dirección de Escuela" (mitad de frase) ->
    "direccion_de_escuela" (el artículo, en minúscula, no lo capturaba el
    regex): dos claves distintas para la misma entidad."""
    inicio_oracion = _valores_precision_amplios("La Dirección de Escuela resuelve el caso.")
    mitad_oracion = _valores_precision_amplios("El caso lo resuelve la Dirección de Escuela.")
    assert "organismo_generico_direccion_de_escuela" in inicio_oracion
    assert "organismo_generico_direccion_de_escuela" in mitad_oracion
    assert inicio_oracion == mitad_oracion


def test_parafrasis_fiel_que_reordena_organismo_al_inicio_se_acepta():
    """Caso mínimo reproducible del bug (equivalente a PERT-0181/Q-0100 del
    golden set v2): la referencia nombra el organismo a mitad de frase y la
    candidata (una paráfrasis fiel) lo mueve al inicio de la oración. Antes
    de la reparación, la guardia de precisión de hechos marcaba esto como
    "posible información inventada" por el choque de valor_norm descrito
    arriba, aunque la candidata no agrega ningún hecho nuevo."""
    fragmento = "Antes de la inscripción, la Dirección de Escuela planifica los módulos P1 y P2."
    referencia = "Antes de la inscripción, la Dirección de Escuela planifica los módulos P1 y P2."
    candidata = "La Dirección de Escuela planifica los módulos P1 y P2 antes de la inscripción."
    r = evaluar_exactitud_factual(
        respuesta_candidata=candidata,
        respuesta_referencia=referencia,
        hechos_clave=[{"tipo": "organismo", "valor_norm": "direccion_de_escuela"}],
        hechos_prohibidos=[],
        fragmentos=[fragmento],
    )
    assert r.correcta, f"paráfrasis fiel que reordena el organismo al inicio debe aceptarse; motivos={r.motivos}"
