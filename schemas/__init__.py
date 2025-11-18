# schemas/__init__.py
from .routine import EstadoRutinaEnum, NivelDificultadEnum, ObjetivoEnum, EjercicioDiaRutinaCreate, DiaRutinaCreate, \
    ParametrosRutinaCreate, RutinaUpdate, EjercicioDiaRutinaUpdate, EjercicioDiaRutinaResponse, DiaRutinaResponse, \
    RutinaDetailResponse, RutinaListResponse, RutinaGeneradaPorIAResponse, GuardarRutinaResponse, EditarRutinaResponse, \
    EliminarRutinaResponse, RutinaConValidacion


__all__ = [
    "EstadoRutinaEnum",
    "NivelDificultadEnum",
    "ObjetivoEnum",
    "EjercicioDiaRutinaCreate",
    "DiaRutinaCreate",
    "ParametrosRutinaCreate",
    "RutinaUpdate",
    "EjercicioDiaRutinaUpdate",
    "EjercicioDiaRutinaResponse",
    "DiaRutinaResponse",
    "RutinaDetailResponse",
    "RutinaListResponse",
    "RutinaGeneradaPorIAResponse",
    "GuardarRutinaResponse",
    "EditarRutinaResponse",
    "EliminarRutinaResponse",
    "RutinaConValidacion",
]
