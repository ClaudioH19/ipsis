"""Traza observable de una petición, aislada por contexto y apagada por defecto.

No reconstruye decisiones ni repite búsquedas. Conserva copias del estado que
vieron las etapas durante la ejecución, sin identificadores de sesión.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class TrazaConsulta:
    consulta_id: str = field(default_factory=lambda: uuid4().hex)
    inicio: float = field(default_factory=time.perf_counter)
    eventos: list[dict[str, Any]] = field(default_factory=list)

    def agregar(self, tipo: str, **datos: Any) -> dict[str, Any]:
        evento = {"orden": len(self.eventos) + 1, "tipo": tipo,
                  "desde_inicio_ms": round((time.perf_counter() - self.inicio) * 1000, 3),
                  **deepcopy(datos)}
        self.eventos.append(evento)
        return evento


_actual: ContextVar[TrazaConsulta | None] = ContextVar("traza_consulta", default=None)


def traza_actual() -> TrazaConsulta | None:
    return _actual.get()


@contextmanager
def capturar_traza(activo: bool = True):
    traza = TrazaConsulta() if activo else None
    token = _actual.set(traza)
    try:
        yield traza
    finally:
        _actual.reset(token)


def estado_etapa(ctx) -> dict[str, Any]:
    """Estado relevante, sin volcar el contexto de sesión del analizador."""
    diagnostico = ctx.resultado.diagnostico if ctx.resultado is not None else ctx.diagnostico
    salida = {
        "pregunta": ctx.pregunta,
        "pregunta_usuario": ctx.pregunta_usuario or None,
        "intencion": ctx.consulta.intencion if ctx.consulta is not None else None,
        "pregunta_normalizada": ctx.consulta.pregunta_normalizada if ctx.consulta is not None else None,
        "candidatos": [{"chunk_id": c.chunk.chunk_id, "score": c.score,
                         "signals": c.signals.model_dump(mode="json")} for c in ctx.candidatos],
        "descartados_rerank": [c.chunk.chunk_id for c in ctx.descartados_rerank],
        "evidencias": [e.model_dump(mode="json") for e in ctx.evidencias],
        "decision": asdict(ctx.decision) if ctx.decision is not None else None,
        "salto_modelos": ctx.saltar_modelos,
        "diagnostico": {k: v for k, v in diagnostico.items() if k != "contrato_http"},
    }
    if ctx.resultado is not None:
        salida["resultado"] = {"estado": ctx.resultado.estado.value, "motivo": ctx.resultado.motivo,
                               "respuesta": ctx.resultado.mensaje_usuario}
    return deepcopy(salida)


def recuperar_con_traza(retriever, consulta, limite: int, *, filtro=None, origen: str):
    """Registra cada búsqueda real, incluso las dirigidas y de alternativas."""
    traza = traza_actual()
    evento = None
    marca = time.perf_counter()
    if traza is not None:
        evento = traza.agregar(
            "recuperacion", origen=origen, estado="iniciada", limite=limite,
            pregunta_densa=consulta.pregunta_original,
            pregunta_recuperacion=consulta.contexto.get("pregunta_recuperacion", consulta.pregunta_original),
            filtro=filtro.model_dump(mode="json") if filtro is not None else None,
            modo=getattr(retriever, "modo", None),
        )
    try:
        candidatos = (retriever.recuperar(consulta, limite) if filtro is None
                      else retriever.recuperar(consulta, limite, filtro=filtro))
    except Exception as exc:
        if evento is not None:
            evento.update(estado="error", error=type(exc).__name__)
        raise
    else:
        if evento is not None:
            evento.update(estado="completada", candidatos=[c.model_dump(mode="json") for c in candidatos])
        return candidatos
    finally:
        if evento is not None:
            evento["duracion_ms"] = round((time.perf_counter() - marca) * 1000, 3)


def ejecutar_modelo_con_traza(tipo: str, pregunta: str, pasajes: list[str], operacion):
    """Entradas exactas del reranker/lector y sus salidas originales."""
    traza = traza_actual()
    if traza is None:
        return operacion(pregunta, pasajes)
    evento = traza.agregar("modelo", modelo=tipo, estado="iniciada", pregunta=pregunta, pasajes=pasajes)
    marca = time.perf_counter()
    try:
        salida = operacion(pregunta, pasajes)
    except Exception as exc:
        evento.update(estado="error", error=type(exc).__name__)
        raise
    else:
        evento.update(estado="completada",
                      salida=[v.model_dump(mode="json") if hasattr(v, "model_dump") else float(v) for v in salida])
        return salida
    finally:
        evento["duracion_ms"] = round((time.perf_counter() - marca) * 1000, 3)
