# routers/__init__.py
from .usuarios import router as usuarios_router
from .ejercicios import router as ejercicios_router
from .rutinas import router as rutinas_router
from .asignaciones import router as asignaciones_router
from .usuarios import entrenadores_router

__all__ = [
    "usuarios_router",
    "ejercicios_router",
    "rutinas_router",
    "asignaciones_router",
]
