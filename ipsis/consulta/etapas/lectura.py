"""Etapa de lectura: el lector QA busca el tramo exacto en los mejores pasajes."""
from __future__ import annotations

from ipsis.consulta.etapas.base import _Etapa
from ipsis.lenguaje.texto import dividir_oraciones
from ipsis.nucleo.esquemas import EvidenceSpan
from ipsis.recursos.mensajes import t


def _es_titulo(linea: str) -> bool:
    """Una línea corta y sin puntuación final («6.3 Procedimiento de Compra», «Verano»)."""
    linea = linea.strip()
    return bool(linea) and len(linea.split()) <= 10 and not linea.endswith((".", ":", ";", "?", "!", ")", "»", '"'))


def seccion_de(chunk, offset: int) -> list[str]:
    """Ruta de la sección que contiene ``offset`` (absoluto) dentro del chunk.

    Un chunk puede cruzar varias secciones (un FAQ entero); la evidencia nombra la
    de su oración, como en la selección sin lector: «¿Qué horario tiene la Mesa de
    Ayuda?» enmarca «La Mesa de Ayuda atiende…», no el título del documento."""
    for seccion in (chunk.metadata or {}).get("secciones") or []:
        if seccion["inicio"] <= offset < seccion["fin"]:
            return list(seccion["ruta"])
    return list(chunk.seccion_path)


def oracion_que_contiene(texto: str, inicio: int, fin: int) -> tuple[int, int]:
    """Rango de las oraciones de ``texto`` que cubren ``[inicio, fin)``. Se corta
    primero por línea: un título («6.3 Procedimiento de Compra») no es parte de la
    oración que lo sigue."""
    linea_ini = texto.rfind("\n", 0, inicio) + 1
    linea_fin = texto.find("\n", fin)
    linea_fin = len(texto) if linea_fin == -1 else linea_fin
    linea = texto[linea_ini:linea_fin]
    if _es_titulo(linea) and linea_fin < len(texto):
        # Un tramo dentro de un título («Verano») no basta como evidencia: va con
        # la primera oración de lo que titula, que es donde está el contenido.
        siguiente_fin = texto.find("\n", linea_fin + 1)
        siguiente_fin = len(texto) if siguiente_fin == -1 else siguiente_fin
        oraciones = dividir_oraciones(texto[linea_fin + 1:siguiente_fin])
        if oraciones:
            return linea_ini, linea_fin + 1 + oraciones[0][1]
    rangos = [(a + linea_ini, b + linea_ini) for a, b in dividir_oraciones(linea)
              if a + linea_ini < fin and b + linea_ini > inicio]
    if not rangos:
        return inicio, fin
    return rangos[0][0], rangos[-1][1]


def hay_discordancia(lecturas, umbral: float = 0.5) -> bool:
    """Dos tramos confiables de pasajes distintos con entidades del mismo tipo
    y valor distinto (p. ej. «6 meses» y «12 meses») se contradicen."""
    from ipsis.lenguaje.entidades import extraer_entidades

    confiables = sorted((lec for lec in lecturas if lec.texto and lec.s_qa >= umbral), key=lambda lec: -lec.s_qa)[:2]
    if len(confiables) < 2 or confiables[0].indice_pasaje == confiables[1].indice_pasaje:
        return False
    a = {(e["tipo"], e["valor_norm"]) for e in extraer_entidades(confiables[0].texto)}
    b = {(e["tipo"], e["valor_norm"]) for e in extraer_entidades(confiables[1].texto)}
    tipos_comunes = {t for t, _ in a} & {t for t, _ in b}
    return any({v for t, v in a if t == tipo} != {v for t, v in b if t == tipo} for tipo in tipos_comunes)


def _ventana_pertinente(motor, pregunta: str, texto: str, limite: int,
                        pregunta_usuario: str | None = None, comprension=None) -> tuple[int, int]:
    """Rango ``[a, b)`` de ``texto`` (a lo más ``limite`` caracteres) más pertinente."""
    recortar_relacion = bool(pregunta_usuario and getattr(comprension, "intencion", None) == "responsable")
    if len(texto) <= limite and not recortar_relacion:
        return 0, len(texto)
    from ipsis.consulta.etapas.seleccion import seleccionar_texto_pertinente

    obtener = getattr(getattr(motor, "retriever", None), "estadisticas_lexico", None)
    est = obtener() if callable(obtener) else None
    # En un seguimiento, la oración sobre lo que se pregunta ahora evita
    # que otra pregunta/respuesta del mismo pasaje domine al lector.
    resultado = seleccionar_texto_pertinente(pregunta, texto, 0, 0 if recortar_relacion else limite,
                                             estadisticas=est, centrada=not recortar_relacion,
                                             pregunta_usuario=pregunta_usuario, comprension=comprension)
    return resultado.offset_inicio, resultado.offset_fin


