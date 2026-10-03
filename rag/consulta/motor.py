"""Orquestador tipado del flujo de consulta, independiente del transporte."""
from __future__ import annotations

import time
from typing import Any

from rag.consulta.etapas.politica import verificar_premisa_candidatos, separar_entidades_ausentes
from rag.consulta.contexto import ContextoConsulta
from rag.nucleo.contratos import (
    AbstentionPolicy,
    AnswerExtractor,
    EvidenceVerifier,
    IntentClassifier,
    ResponseRenderer,
    Retriever,
)
from rag.nucleo.esquemas import (
    AssistantResult,
    AssistantState,
    EvidenceSpan,
    FiltroEntidad,
    QueryAnalysis,
    QueryDiagnostic,
    RetrievalCandidate,
)
from rag.consulta.etapas.redaccion import construir_mensaje_abstencion
from rag.consulta.etapas.conversacional import respuesta_conversacional

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
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k debe ser mayor que cero")
        if max_fragmentos_adicionales < 0:
            raise ValueError("max_fragmentos_adicionales no puede ser negativo")
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

    def _diagnostico(self, **valores: Any) -> dict[str, Any]:
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
        self._validar_listo()
        self.retriever.calentar()

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
        return self.retriever.recuperar(consulta, self.top_k)

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
    ) -> AssistantResult:
        estados_http = {
            AssistantState.RESPUESTA_DIRECTA: "ok",
            AssistantState.RELACIONADO: "relacionado",
            AssistantState.CONVERSACIONAL: "conversacional",
            AssistantState.SIN_RESPUESTA: "sin_respuesta",
        }
        contrato = {
            "estado": estados_http[estado],
            "nivel_servicio": "normal",
            "respuesta": mensaje,
            "plan": plan,
            "fragmentos": fragmentos_http or [],
            "confianza": confianza,
            "latencia_ms": latencia_ms,
        }
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

    def _abstener(
        self,
        motivo: str,
        confianza: dict[str, Any],
        latencia_ms: int,
        *,
        entidad_texto: str | None = None,
        diagnostico: dict[str, Any] | None = None,
    ) -> AssistantResult:
        return self._resultado(
            estado=AssistantState.SIN_RESPUESTA,
            motivo=motivo,
            mensaje=construir_mensaje_abstencion(
                motivo,
                entidad_texto,
                self.plantillas,
            ),
            confianza=confianza,
            latencia_ms=latencia_ms,
            plan="sin_respuesta",
            diagnostico=diagnostico,
        )

    def respuesta_conversacional(self, categoria: str, pregunta: str = "") -> str:
        return respuesta_conversacional(categoria, pregunta, self.plantillas)

    def consultar(self, pregunta: str, id_sesion: str) -> AssistantResult:
        from contextlib import ExitStack

        from rag.lenguaje.entidades import usar_idioma, usar_perfil

        with ExitStack() as contexto:
            if self.perfil is not None:
                contexto.enter_context(usar_perfil(self.perfil))
            if self.idioma is not None:
                contexto.enter_context(usar_idioma(self.idioma))
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
    """Cascada vigente (layered_v1), en orden."""
    from rag.consulta.etapas.analisis import EtapaAnalisis
    from rag.consulta.etapas.conversacional import EtapaConversacional
    from rag.consulta.etapas.filtros import EtapaFiltros
    from rag.consulta.etapas.politica import EtapaPolitica
    from rag.consulta.etapas.recuperacion import EtapaRecuperacion, EtapaSenales
    from rag.consulta.etapas.redaccion import EtapaRedaccion
    from rag.consulta.etapas.seleccion import EtapaEvidencia
    from rag.consulta.etapas.verificacion import EtapaVerificacion

    clases = [EtapaConversacional, EtapaAnalisis, EtapaSenales, EtapaFiltros, EtapaRecuperacion,
              EtapaPolitica, EtapaEvidencia, EtapaRedaccion, EtapaVerificacion]
    return [clase(motor) for clase in clases]


__all__ = ["Motor", "MotorNoListo", "MotorSaturado", "etapas_por_defecto"]
