"""Orquestador tipado del flujo de consulta, independiente del transporte."""
from __future__ import annotations

import time
from typing import Any

from ipsis.recursos.mensajes import t
from ipsis.consulta.etapas.politica import verificar_premisa_candidatos, separar_entidades_ausentes
from ipsis.consulta.contexto import ContextoConsulta
from ipsis.nucleo.contratos import (
    AbstentionPolicy,
    AnswerExtractor,
    EvidenceVerifier,
    IntentClassifier,
    ResponseRenderer,
    Retriever,
)
from ipsis.nucleo.esquemas import (
    AssistantResult,
    AssistantState,
    EvidenceSpan,
    FiltroEntidad,
    QueryAnalysis,
    QueryDiagnostic,
    RetrievalCandidate,
    RetrievalSignals,
)
from ipsis.consulta.etapas.redaccion import construir_mensaje_abstencion
from ipsis.consulta.etapas.conversacional import respuesta_conversacional

class MotorNoListo(RuntimeError):
    pass


class MotorSaturado(RuntimeError):
    pass


class Motor:
    """Coordina análisis, recuperación, abstención, evidencia y respuesta."""

    def __init__(
        self,
        *,
        retriever: Retriever | None = None,
        analizador: IntentClassifier | None = None,
        politica_abstencion: AbstentionPolicy | None = None,
        extractor: AnswerExtractor | None = None,
        verificador: EvidenceVerifier | None = None,
        renderer: ResponseRenderer | None = None,
        control_admision: Any = None,
        backend: str | None = None,
        perfil: Any = None,
        idioma: Any = None,
        plantillas: dict[str, Any] | None = None,
        configuracion_redaccion: dict[str, Any] | None = None,
        top_k: int = 3,
        max_fragmentos_adicionales: int = 2,
        abstencion_calibrada: bool | None = None,
        etapas: list | None = None,
        reranker: Any = None,
        lector: Any = None,
    ) -> None:
        if top_k < 1:
            raise ValueError(t("runtime.positive", name="top_k"))
        if max_fragmentos_adicionales < 0:
            raise ValueError(t("runtime.not_negative", name="max_fragmentos_adicionales"))
        self.retriever = retriever
        self.analizador = analizador
        self.politica_abstencion = politica_abstencion
        self.extractor = extractor
        self.verificador = verificador
        self.renderer = renderer
        self.control_admision = control_admision
        self.backend = backend or (
            type(retriever).__name__ if retriever is not None else "sin_configurar"
        )
        self.perfil = perfil
        self.idioma = idioma
        self.plantillas = plantillas
        self.configuracion_redaccion = configuracion_redaccion
        self.top_k = top_k
        self.max_fragmentos_adicionales = max_fragmentos_adicionales
        self.abstencion_calibrada = (
            politica_abstencion is not None
            if abstencion_calibrada is None
            else abstencion_calibrada
        )
        self.etapas = etapas if etapas is not None else etapas_por_defecto(self)
        self.perfil_instalacion = None
        self.reranker = reranker
        self.lector = lector
        from ipsis.consulta.variantes import SelectorVariantes

        from ipsis.consulta.seguimiento import MemoriaConversacion

        self.seguimiento = MemoriaConversacion()
        from ipsis.lenguaje.intenciones import construir_respaldo

        self.respaldo_intenciones = construir_respaldo(idioma, retriever)
        from ipsis.consulta.alternativas import ConfigAlternativas

        # Postura ante una abstención (ADR 0008) y taxonomía para la categoría de la pregunta.
        self.alternativas = ConfigAlternativas()
        self.taxonomia: dict | None = None
        self.selector_variantes = SelectorVariantes(tono=(plantillas or {}).get("tono") or "cordial",
                                                    fija=(plantillas or {}).get("variedad") == "fija")

    def _diagnostico(self, **valores: Any) -> dict[str, Any]:
        from ipsis.consulta.variantes import usadas

        tono, plantillas = usadas()
        if tono is not None:
            valores["tono"] = tono
            valores["plantillas"] = [*(valores.get("plantillas") or []),
                                     *(p for p in plantillas if p not in (valores.get("plantillas") or []))]
        valores.setdefault("backend", self.backend)
        perfil = getattr(self, "perfil_instalacion", None)
        valores.setdefault("perfil", perfil.perfil if perfil is not None else None)
        return QueryDiagnostic(**valores).model_dump(mode="python")

    def _validar_listo(self) -> None:
        if (
            self.retriever is None
            or self.analizador is None
            or self.extractor is None
            or self.verificador is None
        ):
            raise MotorNoListo("motor sin componentes configurados")

    def _analizar(self, pregunta: str, id_sesion: str) -> QueryAnalysis:
        return self.analizador.analizar(pregunta, {"id_sesion": id_sesion})

    def calentar(self) -> None:
        """Carga los modelos antes de aceptar tráfico: una falta de modelo se
        detecta al arrancar, no en la primera pregunta."""
        self._validar_listo()
        self.retriever.calentar()
        for modelo in (self.reranker, self.lector):
            calentar = getattr(modelo, "calentar", None)
            if callable(calentar):
                calentar()

    def n_chunks(self) -> int:
        self._validar_listo()
        return self.retriever.n_chunks()

    def inventario_entidades(self) -> set[str]:
        self._validar_listo()
        return self.retriever.inventario_entidades()

    def cerrar(self) -> None:
        """Libera recursos del backend cuando este ofrece cierre explícito."""
        if self.retriever is None:
            return
        cerrar = getattr(self.retriever, "cerrar", None)
        if callable(cerrar):
            cerrar()

    def _recuperar(self, consulta: QueryAnalysis) -> list[RetrievalCandidate]:
        # Con reranker se recuperan más candidatos y él elige los mejores.
        perfil = self.perfil_instalacion
        limite = perfil.cascada.recuperar_n if self.reranker is not None and perfil is not None else self.top_k
        return self.retriever.recuperar(consulta, limite)

    def _completar_premisa(
        self,
        consulta: QueryAnalysis,
        candidatos: list[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        premisa = verificar_premisa_candidatos(consulta, candidatos)
        if not premisa.entidades_ausentes or self.max_fragmentos_adicionales == 0:
            return candidatos
        en_corpus, _ = separar_entidades_ausentes(
            premisa.entidades_ausentes,
            self.retriever.inventario_entidades(),
        )
        vistos = {candidato.chunk.chunk_id for candidato in candidatos}
        agregados = 0
        for entidad in en_corpus:
            if agregados >= self.max_fragmentos_adicionales:
                break
            dirigidos = self.retriever.recuperar(
                consulta,
                1,
                filtro=FiltroEntidad(valor_norm=entidad["valor_norm"]),
            )
            for candidato in dirigidos:
                if candidato.chunk.chunk_id not in vistos:
                    candidatos.append(candidato)
                    vistos.add(candidato.chunk.chunk_id)
                    agregados += 1
                    break
        return candidatos

    @staticmethod
    def _confianza(senales) -> dict[str, Any]:
        return {
            "top1": senales.confianza_top1,
            "margen": senales.margen_top1_top2,
            "acuerdo_bm25": None,
        }

    def _fragmentos_http(
        self,
        evidencias: list[EvidenceSpan],
        candidatos: list[RetrievalCandidate],
    ) -> list[dict[str, Any]]:
        sin_seccion = self.idioma.mensajes.sin_seccion if self.idioma is not None else ""
        por_chunk = {candidato.chunk.chunk_id: candidato for candidato in candidatos}
        salida = []
        for evidencia in evidencias:
            chunk = por_chunk[evidencia.chunk_id].chunk
            salida.append({
                "chunk_id": evidencia.chunk_id,
                "doc_titulo": chunk.doc_titulo,
                "seccion": " > ".join(evidencia.seccion_path) or sin_seccion,
                "version": chunk.version,
                "pagina": chunk.pagina,
                "offset_inicio": evidencia.offset_inicio,
                "offset_fin": evidencia.offset_fin,
                "texto": evidencia.texto,
                "score": evidencia.score if evidencia.score is not None else por_chunk[evidencia.chunk_id].score,
            })
        return salida

    def _resultado(
        self,
        *,
        estado: AssistantState,
        motivo: str,
        mensaje: str,
        confianza: dict[str, Any],
        latencia_ms: int,
        plan: str,
        evidencias: list[EvidenceSpan] | None = None,
        fragmentos_http: list[dict[str, Any]] | None = None,
        diagnostico: dict[str, Any] | None = None,
        respuesta_exacta: dict[str, Any] | None = None,
        bloques: list[dict[str, Any]] | None = None,
    ) -> AssistantResult:
        estados_http = {
            AssistantState.RESPUESTA_DIRECTA: "ok",
            AssistantState.RELACIONADO: "relacionado",
            AssistantState.CONVERSACIONAL: "conversacional",
            AssistantState.SIN_RESPUESTA: "sin_respuesta",
            AssistantState.NECESITA_ACLARACION: "sin_respuesta",
        }
        alternativas = (diagnostico or {}).pop("_alternativas_http", None)
        contrato = {
            "estado": estados_http[estado],
            "nivel_servicio": "normal",
            "respuesta": mensaje,
            # Los párrafos de ``respuesta``; abstenciones y saludos son un solo mensaje.
            "bloques": bloques or [{"tipo": "mensaje", "texto": mensaje}],
            "plan": plan,
            "fragmentos": fragmentos_http or [],
            "confianza": confianza,
            "latencia_ms": latencia_ms,
        }
        nivel = self.nivel_confianza(estado)
        if nivel is not None:
            contrato["nivel_confianza"] = nivel
        if respuesta_exacta is not None:
            contrato["respuesta_exacta"] = respuesta_exacta
        if alternativas:
            contrato["alternativas"] = alternativas
        if estado == AssistantState.CONVERSACIONAL and motivo.startswith("conversacional:"):
            # Para el widget y el avatar: saludo, agradecimiento, despedida o capacidad.
            contrato["categoria_conversacional"] = motivo.split(":", 1)[1]
        detalles = self._diagnostico(**(diagnostico or {}))
        detalles["contrato_http"] = contrato
        return AssistantResult(
            estado=estado,
            motivo=motivo,
            mensaje_usuario=mensaje,
            evidencias=evidencias or [],
            confianza=confianza,
            diagnostico=detalles,
        )

    def nivel_confianza(self, estado: AssistantState) -> str | None:
        """Qué tan segura es la respuesta, por niveles medidos (docs/methodology/
        informal-paraphrases.md, «Confidence and guarantees»):

        - ``alta``: respuesta directa con lector (medium): 96,6 % correcta en 319
          respuestas de los bancos, garantizado ≥ 94 % al 95 %;
        - ``media``: respuesta directa sin lector (light): 85 % correcta;
        - ``baja``: relacionado, el pasaje más cercano sin afirmar que responda;
        - ``None``: abstención, aclaración o conversación (no hay respuesta que medir).

        Sale del estado y del perfil, no de un umbral nuevo: los datos no sostienen
        subniveles dentro de una respuesta directa de medium."""
        if estado == AssistantState.RESPUESTA_DIRECTA:
            return "alta" if self.lector is not None else "media"
        if estado == AssistantState.RELACIONADO:
            return "baja"
        return None

    def _abstener(
        self,
        motivo: str,
        confianza: dict[str, Any],
        latencia_ms: int,
        *,
        entidad_texto: str | None = None,
        diagnostico: dict[str, Any] | None = None,
        alternativas=None,
    ) -> AssistantResult:
        """Resultado ``sin_respuesta``. Con ``alternativas`` (``ResultadoAlternativas``
        con alguna ofrecida), el mensaje sigue con un encabezado fijo del tono y
        cada alternativa como pasaje literal con su cita: el estado no cambia."""
        mensaje = construir_mensaje_abstencion(motivo, entidad_texto, self.plantillas)
        bloques = None
        if alternativas is not None and alternativas.ofrecidas:
            from ipsis.consulta.etapas.redaccion import bloques_alternativas, texto_de_bloques

            bloques = [{"tipo": "mensaje", "texto": mensaje},
                       *bloques_alternativas([a.evidencia for a in alternativas.ofrecidas],
                                             [a.chunk for a in alternativas.ofrecidas],
                                             plantillas=self.plantillas, cfg_redaccion=self.configuracion_redaccion)]
            mensaje = texto_de_bloques(bloques)
            diagnostico = dict(diagnostico or {})
            diagnostico["_alternativas_http"] = self._fragmentos_http(
                [a.evidencia for a in alternativas.ofrecidas],
                [RetrievalCandidate(chunk=a.chunk, signals=RetrievalSignals()) for a in alternativas.ofrecidas])
        return self._resultado(
            estado=AssistantState.SIN_RESPUESTA,
            motivo=motivo,
            mensaje=mensaje,
            confianza=confianza,
            latencia_ms=latencia_ms,
            plan="sin_respuesta",
            diagnostico=diagnostico,
            bloques=bloques,
        )

    def _aclarar(self, motivo: str, confianza: dict[str, Any], latencia_ms: int, *,
                 diagnostico: dict[str, Any] | None = None) -> AssistantResult:
        """Resultado ``necesita_aclaracion``: la pregunta no dice de qué se habla
        (ipsis.lenguaje.aclaracion). En el contrato HTTP es ``sin_respuesta`` con
        ``plan: aclaracion``, para no romper a los clientes que validan el estado."""
        from ipsis.consulta.variantes import elegir

        textos = self.plantillas["abstencion"]
        mensaje = elegir("needs_clarification", list(textos.get("aclaracion") or textos["generico"]), motivo)
        return self._resultado(
            estado=AssistantState.NECESITA_ACLARACION,
            motivo=motivo,
            mensaje=mensaje,
            confianza=confianza,
            latencia_ms=latencia_ms,
            plan="aclaracion",
            diagnostico=diagnostico,
        )

    def respuesta_conversacional(self, categoria: str, pregunta: str = "") -> str:
        return respuesta_conversacional(categoria, pregunta, self.plantillas)

    def consultar(self, pregunta: str, id_sesion: str) -> AssistantResult:
        from contextlib import ExitStack

        from ipsis.lenguaje.entidades import usar_idioma, usar_perfil

        with ExitStack() as contexto:
            if self.perfil is not None:
                contexto.enter_context(usar_perfil(self.perfil))
            if self.idioma is not None:
                contexto.enter_context(usar_idioma(self.idioma))
            from ipsis.consulta.variantes import en_consulta

            contexto.enter_context(en_consulta(self.selector_variantes, id_sesion))
            return self._consultar_en_contexto(pregunta, id_sesion)

    def _ejecutar_etapa(self, etapa, ctx: ContextoConsulta) -> None:
        marca = time.perf_counter()
        etapa.ejecutar(ctx)
        clave = f"{etapa.nombre}_ms"
        ms = int((time.perf_counter() - marca) * 1000)
        ctx.diagnostico.setdefault("etapas", {})[clave] = ms
        if ctx.resultado is not None:
            ctx.resultado.diagnostico.setdefault("etapas", {})[clave] = ms

    def _consultar_en_contexto(self, pregunta: str, id_sesion: str) -> AssistantResult:
        ctx = ContextoConsulta(pregunta=pregunta, id_sesion=id_sesion)
        pendientes = list(self.etapas)
        # Las etapas que no consumen recursos (conversacional) corren antes del
        # control de admisión: un saludo nunca espera ni satura el servicio.
        while pendientes and not pendientes[0].requiere_admision:
            self._ejecutar_etapa(pendientes.pop(0), ctx)
            if ctx.resultado is not None:
                return ctx.resultado

        self._validar_listo()
        if self.control_admision is not None and not self.control_admision.intentar_admitir():
            raise MotorSaturado("límite de concurrencia alcanzado")
        ctx.diagnostico = {**self._diagnostico(), "etapas": dict(ctx.diagnostico.get("etapas", {}))}
        try:
            for etapa in pendientes:
                if ctx.saltar_modelos and getattr(etapa, "usa_modelos", False):
                    continue  # salida temprana: ningún candidato menciona lo que se pregunta
                self._ejecutar_etapa(etapa, ctx)
                if ctx.resultado is not None:
                    return ctx.resultado
            raise RuntimeError("ninguna etapa produjo un resultado")
        finally:
            if self.control_admision is not None:
                self.control_admision.liberar()


def etapas_por_defecto(motor: "Motor") -> list:
    """Etapas del perfil light, en orden (la política decide tras la evidencia)."""
    from ipsis.consulta.etapas.analisis import EtapaAnalisis
    from ipsis.consulta.etapas.conversacional import EtapaConversacional
    from ipsis.consulta.etapas.filtros import EtapaFiltros
    from ipsis.consulta.etapas.politica import EtapaPolitica
    from ipsis.consulta.etapas.recuperacion import EtapaRecuperacion, EtapaSenales
    from ipsis.consulta.etapas.redaccion import EtapaRedaccion
    from ipsis.consulta.etapas.seleccion import EtapaEvidencia
    from ipsis.consulta.etapas.verificacion import EtapaVerificacion

    clases = [EtapaConversacional, EtapaAnalisis, EtapaSenales, EtapaFiltros, EtapaRecuperacion,
              EtapaEvidencia, EtapaPolitica, EtapaRedaccion, EtapaVerificacion]
    return [clase(motor) for clase in clases]


__all__ = ["Motor", "MotorNoListo", "MotorSaturado", "etapas_por_defecto"]