VENTANAS_SEMANTICAS = 3
_RRF_K = 5


def ventanas_semanticas(motor, pregunta: str, candidatos: list, comprension=None,
                        n: int = VENTANAS_SEMANTICAS) -> list[tuple[object, int, int]]:
    """Las ``n`` oraciones de los candidatos que mejor ordena la fusión (RRF) de tres
    órdenes: cross-encoder y coseno denso sobre «título de la sección. oración», y
    ``s_lex`` con las pistas de la intención. Cada una se lee con la oración anterior
    de su línea como contexto. Devuelve ``(candidato, inicio, fin)`` con offsets del chunk.

    Elegir la ventana por palabras perdía las paráfrasis: «olvidé la clave, cómo la
    cambio?» leía «La contraseña vence cada 90 días» y no «Ingrese al portal…». Un
    cross-encoder no da una escala absoluta, pero ordena bien dentro de una consulta.
    Sin reranker o sin codificador, ``[]``: se usa la ventana léxica."""
    codificador = getattr(getattr(motor, "retriever", None), "codificador", None)
    vector = getattr(getattr(motor, "retriever", None), "vector_consulta", None)
    if motor.reranker is None or codificador is None or not callable(vector):
        return []
    import numpy as np

    from ipsis.consulta.etapas.seleccion import _puntuar, dividir_en_unidades

    # La presentación de un documento con secciones («Establece las condiciones de la beca
    # de perfeccionamiento para funcionarios») repite el tema de todas sus secciones y no
    # responde ninguna: «¿Quiénes pueden postular a la beca…?» se lee en «Requisitos».
    con_secciones = {c.chunk.doc_id for c in candidatos
                     if any(len(s["ruta"]) > 1 for s in (c.chunk.metadata or {}).get("secciones") or [])}
    unidades = []  # (candidato, unidad, inicio de la oración previa de la línea)
    for candidato in candidatos:
        texto = candidato.chunk.texto_fuente
        base = candidato.chunk.offset_inicio
        # Como en la selección: en un chunk con secciones, una línea fuera de todas es
        # un título («¿Cómo cambio mi contraseña?»), nunca la respuesta.
        secciones = [(s["inicio"] - base, s["fin"] - base)
                     for s in (candidato.chunk.metadata or {}).get("secciones") or []]
        previa = None
        for u in dividir_en_unidades(texto):
            misma_linea = previa is not None and "\n" not in texto[previa.offset_fin:u.offset_inicio]
            dentro = not secciones or any(a <= u.offset_inicio and u.offset_fin <= b for a, b in secciones)
            if dentro and candidato.chunk.doc_id in con_secciones:
                dentro = len(seccion_de(candidato.chunk, base + u.offset_inicio)) > 1
            if dentro and len(u.texto.split()) >= 3:
                unidades.append((candidato, u, previa.offset_inicio if misma_linea else u.offset_inicio))
            previa = u
    if not unidades:
        return []
    textos = []
    for candidato, u, _ in unidades:
        titulo = seccion_de(candidato.chunk, candidato.chunk.offset_inicio + u.offset_inicio)
        textos.append(f"{titulo[-1]}. {u.texto}" if titulo else u.texto)
    obtener = getattr(motor.retriever, "estadisticas_lexico", None)
    est = obtener() if callable(obtener) else None
    lex = _puntuar(pregunta, [u for _, u, _ in unidades], est, comprension)
    ce = motor.reranker.puntuar(pregunta, textos)
    q = np.asarray(vector(pregunta), dtype=float)
    matriz = np.asarray(codificador.codificar_documentos(textos), dtype=float)
    cos = list(matriz @ q)
    fusion = [0.0] * len(unidades)
    for puntajes in (ce, cos, lex):
        for rango, i in enumerate(sorted(range(len(unidades)), key=lambda i: -puntajes[i])):
            fusion[i] += 1.0 / (_RRF_K + rango + 1)
    ventanas: list[list] = []
    for i in sorted(range(len(unidades)), key=lambda i: -fusion[i]):
        candidato, u, inicio = unidades[i]
        # Una oración y la siguiente (que la trae como contexto) se leen juntas.
        solapada = next((v for v in ventanas if v[0] is candidato and inicio < v[2] and v[1] < u.offset_fin), None)
        if solapada is not None:
            solapada[1], solapada[2] = min(solapada[1], inicio), max(solapada[2], u.offset_fin)
        elif len(ventanas) < n:
            ventanas.append([candidato, inicio, u.offset_fin])
        else:
            break
    return [(c, a, b) for c, a, b in ventanas]


