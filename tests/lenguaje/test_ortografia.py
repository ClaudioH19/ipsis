"""Corrección de erratas contra el vocabulario del corpus (ipsis.lenguaje.ortografia)."""
from __future__ import annotations

import pytest

from ipsis.indice.estadisticas import EstadisticasLexicas
from ipsis.lenguaje.ortografia import correcciones, corregir, distancia
from ipsis.lenguaje.paquete import cargar_paquete

CORPUS = {
    "es": ["La contraseña vence cada 90 días.", "El teletrabajo puede abarcar hasta tres días por semana.",
           "El viático diario es de 150 dólares en el extranjero.", "Los pasajes aéreos los compra la Unidad de Viajes.",
           "Las muestras de sangre se guardan a 4 °C."],
    "en": ["The password expires every 90 days.", "The daily allowance is 150 dollars abroad.",
           "Air tickets are bought by the Travel Unit.", "The library opens on Saturdays."],
    "pt": ["A senha expira a cada 90 dias.", "A diária é de 150 dólares no exterior.",
           "As passagens aéreas são compradas pela Unidade de Viagens."],
}


@pytest.fixture(scope="module")
def entorno():
    salida = {}
    for idioma, textos in CORPUS.items():
        paquete = cargar_paquete(idioma)
        salida[idioma] = (paquete, EstadisticasLexicas.construir(textos, paquete))
    return salida


@pytest.mark.parametrize(("idioma", "pregunta", "esperado"), [
    ("es", "como pido telatrabajo", {"telatrabajo": "teletrabajo"}),
    ("es", "cuanto me dan de viatcio", {"viatcio": "viático"}),
    ("en", "how often do i gotta change my pasword", {"pasword": "password"}),
    ("en", "daily alowance abroad", {"alowance": "allowance"}),
    ("pt", "quando troco a sehna", {"sehna": "senha"}),
])
def test_una_errata_se_corrige_a_la_forma_del_corpus(entorno, idioma, pregunta, esperado):
    paquete, est = entorno[idioma]
    assert correcciones(pregunta, paquete, est) == esperado


@pytest.mark.parametrize(("idioma", "pregunta"), [
    ("es", "quien compra los pasajes de bus"),        # «bus»: corta y real
    ("es", "cuanto aguanta la orina en el refri"),     # «orina» existe en el léxico
    ("es", "a q hora abre la biblio los feriados"),    # «feriados»: real, aunque no esté en el corpus
    ("es", "cada cuanto vence la contrasena"),         # sin tilde no es errata: ya coincide
    ("en", "who books my train tickets"),
    ("en", "library hours on bank holidays"),
    ("pt", "quem compra passagens de onibus"),
])
def test_una_palabra_real_o_ya_presente_no_se_toca(entorno, idioma, pregunta):
    """Corregir una palabra real ausente del corpus convertiría una trampa en un falso ok."""
    paquete, est = entorno[idioma]
    assert correcciones(pregunta, paquete, est) == {}


def test_un_empate_entre_candidatas_no_se_resuelve():
    paquete = cargar_paquete("es")
    est = EstadisticasLexicas.construir(["El campo norte.", "El canto sur."], paquete)
    assert correcciones("donde queda el canpo", paquete, est) == {}


def test_un_paquete_de_respaldo_no_corrige(entorno):
    _, est = entorno["en"]
    respaldo = cargar_paquete("fi")
    assert respaldo.respaldo
    assert correcciones("pasword", respaldo, est) == {}


def test_distancia_cuenta_transposiciones_y_se_corta_en_el_tope():
    assert distancia("pasword", "password", 2) == 1
    assert distancia("viatcio", "viatico", 1) == 1
    assert distancia("teletrabajo", "telatrabajo", 2) == 1
    assert distancia("bus", "biblioteca", 2) == 3


def test_corregir_reemplaza_solo_palabras_completas():
    assert corregir("pasword y paswords", {"pasword": "password"}) == "password y paswords"


# --- capa de normalización: ideas de SymSpell Compound contra el corpus ----------------------
CORPUS_COMPUESTO = ["El estacionamiento abre a las 7:00 y cobra 1.500 pesos por hora.",
                    "La beca financia el 80 % del arancel.", "Cada funcionario registra dos patentes.",
                    "El computador se entrega con la garantía vigente."]


@pytest.fixture(scope="module")
def compuesto():
    paquete = cargar_paquete("es")
    return paquete, EstadisticasLexicas.construir(CORPUS_COMPUESTO, paquete)


