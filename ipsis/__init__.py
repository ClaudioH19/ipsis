"""API pública básica de :mod:`rag`."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ipsis")
except PackageNotFoundError:  # checkout sin instalar
    __version__ = "0+local"

__all__ = ["__version__"]