def _candidato_por_pista(motor, pregunta: str, leidos: list, resto: list, comprension=None):
    """Si la pregunta tiene una intención (``ipsis.lenguaje.consultas``) y la mejor
    oración con una pista suya está en un candidato que el reranker dejó fuera
    de la lectura (más abajo que ``leer_m`` o fuera de ``rerank_k``), ese
    candidato también se lee. El reranker mide «se parece»;
    la pista dice «puede responder esta relación»: con «¿cuándo empieza la
    compra?», un pasaje sobre horarios puede quedar arriba y «Una vez aprobado
    el formulario, se realizará la compra», abajo. El lector sigue decidiendo."""
    if not resto:
        return None
    from ipsis.consulta.etapas.seleccion import _puntuar, dividir_en_unidades
    from ipsis.lenguaje.consultas import comprender, peso_pista

    comprension = comprension or comprender(pregunta, motor.idioma)
    if not comprension.pistas:
        return None
    obtener = getattr(getattr(motor, "retriever", None), "estadisticas_lexico", None)
    est = obtener() if callable(obtener) else None

    def mejor_con_pista(candidato) -> float:
        unidades = dividir_en_unidades(candidato.chunk.texto_fuente)
        scores = _puntuar(pregunta, unidades, est, comprension)
        return max((s for u, s in zip(unidades, scores) if peso_pista(u.texto, comprension) > 0), default=0.0)

    techo = max((mejor_con_pista(c) for c in leidos), default=0.0)
    mejor = max(resto, key=mejor_con_pista)
    return mejor if mejor_con_pista(mejor) > techo else None


