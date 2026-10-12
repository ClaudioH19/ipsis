"""Glosario de los archivos del proyecto: claves y valores en inglés en el disco.

El código usa nombres internos (en español); los archivos que edita el usuario
usan inglés. La traducción ocurre solo aquí, en el borde:

- ``a_interno``: lo leído del disco → nombres internos (al cargar);
- ``a_externo``: nombres internos → disco (al escribir);
- ``nombres_externos``: un mensaje de error con nombres internos → externos.

Una clave o un valor desconocido pasa sin cambios. Así un archivo anterior,
con claves en español, también se lee (y la migración lo reescribe en inglés).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Clave:
    externa: str
    hijos: dict[str, "Clave"] | None = None  # el valor es un objeto con estas claves
    lista: bool = False  # el valor es una lista de objetos con ``hijos``
    valores: dict[str, str] = field(default_factory=dict)  # valor interno → valor externo (o lista de ellos)


def _c(externa: str, hijos: dict | None = None, **kw) -> Clave:
    return Clave(externa, hijos, **kw)


# --- vocabulario compartido ----------------------------------------------------------------------
UMBRALES = {"oov_dominio": _c("oov_domain"), "oov_ok": _c("oov_ok"), "dominio": _c("domain"),
            "relacionado": _c("related"), "foco": _c("focus"), "ok": _c("ok"), "cov": _c("cov"),
            "ok_fuerte": _c("ok_strong"), "oov_ok_fuerte": _c("oov_ok_strong"),
            "foco_coloquial": _c("focus_informal")}
MODELOS = {"denso": _c("dense"), "reranker": _c("reranker"), "lector": _c("reader")}
MODOS_RECUPERACION = {"vectorial": "dense", "hibrida": "hybrid", "dispersa": "sparse"}
ETAPAS = {"conversacional": "conversational", "analisis": "analysis", "confianza": "confidence",
          "filtros": "filters", "recuperacion": "retrieval", "reranking": "reranking", "lectura": "reading",
          "evidencia": "evidence", "politica": "policy", "redaccion": "rendering", "verificacion": "verification"}

POSTURAS = {"proactiva": "proactive", "estricta": "strict"}
SENALES_ALTERNATIVA = {"familia": _c("family"), "medida": _c("measure"), "terminos": _c("terms"), "seccion": _c("section"),
                       "keywords": _c("keywords"), "categoria": _c("category"), "similitud": _c("similarity")}

PERFIL = {
    "perfil": _c("profile"), "descripcion": _c("description"), "presupuesto_p95_ms": _c("p95_budget_ms"),
    "modelos": _c("models", MODELOS),
    "cascada": _c("cascade", {
        "recuperar_n": _c("retrieve_n"), "rerank_k": _c("rerank_k"),
        "rerank_candidatos": _c("rerank_candidates"), "leer_m": _c("read_m"),
        "max_tokens_pasaje": _c("max_passage_tokens"), "stride": _c("stride"),
        "salida_temprana_sin_foco": _c("early_exit_without_focus"), "concordancia": _c("agreement_check"),
        "max_caracteres_lectura": _c("max_reading_chars"), "lectura_semantica": _c("semantic_reading"),
    }),
    "etapas": _c("stages", valores=ETAPAS),
    "lexico": _c("lexical", {"k1": _c("k1"), "b": _c("b"), "max_terminos_foco": _c("max_focus_terms")}),
    "umbrales_por_defecto": _c("default_thresholds", UMBRALES),
    "recuperacion_modo": _c("retrieval_mode", valores=MODOS_RECUPERACION),
    "alternativas": _c("alternatives", {"umbral": _c("threshold"), "pesos": _c("weights", SENALES_ALTERNATIVA)}),
}

# --- archivos ------------------------------------------------------------------------------------
ASISTENTE = {
    "config_version": _c("config_version"), "nombre_asistente": _c("assistant_name"),
    "descripcion_dominio": _c("domain_description"), "idioma": _c("language"), "perfil": _c("profile"),
    "cors_origenes": _c("cors_origins"), "claves_widget": _c("widget_keys"),
    "registro": _c("query_log", {"activo": _c("enabled")}),
    "postura": _c("posture", {"modo": _c("mode", valores=POSTURAS), "max_alternativas": _c("max_alternatives")}),
}

MOTOR = {
    "config_version": _c("config_version"),
    "pipeline": _c("pipeline"),
    "v2": _c("v2", {"corregir_erratas": _c("spelling_corrections"),
                     "max_caracteres_contexto": _c("max_context_chars"),
                     "recuperar_n": _c("retrieve_n"), "rerank_candidatos": _c("rerank_candidates"),
                     "rerank_k": _c("rerank_k"), "leer_m": _c("read_m"),
                     "lote_reranker": _c("reranker_batch_size"),
                     "presupuesto_consulta_ms": _c("query_budget_ms"),
                     "max_tokens_reranker": _c("reranker_max_tokens"),
                     "max_tokens_pasaje": _c("max_passage_tokens"), "stride": _c("stride"),
                     "resultados_n": _c("results_limit"),
                     "max_caracteres_resultado": _c("max_result_chars"),
                     "vecinos_contexto": _c("context_neighbors"),
                     "destacar_fragmentos": _c("qa_highlights")}),
    "recuperacion": _c("retrieval", {
        "modelo": _c("model"), "estrategia_chunking": _c("chunking_strategy"), "con_header": _c("with_header"),
        "modo": _c("mode", valores=MODOS_RECUPERACION), "top_k": _c("top_k"),
        "coleccion_base": _c("collection_base"), "qdrant_path": _c("qdrant_path"),
        "version_coleccion": _c("collection_version"),
        "preparacion": _c("preparation", {"modo": _c("mode", valores={"estructural_v1": "structural_v1"}),
            "max_palabras_unidad": _c("max_unit_words"), "palabras_hijo": _c("child_words")}),
    }),
    "componentes": _c("components", {
        nombre: _c(nombre) for nombre in ("parser", "chunker", "dense_encoder", "sparse_encoder", "retriever",
                                          "fusion", "reranker", "intent_classifier", "answer_extractor",
                                          "evidence_verifier", "response_renderer")
    } | {"abstention_policy": _c("abstention_policy", valores={"cascada_v1": "cascade_v1"})}),
    "qdrant": _c("qdrant", {"modo": _c("mode", valores={"servidor": "server"}), "url_servidor": _c("server_url")}),
    "servicio": _c("service", {"concurrencia_maxima": _c("max_concurrency")}),
    "conversacion": _c("conversation", {"vencimiento_minutos": _c("expiry_minutes"),
                                        "max_sesiones": _c("max_sessions")}),
    "seguridad": _c("security", {"limite_peticiones": _c("rate_limit", {
        "capacidad": _c("capacity"), "tasa_por_segundo": _c("rate_per_second")})}),
    "redaccion": _c("rendering", {
        "longitud_maxima_fragmento_chars": _c("max_fragment_chars"),
        "max_fragmentos_en_respuesta": _c("max_fragments"), "score_relativo_minimo": _c("min_relative_score"),
        "cita_en_texto": _c("inline_citation", valores={"completa": "full", "breve": "short", "ninguna": "none"}),
        "incluir_apertura": _c("include_opening"),
    }),
    "abstencion": _c("abstention", {"max_fragmentos_adicionales": _c("max_extra_fragments")}),
    "criterios_aceptacion": _c("acceptance_criteria"),
    "pipeline_version": _c("pipeline_version"),
    "ajustes_perfil": _c("profile_overrides", PERFIL),
}

_COLORES = {"acento": _c("accent"), "acento_texto": _c("accent_text"), "superficie": _c("surface"),
            "fondo": _c("background"), "texto": _c("text"), "texto_suave": _c("muted_text"), "borde": _c("border"),
            "aviso": _c("warning"), "aviso_borde": _c("warning_border"), "vivo": _c("live")}
POSICIONES = {"abajo-derecha": "bottom-right", "abajo-izquierda": "bottom-left", "arriba-derecha": "top-right",
              "arriba-izquierda": "top-left", "incrustado": "embedded"}
TAMANOS = {"compacto": "compact", "normal": "normal", "amplio": "wide"}
LANZADORES = {"burbuja": "bubble", "pestana": "tab", "oculto": "hidden"}
PRESETS = {"clasico": "classic", "contraste": "contrast", "minimal": "minimal", "editorial": "editorial",
           "buscador": "search", "buscador_compacto": "search_compact"}

ESTILOS = {
    "preset": _c("preset", valores=PRESETS),
    "presentacion": _c("presentation", {
        "densidad": _c("density", valores={"comoda": "comfortable", "compacta": "compact"}),
        "citas": _c("citations", valores={"acordeon": "accordion", "lista": "list"}),
        "mostrar_etiqueta_estado": _c("show_status_label"),
        "alineacion": _c("text_align", valores={"inicio": "start", "justificada": "justify"}),
    }),
    "ubicacion": _c("placement", {
        "posicion": _c("position", valores=POSICIONES), "desplazamiento_x": _c("offset_x"),
        "desplazamiento_y": _c("offset_y"), "z_index": _c("z_index"), "tamano": _c("size", valores=TAMANOS),
        "lanzador": _c("launcher", valores=LANZADORES),
    }),
    "colores": _c("colors", _COLORES),
    "colores_oscuro": _c("dark_colors", _COLORES),
    "tipografia": _c("typography", {
        "familia": _c("family"), "tamano_base": _c("base_size"), "tamano_mensaje": _c("message_size"),
        "tamano_cita": _c("citation_size"), "tamano_etiqueta": _c("label_size"), "interlineado": _c("line_height"),
    }),
    "forma": _c("shape", {
        "radio_panel": _c("panel_radius"), "radio_burbuja": _c("bubble_radius"), "radio_control": _c("control_radius"),
        "ancho_panel": _c("panel_width"), "alto_panel": _c("panel_height"), "tamano_boton": _c("button_size"),
        "tamano_icono": _c("icon_size"), "separacion": _c("gap"), "relleno": _c("padding"),
    }),
    "sombras": _c("shadows", {"panel": _c("panel"), "boton": _c("button"), "panel_oscuro": _c("panel_dark"),
                              "boton_oscuro": _c("button_dark")}),
    "animaciones": _c("animations", {
        "activadas": _c("enabled"), "duracion_panel": _c("panel_duration"), "duracion_burbuja": _c("bubble_duration"),
        "duracion_control": _c("control_duration"), "duracion_latido": _c("pulse_duration"), "curva": _c("easing"),
        "desplazamiento_entrada": _c("enter_offset"), "escala_entrada": _c("enter_scale"),
        "escala_hover": _c("hover_scale"),
    }),
    "css_extra": _c("custom_css"),
}

PERSONALIDAD = {
    "config_version": _c("config_version"),
    "tono": _c("tone", {"activo": _c("active"), "variedad": _c("variety", valores={"rotativa": "rotating",
                                                                                    "fija": "fixed"}),
                        "plantillas": _c("templates")}),
    "avatar": _c("avatar", {
        "activo": _c("enabled"), "definicion": _c("definition"),
        "ubicacion": _c("placement", valores={"cabecera": "header", "esquina-superior": "top-corner",
                                              "esquina-inferior": "bottom-corner"}),
        "tamano": _c("size"), "en_lanzador": _c("in_launcher"),
        "mirada": _c("gaze", {"activa": _c("enabled"), "amplitud_ojos": _c("eye_range"),
                              "amplitud_cabeza": _c("head_range"), "zona_muerta": _c("dead_zone")}),
        "inactividad_min": _c("idle_minutes"),
        "colores": _c("colors", {"cuerpo": _c("body"), "ojos": _c("eyes")}),
        "eventos": _c("events"),
    }),
}

DOMINIO = {
    "sinonimos": _c("synonyms"),
    "organismos": _c("organizations"),
    "extractores_regex": _c("regex_extractors", {
        "tipo": _c("type"), "patron": _c("pattern"), "valor_norm": _c("normalized_value"), "glosa": _c("gloss"),
        "ignorecase": _c("ignore_case"), "transform": _c("transform"),
    }, lista=True),
    "taxonomia": _c("taxonomy", {
        "dominio": _c("domain"),
        "categorias": _c("categories", {"id": _c("id"), "descripcion": _c("description"),
                                        "palabras_gatillo": _c("trigger_words")}, lista=True),
        "umbral_categoria_filtro_duro": _c("hard_filter_threshold"),
    }),
}

CALIBRACION = {
    "version": _c("version"),
    "estado": _c("status", valores={"calibrado": "calibrated", "muestra_insuficiente": "insufficient_sample",
                                    "sin_umbral_seguro": "no_safe_threshold"}),
    "alfa": _c("alpha"), "confianza": _c("confidence"),
    "procedencia": _c("provenance", {"perfil": _c("profile"), "modelos": _c("models", MODELOS),
                                     "hash_corpus": _c("corpus_hash"), "banco": _c("bank"),
                                     "hash_banco": _c("bank_hash"), "hash_lexico": _c("lexical_hash")}),
    "umbrales": _c("thresholds", UMBRALES),
    "resultado": _c("result"),
}

CATALOGO = {
    "documentos": _c("documents", {
        "archivo": _c("file"), "doc_id": _c("doc_id"), "doc_titulo": _c("doc_title"), "version": _c("version"),
        "vigente": _c("active"), "hash_contenido": _c("content_hash"),
    }, lista=True),
}

ARCHIVOS = {"asistente": ASISTENTE, "motor": MOTOR, "estilos": ESTILOS, "personalidad": PERSONALIDAD,
            "dominio": DOMINIO, "calibracion": CALIBRACION, "catalogo": CATALOGO, "perfil": PERFIL}


# --- traducción ----------------------------------------------------------------------------------
def _valor(valor: Any, mapa: dict[str, str]) -> Any:
    if not mapa:
        return valor
    if isinstance(valor, list):
        return [mapa.get(v, v) if isinstance(v, str) else v for v in valor]
    return mapa.get(valor, valor) if isinstance(valor, str) else valor


def _traducir(datos: Any, espec: dict[str, Clave], *, hacia_afuera: bool) -> Any:
    if not isinstance(datos, dict):
        return datos
    if hacia_afuera:
        por_nombre = espec
    else:
        por_nombre = _inverso(id(espec), espec)
    salida: dict[str, Any] = {}
    for clave, valor in datos.items():
        regla = por_nombre.get(clave)
        if regla is None:
            salida[clave] = valor
            continue
        destino = regla.externa if hacia_afuera else _interna(espec, regla)
        valores = regla.valores if hacia_afuera else {v: k for k, v in regla.valores.items()}
        if regla.hijos is not None and regla.lista and isinstance(valor, list):
            valor = [_traducir(v, regla.hijos, hacia_afuera=hacia_afuera) for v in valor]
        elif regla.hijos is not None and isinstance(valor, dict):
            valor = _traducir(valor, regla.hijos, hacia_afuera=hacia_afuera)
        else:
            valor = _valor(valor, valores)
        salida[destino] = valor
    return salida


_CACHE_INVERSO: dict[int, dict[str, Clave]] = {}


def _inverso(clave: int, espec: dict[str, Clave]) -> dict[str, Clave]:
    if clave not in _CACHE_INVERSO:
        _CACHE_INVERSO[clave] = {regla.externa: regla for regla in espec.values()}
    return _CACHE_INVERSO[clave]


def _interna(espec: dict[str, Clave], regla: Clave) -> str:
    return next(nombre for nombre, r in espec.items() if r is regla)


def a_interno(datos: Any, archivo: str) -> Any:
    """Lo leído de un archivo del proyecto (claves en inglés o, si es anterior, en español) → interno."""
    return _traducir(datos, ARCHIVOS[archivo], hacia_afuera=False)


def a_externo(datos: Any, archivo: str) -> Any:
    """Interno → como se escribe en el archivo (inglés)."""
    return _traducir(datos, ARCHIVOS[archivo], hacia_afuera=True)


def _pares(espec: dict[str, Clave]) -> dict[str, str]:
    salida: dict[str, str] = {}
    for nombre, regla in espec.items():
        if nombre != regla.externa:
            salida[nombre] = regla.externa
        salida.update({v: e for v, e in regla.valores.items() if v != e})
        if regla.hijos:
            salida.update(_pares(regla.hijos))
    return salida


def nombres_externos(texto: str, archivo: str) -> str:
    """Reemplaza en un mensaje los nombres internos de claves y valores por los del archivo."""
    pares = _pares(ARCHIVOS[archivo])
    if not pares:
        return texto
    patron = re.compile(r"(?<![\w-])(" + "|".join(re.escape(k) for k in sorted(pares, key=len, reverse=True))
                        + r")(?![\w-])")
    return patron.sub(lambda m: pares[m.group(1)], texto)


__all__ = ["ARCHIVOS", "Clave", "a_externo", "a_interno", "nombres_externos"]
