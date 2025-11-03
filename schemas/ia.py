# schemas/ia.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Ejercicio(BaseModel):
    nombre: str
    series: int
    repeticiones: int
    descanso_segundos: int
    notas: Optional[str] = None


class GenerarRutinaRequest(BaseModel):
    objetivo: str
    duracion_minutos: Optional[int] = None
    dificultad: Optional[str] = None


class RutinaGeneradaOut(BaseModel):
    id_rutina_generada: int
    id_usuario: int
    nombre: str
    descripcion: str
    duracion_minutos: int
    dificultad: str
    ejercicios: List[Ejercicio]
    prompt_usado: str
    fecha_generacion: datetime

    class Config:
        from_attributes = True


class AnalisisPhotoRequest(BaseModel):
    imagen_base64: str
    descripcion_opcional: Optional[str] = None


class AnalisisPhotoOut(BaseModel):
    id_analisis: int
    id_usuario: int
    estado_fisico: str
    composicion_corporal: str
    observaciones_postura: str
    recomendaciones: str
    puntuacion_forma_fisica: float
    fecha_analisis: datetime

    class Config:
        from_attributes = True


class CalificacionEntrenadorRequest(BaseModel):
    id_entrenador: int


class CalificacionEntrenadorOut(BaseModel):
    puntuacion: float
    fortalezas: List[str]
    areas_mejora: List[str]
    recomendacion: str
    fecha_calificacion: datetime

    class Config:
        from_attributes = True


class ProgresoOut(BaseModel):
    id_progreso: int
    id_usuario: int
    peso_actual: float
    fecha: datetime
    notas: Optional[str] = None

    class Config:
        from_attributes = True