"""Modo de ejecución del servicio (desarrollo o producción) y acceso a ``/admin``.

Todo sale de variables de entorno, para que un VPS se configure sin tocar el
proyecto:

- ``IPSIS_MODE``: ``produccion`` (por defecto) o ``desarrollo``;
- ``IPSIS_ADMIN_TOKEN``: activa ``/admin`` (al menos 32 caracteres);
- ``IPSIS_TRUSTED_PROXY``: IPs del proxy (p. ej. Caddy) cuyos ``X-Forwarded-*`` se aceptan;
- ``IPSIS_ADMIN_IPS``: IPs permitidas en ``/admin`` (opcional);
- ``IPSIS_DOCS=1``: ``/docs`` también en producción; ``IPSIS_DEMO=1``: ``/widget/demo.html``
  también en producción;
- ``IPSIS_SOURCE_URL``: enlace «Código fuente» (AGPL §13).
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from typing import Mapping

MODOS = ("produccion", "desarrollo")
LARGO_MINIMO_TOKEN = 32
URL_FUENTE_POR_DEFECTO = "https://github.com/ClaudioH19/Deterministic-Retrieval-Assistant-Chat"


def _lista(valor: str | None) -> tuple[str, ...]:
    return tuple(v.strip() for v in (valor or "").split(",") if v.strip())


@dataclass(frozen=True)
class ModoServicio:
    modo: str = "produccion"
    token_admin: str | None = field(default=None, repr=False)
    proxy_confiable: tuple[str, ...] = ()
    admin_ips: tuple[str, ...] = ()
    docs: bool = False  # IPSIS_DOCS=1: /docs también en producción
    demo: bool = False  # IPSIS_DEMO=1: /widget/demo.html también en producción
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
            salida.append(f"IPSIS_ADMIN_TOKEN tiene {len(self.token_admin)} caracteres; se necesitan "
                          f"{LARGO_MINIMO_TOKEN} o más: /admin queda apagado")
        if not self.url_fuente.startswith(("https://", "http://")):
            salida.append(f"IPSIS_SOURCE_URL={self.url_fuente!r} no es una URL http(s): /fuente usa "
                          f"{URL_FUENTE_POR_DEFECTO}")
        return salida

    @property
    def fuente(self) -> str:
        """URL del código fuente (AGPL §13); la del repositorio si la configurada no es válida."""
        return self.url_fuente if self.url_fuente.startswith(("https://", "http://")) else URL_FUENTE_POR_DEFECTO


def modo_servicio(modo: str | None = None, entorno: Mapping[str, str] | None = None) -> ModoServicio:
    entorno = os.environ if entorno is None else entorno
    modo = (modo or entorno.get("IPSIS_MODE") or "produccion").strip().lower()
    if modo not in MODOS:
        raise ValueError(f"modo desconocido {modo!r}: usa produccion o desarrollo")
    return ModoServicio(
        modo=modo,
        token_admin=entorno.get("IPSIS_ADMIN_TOKEN") or None,
        proxy_confiable=_lista(entorno.get("IPSIS_TRUSTED_PROXY")),
        admin_ips=_lista(entorno.get("IPSIS_ADMIN_IPS")),
        docs=entorno.get("IPSIS_DOCS") == "1",
        demo=entorno.get("IPSIS_DEMO") == "1",
        url_fuente=entorno.get("IPSIS_SOURCE_URL") or URL_FUENTE_POR_DEFECTO,
    )


def generar_token() -> str:
    """Token aleatorio (43 caracteres URL-safe) para /admin."""
    return secrets.token_urlsafe(32)


__all__ = ["LARGO_MINIMO_TOKEN", "MODOS", "ModoServicio", "generar_token", "modo_servicio"]