class EtapaLectura(_Etapa):
    """Lee los ``leer_m`` primeros candidatos. Si hay un tramo con respuesta,
    la evidencia es la oración que lo contiene (texto literal, offsets exactos)
    y el tramo viaja aparte como ``respuesta_exacta``."""

    nombre = "lectura"
    usa_modelos = True

    def ejecutar(self, ctx) -> None:
        m = self.motor
        if m.lector is None or not ctx.candidatos:
            return
        perfil = getattr(m, "perfil_instalacion", None)
        leer_m = perfil.cascada.leer_m if perfil is not None and perfil.cascada.leer_m else 2
        candidatos = ctx.candidatos[:leer_m]
        from ipsis.lenguaje.consultas import comprender_consulta

        comprension = comprender_consulta(ctx.consulta, getattr(m, "idioma", None)) if ctx.consulta is not None else None
        extra = _candidato_por_pista(m, ctx.pregunta, candidatos,
                                     [*ctx.candidatos[leer_m:], *ctx.descartados_rerank], comprension)
        if extra is not None:
            candidatos = [*candidatos, extra]
            ctx.diagnostico["lectura_por_pista"] = extra.chunk.chunk_id
            if extra not in ctx.candidatos:  # lo había dejado fuera el reranker: vuelve, para verificar su evidencia
                ctx.candidatos = [*ctx.candidatos, extra]
        limite = perfil.cascada.max_caracteres_lectura if perfil is not None else 600
        semanticas = []
        if perfil is not None and getattr(perfil.cascada, "lectura_semantica", False):
            # Todos los candidatos del reranker, no solo los leer_m primeros: la oración
            # que responde puede estar en el segundo o tercer chunk.
            todos = list({c.chunk.chunk_id: c for c in [*ctx.candidatos, *candidatos]}.values())
            semanticas = ventanas_semanticas(m, ctx.pregunta_usuario or ctx.pregunta, todos, comprension)
        if semanticas:
            candidatos = [c for c, _, _ in semanticas]
            ventanas = [(a, b) for _, a, b in semanticas]
            ctx.diagnostico["lectura_semantica"] = [
                {"chunk_id": c.chunk.chunk_id, "texto": c.chunk.texto_fuente[a:b]} for c, a, b in semanticas]
        else:
            ventanas = [_ventana_pertinente(m, ctx.pregunta, c.chunk.texto_fuente, limite,
                                            ctx.pregunta_usuario or None, comprension)
                        for c in candidatos]
        # El contexto recuperado resuelve el tema; la relación que responde el
        # lector es la del turno actual. Un verbo heredado («firma») no debe
        # competir con el que acaba de preguntar el usuario («redacta»).
        pregunta_lectura = ctx.pregunta
        if ctx.pregunta_usuario:
            from ipsis.lenguaje.consultas import terminos_de_contenido

            propios = terminos_de_contenido(ctx.pregunta_usuario, getattr(m, "idioma", None))
            # «¿y en verano?» solo aporta un calificativo: necesita la relación
            # heredada. «¿quién redacta?» trae una relación nueva y «¿si llega
            # dañado?» varios términos propios; sus verbos previos no mandan.
            if getattr(comprension, "intencion", None) or len(propios) > 1:
                pregunta_lectura = ctx.pregunta_usuario
        ctx.diagnostico["pregunta_lectura"] = pregunta_lectura
        lecturas = m.lector.leer(pregunta_lectura, [texto[a:b] for texto, (a, b) in zip(
            (c.chunk.texto_fuente for c in candidatos), ventanas)])
        # offsets de la ventana -> offsets del pasaje completo
        ctx.lecturas = [
            lec.model_copy(update={"inicio": lec.inicio + ventanas[lec.indice_pasaje][0],
                                   "fin": lec.fin + ventanas[lec.indice_pasaje][0]})
            for lec in lecturas
        ]
        ctx.diagnostico["lecturas"] = [
            {"chunk_id": candidatos[lec.indice_pasaje].chunk.chunk_id, "texto": lec.texto,
             "prob_respuesta": round(lec.prob_respuesta, 4), "s_qa": round(lec.s_qa, 4)}
            for lec in ctx.lecturas
        ]
        if perfil is not None and perfil.cascada.concordancia:
            ctx.discordancia = hay_discordancia(ctx.lecturas)
            if ctx.discordancia:
                ctx.diagnostico["advertencias"].append(t("runtime.reader_disagreement"))
        mejor = max(ctx.lecturas, key=lambda lec: (lec.s_qa, -lec.indice_pasaje))
        if not mejor.texto or mejor.s_qa <= 0:
            return
        chunk = candidatos[mejor.indice_pasaje].chunk
        if ctx.pregunta_usuario:
            from ipsis.lenguaje.respuestas import completar_tramo

            a, b = ventanas[mejor.indice_pasaje]
            ini_completa, fin_completa = completar_tramo(
                ctx.pregunta_usuario, chunk.texto_fuente[a:b], mejor.inicio - a, mejor.fin - a,
                getattr(m, "idioma", None))
            ini_completa, fin_completa = ini_completa + a, fin_completa + a
            if (ini_completa, fin_completa) != (mejor.inicio, mejor.fin):
                ctx.diagnostico["tramo_completado"] = {
                    "original": mejor.texto, "inicio_original": mejor.inicio, "fin_original": mejor.fin,
                }
                mejor = mejor.model_copy(update={"inicio": ini_completa, "fin": fin_completa,
                                                  "texto": chunk.texto_fuente[ini_completa:fin_completa]})
        ini, fin = oracion_que_contiene(chunk.texto_fuente, mejor.inicio, mejor.fin)
        ctx.evidencia_lector = EvidenceSpan(
            doc_id=chunk.doc_id,
            chunk_id=chunk.chunk_id,
            texto=chunk.texto_fuente[ini:fin],
            offset_inicio=chunk.offset_inicio + ini,
            offset_fin=chunk.offset_inicio + fin,
            seccion_path=seccion_de(chunk, chunk.offset_inicio + ini),
            score=mejor.s_qa,
        )
        ctx.respuesta_exacta = {
            "chunk_id": chunk.chunk_id,
            "texto": mejor.texto,
            "offset_inicio": chunk.offset_inicio + mejor.inicio,
            "offset_fin": chunk.offset_inicio + mejor.fin,
        }


__all__ = ["EtapaLectura", "hay_discordancia", "oracion_que_contiene", "seccion_de"]
