"""Registro de consultas y su auditoría (``ipsis auditar``).

El registro es un JSONL en ``.ipsis/registros/consultas.jsonl``, apagado por
defecto (privacidad: ``asistente.yaml::registro.activo``). Cada línea guarda
la pregunta, el estado, la regla, las señales y las evidencias con sus
offsets; no guarda la sesión ni la IP. Solo lo escribe el servicio.

``auditar_registro`` comprueba que cada evidencia registrada siga siendo
literal: el texto guardado debe estar en esos offsets del corpus vigente.
"""
from __future__ import annotations

import json
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ipsis.configuracion import rutas

VERSION_REGISTRO = 1


class SinRegistro(FileNotFoundError):
    """No hay registro de consultas que auditar."""


def entrada_de_registro(pregunta: str, resultado) -> dict[str, Any]:
    """Línea del registro para un ``AssistantResult``."""
    d = resultado.diagnostico or {}
    contrato = d.get("contrato_http") or {}
    evidencias = [{"doc_id": e.doc_id, "chunk_id": e.chunk_id, "offset_inicio": e.offset_inicio,
                   "offset_fin": e.offset_fin, "texto": e.texto} for e in resultado.evidencias]
    exacta = contrato.get("respuesta_exacta")
    if exacta is not None:  # el tramo trae chunk_id; el doc_id sale de su evidencia
        doc_id = next((e["doc_id"] for e in evidencias if e["chunk_id"] == exacta.get("chunk_id")), None)
        exacta = {**exacta, "doc_id": doc_id}
    return {
        "version": VERSION_REGISTRO,
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pregunta": pregunta,
        "estado": contrato.get("estado", resultado.estado.value),
        "regla": d.get("regla"),
        "motivo": resultado.motivo,
        "perfil": d.get("perfil"),
        "senales": d.get("senales_politica") or {},
        "tono": d.get("tono"),
        "plantillas": list(d.get("plantillas") or []),
        "evidencias": evidencias,
        "respuesta_exacta": exacta,
    }


class RegistroConsultas:
    """Agrega una línea por consulta; seguro entre hilos del servicio."""

    def __init__(self, ruta: str | Path = rutas.REGISTRO_CONSULTAS) -> None:
        self.ruta = Path(ruta)
        self._candado = threading.Lock()

    def registrar(self, pregunta: str, resultado) -> None:
        linea = json.dumps(entrada_de_registro(pregunta, resultado), ensure_ascii=False)
        with self._candado:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with self.ruta.open("a", encoding="utf-8") as archivo:
                archivo.write(linea + "\n")


def registro_del_proyecto(cfg_dominio: dict) -> RegistroConsultas | None:
    """El registro si ``registro.activo`` es verdadero; si no, ``None`` (no se escribe nada)."""
    activo = bool((cfg_dominio.get("registro") or {}).get("activo"))
    return RegistroConsultas() if activo else None


# --- auditoría ----------------------------------------------------------------------------
@dataclass(frozen=True)
class ProblemaEvidencia:
    linea: int
    doc_id: str | None
    offset_inicio: int | None
    offset_fin: int | None
    motivo: str  # "alterada" | "documento_ausente" | "fuera_de_rango" | "tramo_alterado"
    detalle: str


@dataclass
class ReporteAuditoria:
    ruta: Path
    consultas: int = 0
    por_estado: Counter = field(default_factory=Counter)
    por_regla: Counter = field(default_factory=Counter)
    por_tono: Counter = field(default_factory=Counter)
    evidencias: int = 0
    problemas: list[ProblemaEvidencia] = field(default_factory=list)
    lineas_invalidas: list[int] = field(default_factory=list)
    desde: datetime | None = None
    hasta: datetime | None = None
    fuera_de_rango: int = 0  # consultas excluidas por --desde/--hasta
    sin_fecha: list[int] = field(default_factory=list)  # líneas sin fecha legible (excluidas si se filtra)

    @property
    def ok(self) -> bool:
        return not self.problemas and not self.lineas_invalidas


def _verificar(linea: int, doc_id, inicio, fin, texto, textos: dict[str, str],
               motivo_alterado: str = "alterada") -> ProblemaEvidencia | None:
    if doc_id not in textos:
        return ProblemaEvidencia(linea, doc_id, inicio, fin, "documento_ausente",
                                 "el documento ya no está en el corpus vigente")
    documento = textos[doc_id]
    if not (isinstance(inicio, int) and isinstance(fin, int) and 0 <= inicio <= fin <= len(documento)):
        return ProblemaEvidencia(linea, doc_id, inicio, fin, "fuera_de_rango",
                                 f"offsets fuera del documento (largo {len(documento)})")
    if documento[inicio:fin] != texto:
        return ProblemaEvidencia(linea, doc_id, inicio, fin, motivo_alterado,
                                 f"registrado «{_corto(texto)}», en el corpus «{_corto(documento[inicio:fin])}»")
    return None


