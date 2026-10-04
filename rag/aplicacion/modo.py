"""Modo de ejecución del servicio (desarrollo o producción) y acceso a ``/admin``.

Todo sale de variables de entorno, para que un VPS se configure sin tocar el
proyecto:

- ``RAG_MODO``: ``produccion`` (por defecto) o ``desarrollo``;
- ``RAG_ADMIN_TOKEN``: activa ``/admin`` (al menos 32 caracteres);
- ``RAG_PROXY_CONFIABLE``: IPs del proxy (p. ej. Caddy) cuyos ``X-Forwarded-*`` se aceptan;
- ``RAG_ADMIN_IPS``: IPs permitidas en ``/admin`` (opcional);
- ``RAG_DOCS=1``: ``/docs`` también en producción; ``RAG_DEMO=1``: ``/widget/demo.html``
  también en producción;
- ``RAG_URL_FUENTE``: enlace «Código fuente» (AGPL §13).
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from typing import Mapping

MODOS = ("produccion", "desarrollo")
LARGO_MINIMO_TOKEN = 32
URL_FUENTE_POR_DEFECTO = "https://github.com/Claudiobiovision/rag-extractivo"


def _lista(valor: str | None) -> tuple[str, ...]:
    return tuple(v.strip() for v in (valor or "").split(",") if v.strip())


@dataclass(frozen=True)
class ModoServicio:
    modo: str = "produccion"
    token_admin: str | None = field(default=None, repr=False)
    proxy_confiable: tuple[str, ...] = ()
    admin_ips: tuple[str, ...] = ()
    docs: bool = False  # RAG_DOCS=1: /docs también en producción
    demo: bool = False  # RAG_DEMO=1: /widget/demo.html también en producción
    url_fuente: str = URL_FUENTE_POR_DEFECTO

    @property
    def desarrollo(self) -> bool:
        return self.modo == "desarrollo"

    @property
    def docs_activos(self) -> bool:
        return self.desarrollo or self.docs

    @property
    def demo_activa(self) -> bool:
        return self.desarrollo or self.demo

    @property
    def admin_activo(self) -> bool:
        return bool(self.token_admin) and len(self.token_admin) >= LARGO_MINIMO_TOKEN

    @property
    def problemas(self) -> list[str]:
        """Configuración que impide lo que el usuario quiso activar."""
        salida = []
        if self.token_admin and len(self.token_admin) < LARGO_MINIMO_TOKEN:
            salida.append(f"RAG_ADMIN_TOKEN tiene {len(self.token_admin)} caracteres; se necesitan "
                          f"{LARGO_MINIMO_TOKEN} o más: /admin queda apagado")
        return salida


def modo_servicio(modo: str | None = None, entorno: Mapping[str, str] | None = None) -> ModoServicio:
    entorno = os.environ if entorno is None else entorno
    modo = (modo or entorno.get("RAG_MODO") or "produccion").strip().lower()
    if modo not in MODOS:
        raise ValueError(f"modo desconocido {modo!r}: usa produccion o desarrollo")
    return ModoServicio(
        modo=modo,
        token_admin=entorno.get("RAG_ADMIN_TOKEN") or None,
        proxy_confiable=_lista(entorno.get("RAG_PROXY_CONFIABLE")),
        admin_ips=_lista(entorno.get("RAG_ADMIN_IPS")),
        docs=entorno.get("RAG_DOCS") == "1",
        demo=entorno.get("RAG_DEMO") == "1",
        url_fuente=entorno.get("RAG_URL_FUENTE") or URL_FUENTE_POR_DEFECTO,
    )


def generar_token() -> str:
    """Token aleatorio (43 caracteres URL-safe) para /admin."""
    return secrets.token_urlsafe(32)


__all__ = ["LARGO_MINIMO_TOKEN", "MODOS", "ModoServicio", "generar_token", "modo_servicio"]
