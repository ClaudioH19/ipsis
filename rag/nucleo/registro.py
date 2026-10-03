"""Registro de factories de componentes, separado por tipo.

Permite construir implementaciones por nombre desde la configuración sin que
el núcleo las conozca. Las factories importan sus dependencias pesadas solo al
ejecutarse.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

Factory = Callable[..., Any]


class RegistroComponentes:
    """Registro explícito de factories, separado por tipo de componente."""

    def __init__(self) -> None:
        self._factories: dict[str, dict[str, Factory]] = {}

    @staticmethod
    def _normalizar(valor: str, campo: str) -> str:
        normalizado = valor.strip().lower().replace("-", "_")
        if not normalizado:
            raise ValueError(f"{campo} no puede estar vacío")
        return normalizado

    def registrar(self, tipo: str, nombre: str, factory: Factory, *, reemplazar: bool = False) -> None:
        tipo_n = self._normalizar(tipo, "tipo")
        nombre_n = self._normalizar(nombre, "nombre")
        if not callable(factory):
            raise TypeError("factory debe ser invocable")
        grupo = self._factories.setdefault(tipo_n, {})
        if nombre_n in grupo and not reemplazar:
            raise ValueError(f"componente ya registrado: {tipo_n}/{nombre_n}")
        grupo[nombre_n] = factory

    def obtener(self, tipo: str, nombre: str) -> Factory:
        tipo_n = self._normalizar(tipo, "tipo")
        nombre_n = self._normalizar(nombre, "nombre")
        try:
            return self._factories[tipo_n][nombre_n]
        except KeyError as exc:
            disponibles = self.disponibles(tipo_n)
            raise KeyError(
                f"componente desconocido {tipo_n}/{nombre_n}; disponibles: {disponibles or '(ninguno)'}"
            ) from exc

    def crear(self, tipo: str, nombre: str, /, *args: Any, **kwargs: Any) -> Any:
        return self.obtener(tipo, nombre)(*args, **kwargs)

    def disponibles(self, tipo: str) -> list[str]:
        tipo_n = self._normalizar(tipo, "tipo")
        return sorted(self._factories.get(tipo_n, {}))

    def limpiar(self) -> None:
        """Vacía el registro. Destinado principalmente a aislamiento de tests."""
        self._factories.clear()

    def registrar_mapa(self, tipo: str, factories: dict[str, Factory], *, reemplazar: bool = False) -> None:
        """Registra un conjunto de implementaciones de forma determinista."""
        for nombre in sorted(factories):
            self.registrar(tipo, nombre, factories[nombre], reemplazar=reemplazar)

    def resolver_configuracion(self, seleccion: dict[str, Any]) -> dict[str, Any]:
        """Resuelve una selección declarativa ``tipo -> nombre/opciones``."""
        resultado: dict[str, Any] = {}
        for tipo, especificacion in seleccion.items():
            if especificacion is None:
                resultado[tipo] = None
                continue
            if isinstance(especificacion, str):
                nombre, opciones = especificacion, {}
            elif isinstance(especificacion, dict):
                nombre = especificacion.get("nombre")
                opciones = {k: v for k, v in especificacion.items() if k != "nombre"}
                if not isinstance(nombre, str):
                    raise ValueError(f"configuracion de {tipo} requiere la clave 'nombre'")
            else:
                raise TypeError(f"configuracion de {tipo} debe ser texto, objeto o null")
            resultado[tipo] = self.crear(tipo, nombre, **opciones)
        return resultado


registro_componentes = RegistroComponentes()


def componente(tipo: str, nombre: str, *, reemplazar: bool = False):
    """Decorador para registrar una clase o factory sin importarla desde el core."""
    def decorar(factory: Factory) -> Factory:
        registro_componentes.registrar(tipo, nombre, factory, reemplazar=reemplazar)
        return factory
    return decorar


__all__ = ["Factory", "RegistroComponentes", "componente", "registro_componentes"]
