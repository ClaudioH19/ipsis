"""Orquestador tipado del flujo de consulta, independiente del transporte."""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rag.abstencion import verificar_premisa_candidatos, separar_entidades_ausentes
from rag.componentes import (
    AbstentionPolicy,
    AnswerExtractor,
    EvidenceVerifier,
    IntentClassifier,
    RegistroComponentes,
    ResponseRenderer,
    Retriever,
)
from rag.esquemas import (
    AssistantResult,
    AssistantState,
    EvidenceSpan,
    FiltroEntidad,
    QueryAnalysis,
    QueryDiagnostic,
    RetrievalCandidate,
)
from rag.payload import payload_desde_evidencia
from rag.servicio.pipeline import (
    construir_mensaje_abstencion,
    cargar_plantillas,
    detectar_conversacional,
    elegir_plan,
    redactar,
    redactar_zona_gris,
    respuesta_conversacional,
    verificar_fidelidad,
    verificar_respaldo_dato_solicitado,
)

EjecutorLegacy = Callable[[str, str], Any]

_ESTADOS_LEGACY: dict[str, AssistantState] = {
    "ok": AssistantState.RESPUESTA_DIRECTA,
    "relacionado": AssistantState.RELACIONADO,
    "conversacional": AssistantState.CONVERSACIONAL,
    "sin_respuesta": AssistantState.SIN_RESPUESTA,
    "degradado": AssistantState.DEGRADADO,
    "saturado": AssistantState.SATURADO,
}


class MotorNoListo(RuntimeError):
    pass


class MotorSaturado(RuntimeError):
    pass


