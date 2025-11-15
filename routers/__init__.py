# routers/__init__.py

from .usuarios import router as usuarios_router
from .usuarios import entrenadores_router
from .ejercicios import router as ejercicios_router
from .rutinas import router as rutinas_router
from .asignaciones import router as asignaciones_router
from .resenas import router as resenas_router
from .mensajes import router as mensajes_router
from .pagos import router as pagos_router

# 🚀 CORRECTO: este es tu archivo real
from .ia import router as ia_router

from .progresion import router as progresion_router

__all__ = [
    "usuarios_router",
    "entrenadores_router",
    "ejercicios_router",
    "rutinas_router",
    "asignaciones_router",
    "resenas_router",
    "mensajes_router",
    "pagos_router",
    "ia_router",             # ← correcto
    "progresion_router",
]
