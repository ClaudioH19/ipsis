"""Motor v2 completo sobre un índice en memoria: sin modelos, sin red, determinista.

Lo comparten ``tests/consulta/test_caracterizacion_v2.py`` (congela las respuestas) y
``tests/consulta/test_aislamiento_v2.py`` (comprueba que servir v2 no carga código
del motor v1). ``tests/`` está en ``pythonpath``: ``from apoyo_v2 import ...``.

El motor se construye con la fábrica real (``construir_motor``), igual que
``ipsis serve``; solo el recuperador es falso.
"""
from __future__ import annotations

import re
import unicodedata
from types import SimpleNamespace

from ipsis.nucleo.esquemas import ChunkRecord, RetrievalCandidate, RetrievalSignals

# (chunk_id, sección, tipo de contenido, texto). Un solo documento: «Manual del purificador».
FRAGMENTOS = [
    ("filtro", ["Mantenimiento"], "parrafo",
     "El filtro de sedimentos del purificador se cambia cada 6 meses."),
    ("reembolso", ["Postventa", "Reembolsos"], "parrafo",
     "El reembolso del purificador se paga en 10 días hábiles desde la devolución."),
    ("garantia", ["Postventa", "Garantía"], "parrafo",
     "La garantía cubre 12 meses desde la compra del purificador."),
    ("visita", ["Instalación"], "parrafo",
     "Si no estás en la visita de instalación, se reagenda sin costo."),
    ("precios", ["Precios"], "tabla",
     "Modelo | Precio\nPurificador P1 | $120.000\nPurificador P2 | $180.000"),
    ("equipo-1", ["Equipo", "Uso"], "parrafo", "El equipo funciona solo con agua fría."),
    ("equipo-2", ["Equipo", "Seguridad"], "parrafo", "El equipo debe instalarse lejos de fuentes de calor."),
    ("equipo-3", ["Equipo", "Presión"], "parrafo", "El equipo admite una presión máxima de 4,0 bar."),
    ("equipo-4", ["Equipo", "Ruido"], "parrafo", "El equipo emite menos de 40 dB durante el uso."),
    ("equipo-5", ["Equipo", "Limpieza"], "parrafo", "El equipo se limpia por fuera con un paño húmedo."),
]
_SOBRAS = {"el", "la", "los", "las", "de", "del", "en", "se", "un", "una", "que", "con", "por", "para", "al", "es", "y", "a"}


def _tokens(texto: str) -> set[str]:
    plano = unicodedata.normalize("NFD", texto.lower())
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return {t for t in re.findall(r"[a-z0-9]+", plano) if len(t) >= 2 and t not in _SOBRAS}


def _candidato(posicion: int, fragmento) -> RetrievalCandidate:
    chunk_id, seccion, tipo, texto = fragmento
    inicio = posicion * 200
    return RetrievalCandidate(
        chunk=ChunkRecord(
            chunk_id=chunk_id, doc_id="manual", doc_titulo="Manual del purificador", version="1",
            texto_fuente=texto, texto_embedding=texto, offset_inicio=inicio, offset_fin=inicio + len(texto),
            seccion_path=seccion, tipo_contenido=tipo),
        signals=RetrievalSignals())


class RecuperadorMemoria:
    """Ordena por palabras en común con la pregunta; sin coincidencias no devuelve nada."""

    coleccion = None  # sin colección: no hay manifiesto ni carril multimedia

    def __init__(self):
        self._candidatos = [_candidato(i, f) for i, f in enumerate(FRAGMENTOS)]
        self._tokens = [_tokens(f[3]) for f in FRAGMENTOS]

    def recuperar(self, consulta, limite, filtro=None):
        pregunta = _tokens(getattr(consulta, "pregunta_original", None) or str(consulta))
        puntuados = sorted(
            ((len(pregunta & tokens), -i) for i, tokens in enumerate(self._tokens) if pregunta & tokens),
            reverse=True)
        salida = []
        for rango, (coincidencias, i) in enumerate(puntuados[:limite], start=1):
            candidato = self._candidatos[-i].model_copy(deep=True)
            candidato.signals = RetrievalSignals(fusion_rank=rango, fusion_score=round(coincidencias / 10, 4))
            salida.append(candidato)
        return salida

    def calentar(self):
        pass

    def n_chunks(self):
        return len(self._candidatos)

    def inventario_entidades(self):
        return set()

    def estadisticas_lexico(self):
        return SimpleNamespace()


def construir_motor_en_memoria(perfil: str = "light"):
    """El motor que arma ``ipsis serve``, con el recuperador en memoria (cwd: un proyecto con ``config/``)."""
    from ipsis.aplicacion.consulta import construir_motor
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto
    from ipsis.nucleo.registro import RegistroComponentes

    registro = RegistroComponentes()
    registro.registrar("retriever", "memoria_v2", lambda **_: RecuperadorMemoria())
    cfg = cargar_proyecto()
    cfg["componentes"]["retriever"] = "memoria_v2"
    return construir_motor(cfg, cfg_dominio={**cargar_dominio(), "perfil": perfil}, registro=registro)


# Módulos del motor v1 (cascada de etapas, calibración y heurísticas que solo ella usa).
# v2 no debe importarlos, ni directa ni indirectamente; ver ``tests/test_arquitectura.py``
# y ``tests/consulta/test_aislamiento_v2.py``.
MODULOS_V1 = (
    "ipsis.consulta.motor",
    "ipsis.consulta.contexto",
    "ipsis.consulta.alternativas",
    "ipsis.consulta.etapas",
    "ipsis.lenguaje.aclaracion",
    "ipsis.lenguaje.estilo",
    "ipsis.lenguaje.intenciones",
    "ipsis.lenguaje.respuestas",
    "ipsis.evaluacion.calibracion",
)


def es_modulo_v1(nombre: str) -> bool:
    return any(nombre == m or nombre.startswith(m + ".") for m in MODULOS_V1)
