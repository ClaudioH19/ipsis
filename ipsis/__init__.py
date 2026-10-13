"""Metadatos del paquete ipsis; la integración pública usa CLI y HTTP."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ipsis")
except PackageNotFoundError:  # checkout sin instalar
    __version__ = "0+local"

__all__ = ["__version__"]
