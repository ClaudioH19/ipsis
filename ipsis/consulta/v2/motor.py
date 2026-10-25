"""Recuperación y lectura mapeada, sin veto léxico ni certificación por QA."""
from __future__ import annotations

import time
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from ipsis.consulta.errores import MotorNoListo, MotorSaturado
from ipsis.consulta.salida import construir_resultado
from ipsis.nucleo.esquemas import AssistantState, EvidenceSpan, QueryAnalysis, QueryDiagnostic
from ipsis.nucleo.lectura import ContextoLectura, CopiaFuente
from ipsis.nucleo.documentos import ReferenciaFuente
from ipsis.nucleo.traza import ejecutar_modelo_con_traza, recuperar_con_traza, traza_actual
from ipsis.consulta.v2.resultados import preparar_resultados
from ipsis.consulta.v2.reranking import preparar_vistas, puntuar_progresivo
from ipsis.consulta.v2.paginacion import RankingsTemporales

LINEA_CLAVE_FUENTES = 3  # cuántas fuentes publicadas reciben línea clave
LINEA_CLAVE_MS_POR_LINEA = 25  # costo medido de codificar una línea (multilingual-e5-small, 6 núcleos)


@dataclass
class _Consulta:
    pregunta: str
    inicio: float = field(default_factory=time.perf_counter)
    variantes: list[str] = field(default_factory=list)
    candidatos: list[Any] = field(default_factory=list)
    pasajes: list[tuple[Any, str]] = field(default_factory=list)
    lecturas: list[Any] = field(default_factory=list)
    contextos_lectura: list[ContextoLectura] = field(default_factory=list)
    destacados: dict[str, list[dict]] = field(default_factory=dict)
    evidencias: list[EvidenceSpan] = field(default_factory=list)
    diagnostico: dict = field(default_factory=lambda: {"etapas": {}, "advertencias": []})

    def estado(self):
        return {"pregunta": self.pregunta, "variantes": list(self.variantes),
                "candidatos": [c.model_dump(mode="json") for c in self.candidatos],
                "pasajes": [{"chunk_id": c.chunk.chunk_id, "texto": t} for c, t in self.pasajes],
                "evidencias": [e.model_dump(mode="json") for e in self.evidencias],
                "lecturas": [l.model_dump(mode="json") for l in self.lecturas],
                "contextos_lectura": [c.model_dump(mode="json") for c in self.contextos_lectura],
                "destacados": deepcopy(self.destacados),
                "diagnostico": deepcopy(self.diagnostico)}


