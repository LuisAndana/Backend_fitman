# Backend_fitman/__init__.py
"""
Inicializador del paquete Backend_fitman.

Objetivo:
- Marcar el repo como paquete Python para permitir imports relativos
  (p. ej. desde routers: `from ..dependencies import get_db`).
- Evitar efectos secundarios al importar: NO traemos submódulos aquí
  para no crear ciclos de importación durante el arranque de FastAPI.
"""

from importlib.metadata import version, PackageNotFoundError

PACKAGE_NAME = "Backend_fitman"
__all__: list[str] = []

# Versión informativa (si no está instalado como paquete, usa "dev")
try:
    __version__ = version(PACKAGE_NAME)
except PackageNotFoundError:
    __version__ = "dev"
