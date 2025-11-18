# schemas/__init__.py
from schemas.routine import EstadoRutinaEnum, NivelDificultadEnum, ObjetivoEnum, EjercicioDiaRutinaCreate, \
    DiaRutinaCreate, ParametrosRutinaCreate, RutinaUpdate, EjercicioDiaRutinaUpdate, EjercicioDiaRutinaResponse, \
    DiaRutinaResponse, RutinaDetailResponse, RutinaListResponse, RutinaGeneradaPorIAResponse, GuardarRutinaResponse, \
    EditarRutinaResponse, EliminarRutinaResponse, RutinaConValidacion


__all__ = [
    # Enums
    "EstadoRutinaEnum",
    "NivelDificultadEnum",
    "ObjetivoEnum",

    # Requests
    "EjercicioDiaRutinaCreate",
    "DiaRutinaCreate",
    "ParametrosRutinaCreate",
    "RutinaUpdate",
    "EjercicioDiaRutinaUpdate",

    # Responses
    "EjercicioDiaRutinaResponse",
    "DiaRutinaResponse",
    "RutinaDetailResponse",
    "RutinaListResponse",
    "RutinaGeneradaPorIAResponse",
    "GuardarRutinaResponse",
    "EditarRutinaResponse",
    "EliminarRutinaResponse",

    # Validaciones complejas
    "RutinaConValidacion",
]