class Motor:
    """Coordina análisis, recuperación, abstención, evidencia y respuesta."""

    def __init__(
        self,
        ejecutor_legacy: EjecutorLegacy | None = None,
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
        plantillas: dict[str, Any] | None = None,
        configuracion_redaccion: dict[str, Any] | None = None,
        top_k: int = 3,
        max_fragmentos_adicionales: int = 2,
        abstencion_calibrada: bool | None = None,
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
        self.plantillas = plantillas
        self.configuracion_redaccion = configuracion_redaccion
        self.top_k = top_k
        self.max_fragmentos_adicionales = max_fragmentos_adicionales
        self.abstencion_calibrada = (
            politica_abstencion is not None
            if abstencion_calibrada is None
            else abstencion_calibrada
        )
        self._ejecutor_legacy = ejecutor_legacy

    @classmethod
    def desde_configuracion(
        cls,
        cfg: dict[str, Any],
        *,
        cfg_dominio: dict[str, Any] | None = None,
        registro: RegistroComponentes | None = None,
        ruta_plantillas: str | Path | None = None,
    ) -> "Motor":
        """Construye el motor completo desde la selección declarativa.

        Primero valida todos los nombres configurados y solo después crea
        los componentes que participan en consulta. Así un nombre inválido
        falla durante el arranque, incluso si corresponde a otra fase como
        ingesta.
        """
        from rag.configuracion import (
            cargar_dominio,
            config_abstencion,
            config_recuperacion,
            config_redaccion,
            config_servicio,
        )
        from rag.dominio import cargar_perfil
        from rag.registro import registrar_componentes_base
        from rag.servicio.pipeline import ConfiguracionAdmision, ControlAdmision
        from rag.texto_util import cargar_palabras_generales

        componentes = dict(cfg.get("componentes") or {})
        if not componentes:
            raise ValueError("la configuración no define componentes")
        registro = registrar_componentes_base(registro or RegistroComponentes())
        for tipo, nombre in componentes.items():
            if nombre is not None:
                registro.obtener(tipo, nombre)

        cfg_dominio = cfg_dominio or cargar_dominio()
        perfil = cargar_perfil(cfg_dominio["perfil"])
        ruta_textos = Path(ruta_plantillas or "configuracion/textos.yaml").resolve()
        plantillas = cargar_plantillas(ruta_textos, cfg_dominio)
        palabras_generales = cargar_palabras_generales(cfg_dominio.get("idioma", "es"))
        cfg_rec = config_recuperacion(cfg)
        cfg_abs = config_abstencion(cfg, retriever=componentes["retriever"])
        cfg_red = config_redaccion(cfg)
        cfg_srv = config_servicio(cfg)

        retriever = registro.crear(
            "retriever",
            componentes["retriever"],
            recuperacion=cfg_rec,
            qdrant=cfg.get("qdrant", {}),
        )
        analizador = registro.crear("intent_classifier", componentes["intent_classifier"])
        politica = None
        if cfg_abs is not None:
            politica = registro.crear(
                "abstention_policy",
                componentes["abstention_policy"],
                configuracion=cfg_abs,
                inventario_entidades=retriever.inventario_entidades(),
                estadisticas_lexico=retriever.estadisticas_lexico(),
                palabras_generales=palabras_generales,
            )
        extractor = registro.crear(
            "answer_extractor",
            componentes["answer_extractor"],
            limite_caracteres=cfg_red["longitud_maxima_fragmento_chars"],
            metodo=cfg_red["metodo_seleccion"],
            modelo_st=getattr(retriever, "codificador", None),
            prefijo_query=cfg_rec.get("prefijo_query", ""),
        )
        verificador = registro.crear(
            "evidence_verifier", componentes["evidence_verifier"]
        )
        renderer = registro.crear("response_renderer", componentes["response_renderer"])
        return cls(
            retriever=retriever,
            analizador=analizador,
            politica_abstencion=politica,
            extractor=extractor,
            verificador=verificador,
            renderer=renderer,
            control_admision=ControlAdmision(
                ConfiguracionAdmision(concurrencia_maxima=cfg_srv["concurrencia_maxima"])
            ),
            backend=componentes["retriever"],
            perfil=perfil,
            plantillas=plantillas,
            configuracion_redaccion=cfg_red,
            top_k=cfg_rec["top_k"],
            max_fragmentos_adicionales=(
                cfg_abs.get("capa_b_premisa", {}).get("max_fragmentos_adicionales", 2)
                if cfg_abs is not None
                else 2
            ),
            abstencion_calibrada=(
                cfg_abs is not None
                and "sin_calibrar" not in str(cfg_abs.get("version", ""))
            ),
        )

    @classmethod
    def desde_ejecutor_legacy(cls, ejecutor: EjecutorLegacy) -> "Motor":
        if not callable(ejecutor):
            raise TypeError("ejecutor debe ser invocable")
        return cls(ejecutor_legacy=ejecutor)

    def _adaptar_legacy(self, pregunta: str, id_sesion: str) -> AssistantResult:
        respuesta = self._ejecutor_legacy(pregunta, id_sesion)
        if not hasattr(respuesta, "model_dump"):
            raise TypeError("el ejecutor heredado debe devolver un modelo Pydantic")
        contrato = respuesta.model_dump(mode="python")
        estado_legacy = str(contrato["estado"])
        try:
            estado = _ESTADOS_LEGACY[estado_legacy]
        except KeyError as exc:
            raise ValueError(f"estado heredado desconocido: {estado_legacy}") from exc
        evidencias = [
            EvidenceSpan(
                doc_id=fragmento.get("doc_id") or fragmento["doc_titulo"],
                chunk_id=fragmento["chunk_id"],
                texto=fragmento["texto"],
                offset_inicio=fragmento["offset_inicio"],
                offset_fin=fragmento["offset_fin"],
                seccion_path=(
                    []
                    if fragmento.get("seccion") in {None, "", "(sin sección)"}
                    else str(fragmento["seccion"]).split(" > ")
                ),
                score=fragmento.get("score"),
            )
            for fragmento in contrato.get("fragmentos", [])
        ]
        diagnostico = self._diagnostico(
            advertencias=["flujo heredado adaptado; diagnóstico limitado"]
        )
        diagnostico["contrato_http"] = contrato
        return AssistantResult(
            estado=estado,
            motivo=f"flujo_heredado:{estado_legacy}",
            mensaje_usuario=str(contrato.get("respuesta") or ""),
            evidencias=evidencias,
            puede_reintentar=estado in {AssistantState.DEGRADADO, AssistantState.SATURADO},
            confianza=dict(contrato.get("confianza") or {}),
            diagnostico=diagnostico,
        )

    def _diagnostico(self, **valores: Any) -> dict[str, Any]:
        valores.setdefault("backend", self.backend)
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

    @staticmethod
    def _fragmentos_http(
        evidencias: list[EvidenceSpan],
        candidatos: list[RetrievalCandidate],
    ) -> list[dict[str, Any]]:
        por_chunk = {candidato.chunk.chunk_id: candidato for candidato in candidatos}
        salida = []
        for evidencia in evidencias:
            chunk = por_chunk[evidencia.chunk_id].chunk
            salida.append({
                "chunk_id": evidencia.chunk_id,
                "doc_titulo": chunk.doc_titulo,
                "seccion": " > ".join(evidencia.seccion_path) or "(sin sección)",
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
        if self.perfil is None:
            return self._consultar_en_contexto(pregunta, id_sesion)
        from rag.reglas_extraccion import usar_perfil

        with usar_perfil(self.perfil):
            return self._consultar_en_contexto(pregunta, id_sesion)

    def _consultar_en_contexto(self, pregunta: str, id_sesion: str) -> AssistantResult:
        if self._ejecutor_legacy is not None:
            return self._adaptar_legacy(pregunta, id_sesion)

        inicio = time.perf_counter()
        latencia = lambda: int((time.perf_counter() - inicio) * 1000)
        categoria = detectar_conversacional(pregunta, self.plantillas)
        if categoria is not None:
            confianza = {"top1": 0.0, "margen": 0.0, "acuerdo_bm25": None}
            return self._resultado(
                estado=AssistantState.CONVERSACIONAL,
                motivo=f"conversacional:{categoria}",
                mensaje=self.respuesta_conversacional(categoria, pregunta),
                confianza=confianza,
                latencia_ms=latencia(),
                plan="conversacional",
                diagnostico={"etapas": {"conversacional_ms": latencia()}},
            )

        self._validar_listo()
        if self.control_admision is not None and not self.control_admision.intentar_admitir():
            raise MotorSaturado("límite de concurrencia alcanzado")

        diagnostico = self._diagnostico()
        try:
            marca = time.perf_counter()
            consulta = self._analizar(pregunta, id_sesion)
            diagnostico["etapas"]["analisis_ms"] = int((time.perf_counter() - marca) * 1000)

            marca = time.perf_counter()
            senales = self.retriever.estimar_confianza(consulta, max(self.top_k, 2))
            confianza = self._confianza(senales)
            diagnostico["etapas"]["confianza_ms"] = int((time.perf_counter() - marca) * 1000)
            diagnostico["senales"] = senales.model_dump(mode="python")

            if self.politica_abstencion is None:
                return self._abstener("generico", confianza, latencia(), diagnostico=diagnostico)
            decision_dominio = self.politica_abstencion.decidir_dominio(consulta, senales)
            if decision_dominio is not None:
                diagnostico["decision"] = decision_dominio.__dict__
                return self._abstener("fuera_dominio", confianza, latencia(), diagnostico=diagnostico)

            marca = time.perf_counter()
            candidatos = self._completar_premisa(consulta, self._recuperar(consulta))
            diagnostico["etapas"]["recuperacion_ms"] = int((time.perf_counter() - marca) * 1000)
            diagnostico["candidatos"] = [
                {
                    "chunk_id": candidato.chunk.chunk_id,
                    "score": candidato.score,
                    "signals": candidato.signals.model_dump(mode="python"),
                }
                for candidato in candidatos
            ]
            if not candidatos:
                return self._abstener("sin_fragmentos", confianza, latencia(), diagnostico=diagnostico)

            decision = self.politica_abstencion.decidir(consulta, senales, candidatos)
            diagnostico["decision"] = decision.__dict__
            if decision.abstiene:
                motivo_mensaje = "premisa" if decision.motivo == "premisa" else "generico"
                return self._abstener(
                    motivo_mensaje,
                    confianza,
                    latencia(),
                    entidad_texto=decision.entidad_texto,
                    diagnostico=diagnostico,
                )

            marca = time.perf_counter()
            evidencias = self.extractor.extraer(consulta, candidatos)
            validas, errores = self.verificador.verificar(evidencias, candidatos)
            diagnostico["etapas"]["evidencia_ms"] = int((time.perf_counter() - marca) * 1000)
            if not validas:
                diagnostico["advertencias"].extend(errores)
                return self._abstener("guardia", confianza, latencia(), diagnostico=diagnostico)
            diagnostico["evidencias"] = [
                evidencia.model_dump(mode="python") for evidencia in evidencias
            ]

            por_chunk = {c.chunk.chunk_id: c for c in candidatos}
            payloads = [
                payload_desde_evidencia(evidencia, por_chunk[evidencia.chunk_id].chunk)
                for evidencia in evidencias
            ]
            if decision.resultado == "relacionado":
                texto = redactar_zona_gris(
                    payloads,
                    plantillas=self.plantillas,
                    cfg_redaccion=self.configuracion_redaccion,
                )
                estado = AssistantState.RELACIONADO
                plan = "zona_gris"
            else:
                respaldo_solicitud = verificar_respaldo_dato_solicitado(
                    pregunta,
                    payloads,
                )
                if not respaldo_solicitud.fiel:
                    diagnostico["advertencias"].extend(respaldo_solicitud.motivos)
                    return self._abstener(
                        "guardia",
                        confianza,
                        latencia(),
                        diagnostico=diagnostico,
                    )
                texto = redactar(
                    elegir_plan(pregunta, payloads),
                    payloads,
                    plantillas=self.plantillas,
                    cfg_redaccion=self.configuracion_redaccion,
                )
                estado = AssistantState.RESPUESTA_DIRECTA
                plan = "extractivo"
            fidelidad = verificar_fidelidad(texto, payloads)
            if not fidelidad.fiel:
                diagnostico["advertencias"].extend(fidelidad.motivos)
                return self._abstener("guardia", confianza, latencia(), diagnostico=diagnostico)

            return self._resultado(
                estado=estado,
                motivo=decision.motivo,
                mensaje=texto,
                confianza=confianza,
                latencia_ms=latencia(),
                plan=plan,
                evidencias=evidencias,
                fragmentos_http=self._fragmentos_http(evidencias, candidatos),
                diagnostico=diagnostico,
            )
        finally:
            if self.control_admision is not None:
                self.control_admision.liberar()


__all__ = ["Motor", "MotorNoListo", "MotorSaturado"]