class MotorV2:
    """Implementa la frontera de motor sin heredar la cascada de v1."""

    pipeline = "v2"
    etapas_efectivas = ("cortesia", "preparacion", "recuperacion", "contexto", "reranking", "lectura", "evidencia", "redaccion")
    abstencion_calibrada = False

    def __init__(self, *, retriever=None, verificador=None, idioma=None, perfil=None, plantillas=None,
                 control_admision=None, top_k=None, opciones=None, reranker=None, lector=None,
                 buscador_media=None, opciones_media=None):
        if top_k is not None and top_k < 1:
            raise ValueError("top_k debe ser positivo")
        self.retriever, self.verificador = retriever, verificador
        self.idioma, self.perfil_instalacion = idioma, perfil
        self.plantillas = plantillas or {}
        self.control_admision = control_admision
        from ipsis.configuracion.esquemas import PipelineV2Config

        self.opciones = PipelineV2Config.model_validate(opciones or {}).model_dump()
        self.top_k = self.opciones["resultados_n"] if top_k is None else top_k
        self.reranker, self.lector = reranker, lector
        # Carril multimedia (fichas de media/): opcional y siempre después de publicar las fuentes de documentos.
        self.buscador_media = buscador_media
        self.opciones_media = {"presupuesto_ms": 150, **(opciones_media or {})}
        self.backend = type(retriever).__name__
        self.metadatos_auditoria = {}
        self._selector_linea = None  # ADR 0013: se crea al primer uso, con el codificador del recuperador
        self._rankings = RankingsTemporales()

    def _validar_listo(self):
        if self.retriever is None or self.verificador is None:
            raise MotorNoListo("motor v2 sin componentes configurados")

    def calentar(self):
        self._validar_listo()
        self.retriever.calentar()
        for modelo in (self.reranker, self.lector):
            if modelo is not None:
                modelo.calentar()

    def cerrar(self):
        self._rankings.limpiar()
        cerrar = getattr(self.retriever, "cerrar", None)
        if callable(cerrar):
            cerrar()

    def n_chunks(self):
        self._validar_listo()
        return self.retriever.n_chunks()

    def inventario_entidades(self):
        self._validar_listo()
        return self.retriever.inventario_entidades()

    def respuesta_conversacional(self, categoria, pregunta=""):
        respuestas = self.plantillas.get("conversacional", {}).get("respuestas", {})
        valor = respuestas.get(categoria, "")
        return valor if isinstance(valor, str) else next(iter(valor), "")

    @contextmanager
    def _etapa(self, nombre, ctx):
        from ipsis.nucleo.progreso import informar

        informar(nombre)
        traza = traza_actual()
        evento = traza.agregar("etapa", nombre=nombre, estado="iniciada", entrada=ctx.estado()) if traza else None
        inicio = time.perf_counter()
        try:
            yield
        except Exception as exc:
            if evento is not None:
                evento.update(estado="error", error=type(exc).__name__)
            raise
        else:
            if evento is not None:
                evento["estado"] = "completada"
        finally:
            ms = int((time.perf_counter() - inicio) * 1000)
            ctx.diagnostico["etapas"][f"{nombre}_ms"] = ms
            if evento is not None:
                evento.update(duracion_ms=ms, salida=ctx.estado())

    def consultar(self, pregunta, id_sesion):
        return self.consultar_con_presupuesto(pregunta, id_sesion)

    def consultar_con_presupuesto(self, pregunta, id_sesion, deadline_ms=None):
        inicio = time.perf_counter()
        return self._admitir(lambda: self._consultar(pregunta, id_sesion, inicio, deadline_ms))

    def _limite(self, inicio, deadline_ms=None):
        return inicio + max(0, self._presupuesto(deadline_ms) - 150) / 1000

    def _presupuesto(self, deadline_ms=None):
        presupuesto = self.opciones["presupuesto_consulta_ms"]
        if deadline_ms is not None:
            if deadline_ms < 1:
                raise ValueError("deadline_ms debe ser positivo")
            presupuesto = min(presupuesto, deadline_ms)
        return presupuesto

    def _rerank(self, ctx, limite):
        ctx.candidatos, ctx.diagnostico["reranking_progresivo"] = puntuar_progresivo(
            ctx.candidatos, ctx.pregunta, self.reranker, self.opciones, limite=limite,
            reloj=time.perf_counter,
            estimado_ms=ctx.diagnostico.get("reranking_progresivo", {}).get("estimado_ms_por_pasaje"))
        ctx.diagnostico["rerank"] = [{"chunk_id": c.chunk.chunk_id, "score": c.score}
            for c in ctx.candidatos if c.signals.reranker_score is not None]


    def continuar(self, pregunta, id_sesion, cursor, deadline_ms=None):
        inicio = time.perf_counter()
        limite = self._limite(inicio, deadline_ms)

        def preparar(ctx, restantes):
            ctx.inicio = inicio
            ctx.diagnostico["etapas"] = {}
            ctx.candidatos = [c for c, _ in restantes]
            textos = {c.chunk.chunk_id: t for c, t in restantes}
            if self.reranker is not None and any(c.signals.reranker_score is None for c in ctx.candidatos):
                with self._etapa("reranking", ctx):
                    self._rerank(ctx, limite)
            else:
                self._rerank(ctx, limite)  # Actualizar contadores; no ejecuta modelos.
            return [(c, textos[c.chunk.chunk_id]) for c in ctx.candidatos]

        def publicar():
            ctx, elegidos, eventos, offset, siguiente, reutilizada = self._rankings.obtener(
                pregunta, id_sesion, cursor, preparar=preparar)
            ctx.inicio = inicio
            if reutilizada:
                ctx.diagnostico["etapas"] = {}
                d = ctx.diagnostico["reranking_progresivo"]
                d["puntuados_al_crear_pagina"] = d["puntuados_esta_pagina"]
                d["puntuados_esta_pagina"], d["lotes"] = 0, []
            ctx.diagnostico["paginacion"] = {"offset": offset, "ranking_reutilizado": True,
                "pagina_reutilizada": reutilizada, "modo": "progresivo"}
            ctx.diagnostico["presupuestos"]["presupuesto_aplicado_ms"] = self._presupuesto(deadline_ms)
            resultado = self._publicar(ctx, elegidos, eventos)
            self._anadir_linea_clave(resultado, pregunta, limite)
            return self._con_cursor(resultado, siguiente if resultado.evidencias else None)
        return self._admitir(publicar)

    @staticmethod
    def _con_cursor(resultado, siguiente):
        resultado.contrato_http.update(continuation=siguiente, has_more=siguiente is not None)
        resultado.diagnostico["contrato_http"] = resultado.contrato_http
        return resultado

    def _admitir(self, ejecutar):
        self._validar_listo()
        traza = traza_actual()
        if traza is not None:
            traza.agregar("consulta", pipeline=self.pipeline, entorno=self.metadatos_auditoria)
        admitido = self.control_admision is None or self.control_admision.intentar_admitir()
        if traza is not None:
            traza.agregar("admision", estado="admitida" if admitido else "rechazada")
        if not admitido:
            raise MotorSaturado("límite de concurrencia alcanzado")
        try:
            return ejecutar()
        finally:
            if self.control_admision is not None:
                self.control_admision.liberar()

    def _consultar(self, pregunta, id_sesion, inicio, deadline_ms):
        ctx = _Consulta(pregunta=pregunta, inicio=inicio)
        from ipsis.lenguaje.voz import categoria_cortesia, respuesta_fija, voz_del_widget

        with self._etapa("cortesia", ctx):
            ayuda = respuesta_fija(pregunta, getattr(self.idioma, "codigo", "en"))
            categoria = None if ayuda else categoria_cortesia(pregunta, self.plantillas)
        if categoria or ayuda:
            from ipsis.consulta.variantes import elegir

            if categoria:
                banco = voz_del_widget(getattr(self.idioma, "codigo", "en"))["messages"]
                mensaje = elegir(categoria, banco[categoria], pregunta)
            else:
                categoria, mensaje = "help", ayuda
            return construir_resultado(
                estado=AssistantState.CONVERSACIONAL, motivo=f"conversacional:{categoria}",
                mensaje=mensaje,
                confianza={"top1": 0.0, "margen": 0.0, "acuerdo_bm25": None},
                latencia_ms=round((time.perf_counter() - inicio) * 1000),
                plan="conversacional", diagnostico=ctx.diagnostico,
            )
        limite = self._limite(inicio, deadline_ms)
        ctx.diagnostico["presupuestos"] = dict(self.opciones)
        ctx.diagnostico["presupuestos"]["presupuesto_aplicado_ms"] = self._presupuesto(deadline_ms)
        with self._etapa("preparacion", ctx):
            ctx.variantes = [" ".join(pregunta.split())]
            if self.idioma is not None and self.opciones.get("corregir_erratas", True):
                from ipsis.lenguaje.ortografia import correcciones, corregir

                cambios = correcciones(pregunta, self.idioma, self.retriever.estadisticas_lexico())
                if cambios:
                    ctx.diagnostico["ortografia"] = cambios
                    variante = " ".join(corregir(pregunta, cambios).split())
                    if variante != ctx.variantes[0]:
                        ctx.variantes.append(variante)
        with self._etapa("recuperacion", ctx):
            total = self.opciones["recuperar_n"]
            ctx.variantes = ctx.variantes[:total]
            conjuntos = []
            for i, variante in enumerate(ctx.variantes):
                cuota = total // len(ctx.variantes) + (i < total % len(ctx.variantes))
                consulta = QueryAnalysis(pregunta_original=pregunta, pregunta_normalizada=ctx.variantes[0],
                                        contexto={"pregunta_recuperacion": variante})
                conjuntos.append(recuperar_con_traza(self.retriever, consulta, cuota,
                                                    origen="principal" if i == 0 else "ortografia"))
            # Una variante ortográfica no suma votos a un mismo chunk. Se intercala
            # el ranking de las variantes sin modificar los scores de cada búsqueda.
            vistos = set()
            for rango in range(max((len(cs) for cs in conjuntos), default=0)):
                for candidatos in conjuntos:
                    if rango < len(candidatos):
                        c = candidatos[rango]
                        if c.chunk.chunk_id not in vistos:
                            ctx.candidatos.append(c)
                            vistos.add(c.chunk.chunk_id)
            ctx.diagnostico["candidatos"] = [{"chunk_id": c.chunk.chunk_id, "score": c.score,
                "signals": c.signals.model_dump(mode="json"), "inicio": c.chunk.texto_fuente[:90]}
                for c in ctx.candidatos]
        originales = list(ctx.candidatos)
        with self._etapa("contexto", ctx):
            ampliar = getattr(self.retriever, "ampliar_contextos", None)
            if ampliar is not None:
                ctx.candidatos, ctx.diagnostico["expansiones"] = ampliar(
                    ctx.candidatos, self.opciones.get("max_caracteres_contexto", 12000))
        ctx.candidatos = preparar_vistas(originales, ctx.candidatos)
        with self._etapa("reranking", ctx):
            unicos, claves, duplicados = [], {}, {}
            for candidato in ctx.candidatos:
                ch = candidato.chunk
                clave = (ch.doc_id, ch.version, tuple(ch.seccion_path), ch.texto_fuente)
                if clave in claves:
                    duplicados.setdefault(claves[clave], []).append(ch.chunk_id)
                else:
                    claves[clave] = ch.chunk_id
                    unicos.append(candidato)
            ctx.candidatos = unicos
            if duplicados:
                ctx.diagnostico["duplicados"] = duplicados
            self._rerank(ctx, limite)
        with self._etapa("lectura", ctx):
            limite_contexto = self.opciones.get("max_caracteres_contexto", 12000)
            # Light no tiene lector, pero sí debe mostrar resultados recuperados.
            n = max(self.top_k, self.opciones["leer_m"] if self.lector is not None else 0)
            ctx.pasajes = [(c, c.chunk.texto_fuente[:limite_contexto]) for c in ctx.candidatos[:n] if c.chunk.texto_fuente.strip()]
            for candidato, texto in ctx.pasajes:
                ch = candidato.chunk
                preparado = ch.metadata.get("contexto_lectura")
                if preparado is not None:
                    contexto = ContextoLectura.model_validate(preparado)
                else:
                    contexto = ContextoLectura(texto=ch.texto_fuente, copias=[CopiaFuente(
                        inicio=0, fin=len(ch.texto_fuente), referencia=ReferenciaFuente(
                            element_id=ch.metadata.get("element_id", ch.chunk_id),
                            offset_inicio=ch.offset_inicio, offset_fin=ch.offset_fin,
                            localizador="texto_extraido"))])
                ctx.contextos_lectura.append(contexto.recortar(limite_contexto))
            ctx.diagnostico["senales"] = {"contextos": [{"chunk_id": c.chunk.chunk_id,
                "caracteres_fuente": len(c.chunk.texto_fuente), "caracteres_leidos": len(t),
                "truncado": len(t) < len(c.chunk.texto_fuente),
                "formato_lectura": "campos-1" if c.chunk.metadata.get("contexto_lectura") else "literal",
                "caracteres_modelo": len(ctx.contextos_lectura[i].texto),
                "lectura_truncada": len(ctx.contextos_lectura[i].texto) < len(
                    c.chunk.metadata.get("contexto_lectura", {}).get("texto", c.chunk.texto_fuente)),
                "supuestos": ctx.contextos_lectura[i].supuestos} for i, (c, t) in enumerate(ctx.pasajes)]}
            if any(c["truncado"] or c["lectura_truncada"] for c in ctx.diagnostico["senales"]["contextos"]):
                ctx.diagnostico["advertencias"].append("contexto truncado por presupuesto de caracteres")
            if self.lector is not None and ctx.pasajes and time.perf_counter() < limite:
                ctx.lecturas = ejecutar_modelo_con_traza("lector", pregunta,
                    [c.texto for c in ctx.contextos_lectura[:self.opciones["leer_m"]]], self.lector.leer)
                n_leidos = min(len(ctx.pasajes), self.opciones["leer_m"])
                if len(ctx.lecturas) != n_leidos or {l.indice_pasaje for l in ctx.lecturas} != set(range(n_leidos)):
                    raise ValueError("lector no devolvió una lectura por pasaje")
                for lec in ctx.lecturas:
                    texto = ctx.contextos_lectura[lec.indice_pasaje].texto
                    if not (0 <= lec.inicio <= lec.fin <= len(texto)) or texto[lec.inicio:lec.fin] != lec.texto:
                        raise ValueError("lector devolvió texto u offsets ajenos a su contexto")
                ctx.diagnostico["lecturas"] = [{"chunk_id": ctx.pasajes[l.indice_pasaje][0].chunk.chunk_id,
                    "texto": l.texto, "prob_respuesta": l.prob_respuesta, "s_qa": l.s_qa,
                    "referencias": ctx.contextos_lectura[l.indice_pasaje].referencias_span(l.inicio, l.fin),
                    "uso": "destacado_no_confianza_de_respuesta"} for l in ctx.lecturas]
            elif self.lector is not None and ctx.pasajes:
                ctx.diagnostico["advertencias"].append("lector optativo omitido por presupuesto")
        todos, eventos = preparar_resultados(
            ctx.candidatos, self.retriever, limite=self.opciones["max_caracteres_resultado"],
            vecinos=self.opciones["vecinos_contexto"], cantidad=len(ctx.candidatos))
        # Las ventanas se fijan una vez. Solo el orden aún no publicado puede cambiar.
        cursor = self._rankings.guardar(pregunta, id_sesion, ctx, todos, eventos, self.top_k)
        ctx.diagnostico["paginacion"] = {"offset": 0, "ranking_reutilizado": False, "modo": "progresivo"}
        resultado = self._publicar(ctx, todos[:self.top_k], eventos)
        self._anadir_multimedia(resultado, ctx, limite)
        self._anadir_forma(resultado)
        self._anadir_linea_clave(resultado, pregunta, limite)
        return self._con_cursor(resultado, cursor if resultado.evidencias else None)

    def _anadir_forma(self, resultado):
        """Describe la forma de la primera página (``forma_resultados``) para que el widget elija mensaje y disposición.

        Solo si ``v2.presentation.enabled``; apagada no deja ninguna clave. No cambia qué se publica ni su orden
        (ADR 0001, ``ipsis/consulta/v2/forma.py``). Solo en la primera página: ``continuar`` no la llama."""
        presentacion = self.opciones["presentacion"]
        if not presentacion["activo"] or not resultado.evidencias:
            return
        from ipsis.consulta.v2.forma import forma_de_pagina, margen, margen_claro_efectivo, relacion

        rutas = {e.chunk_id: list(e.seccion_path) for e in resultado.evidencias}
        fuentes = [{"score": f["score"], "tipo_puntaje": f["tipo_puntaje"], "doc_id": f["doc_id"],
                    "alcance": f["alcance"], "seccion_path": rutas.get(f["chunk_id"], [])}
                   for f in resultado.contrato_http["fragmentos"]]
        perfil = self.perfil_instalacion.perfil if self.perfil_instalacion else None
        forma = forma_de_pagina(fuentes, activo=True, margen_claro=margen_claro_efectivo(presentacion, perfil))
        resultado.contrato_http["forma_resultados"] = forma
        resultado.diagnostico["forma_resultados"] = {"forma": forma, "margen": margen(fuentes),
                                                      "relacion": relacion(fuentes)}

    def _anadir_linea_clave(self, resultado, pregunta, limite):
        """Marca en las primeras fuentes la línea más cercana a la pregunta (``linea_clave``, ADR 0013).

        Solo con ``v2.presentation.key_line``. Corre después de publicar y sin cambiar qué se publica ni su orden: cada
        fuente gana un campo opcional con offsets del documento. Si no queda presupuesto, las fuentes restantes se
        quedan sin línea y se avisa; una falla del codificador nunca tumba la consulta."""
        presentacion = self.opciones["presentacion"]
        if not presentacion["linea_clave"] or not resultado.evidencias:
            return
        codificador = getattr(self.retriever, "codificador", None)
        vector_consulta = getattr(self.retriever, "vector_consulta", None)
        if codificador is None or vector_consulta is None:
            return
        from ipsis.consulta.v2.linea_clave import SelectorLineaClave, tramos_de_linea

        if self._selector_linea is None or self._selector_linea.codificador is not codificador:
            self._selector_linea = SelectorLineaClave(codificador)
        inicio = time.perf_counter()
        fragmentos = resultado.contrato_http["fragmentos"]
        marcadas = omitidas = 0
        try:
            vector = vector_consulta(" ".join(pregunta.split()))
            for evidencia, fragmento in list(zip(resultado.evidencias, fragmentos, strict=True))[:LINEA_CLAVE_FUENTES]:
                nuevas = self._selector_linea.lineas_nuevas(evidencia.texto)
                # Con todas las líneas en caché el costo es de milisegundos y no compite con el reranker por el tiempo.
                if nuevas and time.perf_counter() + nuevas * LINEA_CLAVE_MS_POR_LINEA / 1000 > limite:
                    omitidas += 1
                    continue
                seleccion = self._selector_linea.seleccionar(
                    vector, evidencia.texto, base=evidencia.offset_inicio, margen=presentacion["margen_linea_clave"])
                if seleccion is not None:
                    fragmento["linea_clave"] = seleccion
                    marcadas += 1
        except Exception as error:  # noqa: BLE001 -- la línea clave es opcional
            resultado.diagnostico.setdefault("advertencias", []).append(f"línea clave falló: {type(error).__name__}")
            return
        if omitidas:
            resultado.diagnostico.setdefault("advertencias", []).append("línea clave omitida por presupuesto")
        resultado.diagnostico["linea_clave"] = {"marcadas": marcadas, "omitidas_por_presupuesto": omitidas,
                                                "ms": round((time.perf_counter() - inicio) * 1000, 1)}

    def _anadir_multimedia(self, resultado, ctx, limite):
        """Busca fichas multimedia para la pregunta y las deja en el contrato interno (``multimedia``).

        Corre después de publicar las fuentes y sin cambiarlas; si no queda presupuesto se omite y se avisa. Solo
        en la primera página: ``continuar`` no la llama."""
        if self.buscador_media is None:
            return
        presupuesto_s = self.opciones_media["presupuesto_ms"] / 1000
        if limite - time.perf_counter() < presupuesto_s:
            resultado.diagnostico.setdefault("advertencias", []).append("carril multimedia omitido por presupuesto")
            return
        inicio = time.perf_counter()
        try:
            fichas = self.buscador_media.buscar(ctx.variantes)
        except Exception as error:  # noqa: BLE001 -- el carril nunca tumba una consulta de documentos
            resultado.diagnostico.setdefault("advertencias", []).append(f"carril multimedia falló: {type(error).__name__}")
            return
        resultado.contrato_http["multimedia"] = fichas
        resultado.diagnostico["multimedia"] = {"publicadas": len(fichas),
                                                "ms": round((time.perf_counter() - inicio) * 1000, 1)}

    def _publicar(self, ctx, elegidos, eventos):
        perfil = self.perfil_instalacion
        with self._etapa("evidencia", ctx):
            # QA propone spans dentro de cada pasaje, sin ordenar fuentes ni
            # certificar que un porcentaje aislado responde toda la pregunta.
            ctx.diagnostico["contextos_resultados"] = eventos
            por_publicado = {c.chunk.chunk_id: c.chunk for c, _ in elegidos}
            if any(e["truncado"] for e in ctx.diagnostico["contextos_resultados"]):
                ctx.diagnostico["advertencias"].append("contexto de resultado truncado por presupuesto")
            publicados = {c.chunk.chunk_id for c, _ in elegidos}
            positivas = [l for l in ctx.lecturas if l.texto and l.s_qa > 0]
            preferida = max(positivas, key=lambda l: (l.s_qa, -l.indice_pasaje)) if positivas else None
            ctx.diagnostico["decision"] = {
                "seleccion_pasajes": "ranking", "qa_desplaza_pasajes": False,
                "pasaje_principal": elegidos[0][0].chunk.chunk_id if elegidos else None,
                "preferencia_qa": ctx.pasajes[preferida.indice_pasaje][0].chunk.chunk_id if preferida else None,
                "confianza_respuesta_calculada": False, "modo": "fuentes_ordenadas"}
            for lec in ctx.lecturas:
                candidato, texto = ctx.pasajes[lec.indice_pasaje]
                refs = ctx.contextos_lectura[lec.indice_pasaje].referencias_span(lec.inicio, lec.fin)
                # Un mapa más compacto puede llegar más lejos que el prefijo
                # fuente publicado. No destacar celdas omitidas por ese límite.
                publicado = por_publicado.get(candidato.chunk.chunk_id)
                refs = [r for r in refs if publicado is not None and
                        publicado.offset_inicio <= r["offset_inicio"] <= r["offset_fin"] <= publicado.offset_fin]
                if lec.texto and lec.s_qa > 0 and refs and candidato.chunk.chunk_id in publicados:
                    ctx.destacados[candidato.chunk.chunk_id] = [{
                        "tipo": "posible_fragmento", "referencias": refs}]
            ctx.evidencias = [EvidenceSpan(doc_id=c.chunk.doc_id, chunk_id=c.chunk.chunk_id, texto=texto,
                offset_inicio=c.chunk.offset_inicio, offset_fin=c.chunk.offset_inicio + len(texto),
                seccion_path=c.chunk.seccion_path, score=c.score) for c, texto in elegidos]
            validas, errores = self.verificador.verificar(ctx.evidencias, [c for c, _ in elegidos])
            if not validas:
                ctx.evidencias, ctx.destacados = [], {}
                ctx.diagnostico["advertencias"].extend(errores)
            ctx.diagnostico["evidencias"] = [e.model_dump(mode="json") for e in ctx.evidencias]
            ctx.diagnostico["regla"] = "recuperado" if ctx.evidencias else "sin_evidencia"
        with self._etapa("redaccion", ctx):
            bloques = []
            if not ctx.evidencias:
                estado = AssistantState.SIN_RESPUESTA
                from ipsis.recursos.mensajes import t

                mensaje = getattr(self.idioma, "interfaz", {}).get("search_empty") or t("app.search_empty")
                bloques = [{"tipo": "mensaje", "texto": mensaje}]
            else:
                estado = AssistantState.RELACIONADO
                from ipsis.recursos.mensajes import t

                intro = getattr(self.idioma, "interfaz", {}).get("ranked_sources")
                bloques.append({"tipo": "mensaje", "texto": intro.format(n=len(ctx.evidencias)) if intro
                                else t("app.ranked_sources", n=len(ctx.evidencias))})
                por_chunk = {c.chunk.chunk_id: c for c in ctx.candidatos}
                for evidencia in ctx.evidencias:
                    titulo = por_chunk[evidencia.chunk_id].chunk.doc_titulo
                    bloque = {"tipo": "pasaje", "texto": evidencia.texto,
                              "cita": titulo, "chunk_id": evidencia.chunk_id}
                    if evidencia.chunk_id in ctx.destacados:
                        bloque["destacados"] = ctx.destacados[evidencia.chunk_id]
                    bloques.append(bloque)
                mensaje = "\n\n".join((f"{i}. " if b.get("cita") else "") + b["texto"] +
                    (f" {b['cita']}." if b.get("cita") else "") for i, b in enumerate(bloques))
        por_chunk = {c.chunk.chunk_id: c.chunk for c, _ in elegidos}
        por_candidato = {c.chunk.chunk_id: c for c, _ in elegidos}
        fragmentos = [{"chunk_id": e.chunk_id, "doc_titulo": por_chunk[e.chunk_id].doc_titulo,
            "seccion": " > ".join(e.seccion_path), "version": por_chunk[e.chunk_id].version,
            "pagina": por_chunk[e.chunk_id].pagina, "offset_inicio": e.offset_inicio,
            "offset_fin": e.offset_fin, "texto": e.texto, "score": e.score, "doc_id": e.doc_id,
            "rango": por_chunk[e.chunk_id].metadata["rango_resultado"],
            "archivo_fuente": por_chunk[e.chunk_id].metadata["ventana_resultado"].get("archivo_fuente"),
            "alcance": por_chunk[e.chunk_id].metadata.get("alcance"),
            "rasgos": por_chunk[e.chunk_id].metadata.get("rasgos_distintivos"),
            "offset_coincidencia_inicio": por_chunk[e.chunk_id].metadata["ventana_resultado"]["coincidencia_inicio"],
            "offset_coincidencia_fin": por_chunk[e.chunk_id].metadata["ventana_resultado"]["coincidencia_fin"],
            "truncado": por_chunk[e.chunk_id].metadata["ventana_resultado"]["truncado"],
            "bloques_fuente": por_chunk[e.chunk_id].metadata.get("bloques_presentacion", []),
            "tipo_puntaje": "logit_reranker" if por_candidato[e.chunk_id].signals.reranker_score is not None
                            else "recuperacion"} for e in ctx.evidencias]
        diagnostico = QueryDiagnostic(backend=self.backend, pipeline=self.pipeline,
                                     perfil=perfil.perfil if perfil else None, **ctx.diagnostico).model_dump(mode="python")
        return construir_resultado(estado=estado, motivo=ctx.diagnostico["regla"], mensaje=mensaje,
            # Campos históricos: cero significa no calculado en este pipeline.
            confianza={"top1": 0.0, "margen": 0.0, "acuerdo_bm25": None},
            latencia_ms=int((time.perf_counter() - ctx.inicio) * 1000),
            plan="zona_gris" if ctx.evidencias else "sin_respuesta",
            diagnostico=diagnostico, evidencias=ctx.evidencias, fragmentos_http=fragmentos,
            bloques=bloques, modo_respuesta="fuentes_ordenadas")