def _corto(texto: str | None, n: int = 60) -> str:
    texto = (texto or "").replace("\n", " ")
    return texto if len(texto) <= n else texto[: n - 1] + "…"


class FechaInvalida(ValueError):
    """``--desde``/``--hasta`` no es una fecha ISO."""


def interpretar_fecha(texto: str, *, fin_del_dia: bool = False) -> datetime:
    """``AAAA-MM-DD`` o fecha y hora ISO 8601; sin zona horaria se toma UTC.

    Con ``fin_del_dia`` una fecha sola cubre el día completo (``--hasta`` inclusivo).
    """
    from datetime import timedelta

    valor = (texto or "").strip()
    try:
        if len(valor) == 10:
            momento = datetime.fromisoformat(valor).replace(tzinfo=timezone.utc)
            return momento + timedelta(days=1) - timedelta(microseconds=1) if fin_del_dia else momento
        momento = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as e:
        raise FechaInvalida(f"fecha inválida {texto!r}: usa AAAA-MM-DD o AAAA-MM-DDTHH:MM (ISO 8601)") from e
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _fecha_entrada(entrada: dict) -> datetime | None:
    try:
        return interpretar_fecha(str(entrada["fecha"]))
    except (KeyError, FechaInvalida):
        return None


def auditar_registro(ruta: str | Path = rutas.REGISTRO_CONSULTAS, *, desde: datetime | None = None,
                     hasta: datetime | None = None) -> ReporteAuditoria:
    """Resume estados y reglas del registro y verifica cada evidencia contra el corpus vigente.

    Solo lectura: no usa modelos ni el índice; parsea los documentos vigentes.
    Con ``desde``/``hasta`` (inclusivos) solo cuenta las consultas de ese rango.
    """
    from ipsis.ingesta.ingesta import parsear_corpus

    ruta = Path(ruta)
    if not ruta.is_file():
        raise SinRegistro(ruta)
    textos = {d.doc_id: d.texto_completo for d in parsear_corpus(rutas.DOCUMENTOS)}
    if desde is not None and hasta is not None and desde > hasta:
        raise FechaInvalida("--desde es posterior a --hasta")
    reporte = ReporteAuditoria(ruta, desde=desde, hasta=hasta)
    filtrar = desde is not None or hasta is not None
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
        if not linea.strip():
            continue
        try:
            entrada = json.loads(linea)
            evidencias = entrada.get("evidencias") or []
        except (json.JSONDecodeError, AttributeError):
            reporte.lineas_invalidas.append(numero)
            continue
        if filtrar:
            fecha = _fecha_entrada(entrada)
            if fecha is None:
                reporte.sin_fecha.append(numero)
                continue
            if (desde is not None and fecha < desde) or (hasta is not None and fecha > hasta):
                reporte.fuera_de_rango += 1
                continue
        reporte.consultas += 1
        reporte.por_estado[entrada.get("estado") or "?"] += 1
        reporte.por_regla[entrada.get("regla") or "—"] += 1
        reporte.por_tono[entrada.get("tono") or "—"] += 1
        for e in evidencias:
            reporte.evidencias += 1
            problema = _verificar(numero, e.get("doc_id"), e.get("offset_inicio"), e.get("offset_fin"),
                                  e.get("texto"), textos)
            if problema:
                reporte.problemas.append(problema)
        exacta = entrada.get("respuesta_exacta")
        if exacta:
            reporte.evidencias += 1
            problema = _verificar(numero, exacta.get("doc_id"), exacta.get("offset_inicio"),
                                  exacta.get("offset_fin"), exacta.get("texto"), textos, "tramo_alterado")
            if problema:
                reporte.problemas.append(problema)
    return reporte


__all__ = ["FechaInvalida", "ProblemaEvidencia", "RegistroConsultas", "ReporteAuditoria", "SinRegistro", "auditar_registro",
           "entrada_de_registro", "interpretar_fecha", "registrar_admin", "registro_del_proyecto"]


def registrar_admin(ip: str | None, accion: str, claves: list[str] | None = None) -> None:
    """Auditoría de ``/admin`` en ``.ipsis/registros/admin.jsonl``: quién cambió qué
    (fecha, IP, acción y claves). Nunca guarda el token ni los valores."""
    ruta = Path(rutas.REGISTRO_CONSULTAS).with_name("admin.jsonl")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    linea = json.dumps({"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ip": ip,
                        "accion": accion, "claves": sorted(claves or [])}, ensure_ascii=False)
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write(linea + "\n")