@pytest.mark.parametrize(("pregunta", "esperado"), [
    ("cuanto covran por hora", {"covran": "cobra"}),                # por raíz: «cobran» no está, «cobra» sí
    ("a q hora abreel estacionamiento", {"abreel": "abre el"}),     # palabra funcional pegada
    ("cuanto cuesta el estacio namiento", {"estacio namiento": "estacionamiento"}),  # palabra separada
    ("a q hora avre", {"avre": "abre"}),                            # corta (4 letras), una sola candidata
])
def test_la_capa_corrige_raices_palabras_pegadas_separadas_y_cortas(compuesto, pregunta, esperado):
    paquete, est = compuesto
    assert correcciones(pregunta, paquete, est) == esperado


@pytest.mark.parametrize("pregunta", [
    "cuanto cuesta la sala Atacama",      # nombre propio: mayúscula fuera del inicio
    "se entrega con cable HDMI",          # sigla
    "de cuantas letras es la clave del compu",  # «compu» lo resuelve su grupo de sinónimos
    "si se muere un familiar",            # conjugación real: no se lleva a otra palabra
    "cuanto financia la veca",            # su raíz («vec») es la de una palabra real: no se arriesga
])
def test_la_capa_no_toca_nombres_siglas_ni_palabras_de_grupos(compuesto, pregunta):
    paquete, est = compuesto
    assert correcciones(pregunta, paquete, est) == {}


def test_corregir_aplica_uniones_y_separaciones():
    assert corregir("a q hora abreel el estacio namiento", {"abreel": "abre el", "estacio namiento": "estacionamiento"}) \
        == "a q hora abre el el estacionamiento"


# --- contexto: pares de palabras del corpus (presencia, no frecuencia) ----------------------
def test_los_pares_cuentan_presencia_y_un_titulo_repetido_no_pesa_mas():
    from ipsis.lenguaje.ortografia import pares_de_contexto

    paquete = cargar_paquete("en")
    una = pares_de_contexto(["Parking permit rules\nThe parking permit is issued by Security."], paquete)
    repetida = pares_de_contexto(["Parking permit rules\n" * 50 + "The parking permit is issued by Security."],
                                 paquete)
    assert una == repetida and len(una) == len(set(una))


def _con_contexto(textos, idioma="en"):
    from ipsis.lenguaje.ortografia import Corrector, pares_de_contexto

    paquete = cargar_paquete(idioma)
    est = EstadisticasLexicas.construir(textos, paquete)
    pares = frozenset(tuple(p.split(" ", 1)) for p in pares_de_contexto(textos, paquete))
    return paquete, est, Corrector(paquete, est, pares=pares), Corrector(paquete, est, pares=frozenset())


def test_el_contexto_corrige_una_errata_que_forma_otra_palabra_con_las_dos_vecinas():
    """«paring» es una palabra real: solo cambia si el par existe con las dos vecinas."""
    textos = ["Security issues the parking permit within two days.", "The parking permit costs nothing."]
    _, _, con, sin = _con_contexto(textos)
    assert sin.correcciones("who issues the paring permit") == {}
    # «issues parking» y «parking permit» están en el corpus: las dos vecinas lo apoyan.
    assert con.correcciones("who issues the paring permit") == {"paring": "parking"}
    # Sin vecina de contenido a la izquierda, una sola no basta para una palabra real.
    assert con.correcciones("where is the paring permit") == {}


def test_el_contexto_no_cambia_una_palabra_real_con_una_sola_vecina():
    """«paper weight» frente a un corpus que dice «weigh»: la palabra real se respeta."""
    _, _, con, _ = _con_contexto(["Sheets must weigh between 70 and 120 grams."])
    assert con.correcciones("what paper weight is accepted") == {}


def test_la_autoprueba_decide_y_un_indice_viejo_sigue_sin_contexto(tmp_path):
    from ipsis.lenguaje.ortografia import Corrector

    paquete = cargar_paquete("es")
    textos = ["El estacionamiento funciona de lunes a viernes entre las siete y las veintiuna horas.",
              "Cada funcionario registra como máximo dos patentes en el sistema de estacionamiento."] * 3
    est = EstadisticasLexicas.construir(textos, paquete, textos_contexto=textos)
    assert est.pares and isinstance(est.contexto_erratas, bool)
    ruta = tmp_path / "stats.json"
    est.guardar(ruta)
    assert EstadisticasLexicas.cargar(ruta).pares == est.pares
    vieja = est.model_copy(update={"pares": [], "contexto_erratas": False})
    assert Corrector(paquete, vieja).pares == frozenset()
