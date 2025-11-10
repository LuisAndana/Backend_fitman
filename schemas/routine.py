# schemas/rutina_schemas.py - Validación de datos con Pydantic

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class EstadoRutinaEnum(str, Enum):
    ACTIVA = "activa"
    INACTIVA = "inactiva"
    COMPLETADA = "completada"
    EN_EDICION = "en_edicion"


class NivelDificultadEnum(str, Enum):
    PRINCIPIANTE = "principiante"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"


class ObjetivoEnum(str, Enum):
    PERDIDA_PESO = "perdida_peso"
    GANANCIA_MUSCULAR = "ganancia_muscular"
    RESISTENCIA = "resistencia"
    FLEXIBILIDAD = "flexibilidad"
    TONIFICACION = "tonificacion"


# ============================================================
# SCHEMAS DE ENTRADA (Requests)
# ============================================================

class EjercicioDiaRutinaCreate(BaseModel):
    """Crear ejercicio dentro de un día de rutina"""
    id_ejercicio: int
    series: int = Field(default=3, ge=1, le=10)
    repeticiones: Optional[int] = Field(default=None, ge=1, le=100)
    rango_repeticiones: Optional[str] = Field(default=None)  # "8-12"
    peso: Optional[float] = Field(default=None, ge=0)
    descanso_segundos: int = Field(default=60, ge=30, le=300)
    notas: Optional[str] = None


class DiaRutinaCreate(BaseModel):
    """Crear un día dentro de una rutina"""
    numero_dia: int
    nombre_dia: str
    descripcion: Optional[str] = None
    ejercicios: List[EjercicioDiaRutinaCreate] = []


class ParametrosRutinaCreate(BaseModel):
    """Parámetros para generar rutina con IA"""
    nombre_rutina: str = Field(..., min_length=3, max_length=255)
    id_usuario: int
    id_entrenador: int
    dias_por_semana: int = Field(..., ge=2, le=6)
    nivel_dificultad: NivelDificultadEnum
    grupo_muscular_enfoque: Optional[str] = None
    objetivo: ObjetivoEnum
    problemas: Optional[List[str]] = None
    enfermedades: Optional[List[str]] = None
    objetivo_alumno: Optional[str] = None


class RutinaUpdate(BaseModel):
    """Actualizar rutina existente"""
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    dias_por_semana: Optional[int] = Field(None, ge=2, le=6)
    nivel_dificultad: Optional[NivelDificultadEnum] = None
    grupo_muscular_enfoque: Optional[str] = None
    objetivo_alumno: Optional[str] = None
    estado: Optional[EstadoRutinaEnum] = None


class EjercicioDiaRutinaUpdate(BaseModel):
    """Actualizar ejercicio dentro de rutina"""
    series: Optional[int] = Field(None, ge=1, le=10)
    repeticiones: Optional[int] = Field(None, ge=1, le=100)
    rango_repeticiones: Optional[str] = None
    peso: Optional[float] = Field(None, ge=0)
    descanso_segundos: Optional[int] = Field(None, ge=30, le=300)
    notas: Optional[str] = None


# ============================================================
# SCHEMAS DE SALIDA (Responses)
# ============================================================

class EjercicioDiaRutinaResponse(BaseModel):
    """Respuesta de ejercicio en rutina"""
    id_ejercicio_dia: int
    id_ejercicio: int
    nombre_ejercicio: str
    orden: int
    series: int
    repeticiones: Optional[int]
    rango_repeticiones: Optional[str]
    peso: Optional[float]
    descanso_segundos: int
    notas: Optional[str]

    class Config:
        from_attributes = True


class DiaRutinaResponse(BaseModel):
    """Respuesta de día de rutina completo"""
    id_dia_rutina: int
    numero_dia: int
    nombre_dia: str
    descripcion: Optional[str]
    activo: bool
    ejercicios: List[EjercicioDiaRutinaResponse]

    class Config:
        from_attributes = True


class RutinaDetailResponse(BaseModel):
    """Respuesta detallada de rutina completa"""
    id_rutina: int
    nombre: str
    descripcion: Optional[str]
    id_usuario: int
    id_entrenador: int
    dias_por_semana: int
    nivel_dificultad: str
    grupo_muscular_enfoque: Optional[str]
    objetivo_alumno: Optional[str]
    estado: EstadoRutinaEnum
    fecha_creacion: datetime
    fecha_inicio: Optional[datetime]
    fecha_modificacion: datetime
    dias: List[DiaRutinaResponse]

    class Config:
        from_attributes = True


class RutinaListResponse(BaseModel):
    """Respuesta resumida de rutina para listas"""
    id_rutina: int
    nombre: str
    id_usuario: int
    dias_por_semana: int
    nivel_dificultad: str
    estado: EstadoRutinaEnum
    fecha_creacion: datetime
    fecha_modificacion: datetime

    class Config:
        from_attributes = True


class RutinaGeneradaPorIAResponse(BaseModel):
    """Respuesta de rutina generada por IA (antes de guardar)"""
    nombre: str
    dias_por_semana: int
    nivel_dificultad: str
    dias: List[DiaRutinaResponse]


class GuardarRutinaResponse(BaseModel):
    """Respuesta al guardar rutina"""
    ok: bool
    mensaje: str
    id_rutina: Optional[int] = None


class EditarRutinaResponse(BaseModel):
    """Respuesta al editar rutina"""
    ok: bool
    mensaje: str


class EliminarRutinaResponse(BaseModel):
    """Respuesta al eliminar rutina"""
    ok: bool
    mensaje: str


# ============================================================
# SCHEMAS PARA VALIDACIONES COMPLEJAS
# ============================================================

class RutinaConValidacion(BaseModel):
    """Validación completa de una rutina"""
    id_rutina: int
    nombre: str
    dias_por_semana: int
    dias: List[DiaRutinaResponse]

    @staticmethod
    def validar_rutina(rutina: 'RutinaConValidacion') -> bool:
        """
        Validaciones adicionales:
        - Número de días coincide con días_por_semana
        - Cada día tiene al menos 1 ejercicio
        """
        if len(rutina.dias) != rutina.dias_por_semana:
            raise ValueError(f"Rutina debe tener {rutina.dias_por_semana} días, tiene {len(rutina.dias)}")

        for dia in rutina.dias:
            if not dia.ejercicios:
                raise ValueError(f"Día {dia.nombre_dia} no tiene ejercicios")

        return True