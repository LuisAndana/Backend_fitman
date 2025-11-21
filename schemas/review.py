# schemas/review.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ResenaCreate(BaseModel):
    id_entrenador: int
    calificacion: float = Field(..., ge=1.0, le=5.0, description="Calificación de 1.0 a 5.0")
    titulo: Optional[str] = None
    comentario: Optional[str] = None
    calidad_rutina: Optional[int] = Field(None, ge=1, le=5, description="Puntuación 1-5")
    comunicacion: Optional[int] = Field(None, ge=1, le=5, description="Puntuación 1-5")
    disponibilidad: Optional[int] = Field(None, ge=1, le=5, description="Puntuación 1-5")
    resultados: Optional[int] = Field(None, ge=1, le=5, description="Puntuación 1-5")


class ResenaUpdate(BaseModel):
    calificacion: Optional[float] = Field(None, ge=1.0, le=5.0)
    titulo: Optional[str] = None
    comentario: Optional[str] = None
    calidad_rutina: Optional[int] = Field(None, ge=1, le=5)
    comunicacion: Optional[int] = Field(None, ge=1, le=5)
    disponibilidad: Optional[int] = Field(None, ge=1, le=5)
    resultados: Optional[int] = Field(None, ge=1, le=5)


class ResenaOut(BaseModel):
    id_resena: int
    id_entrenador: int
    id_alumno: int
    calificacion: float
    titulo: Optional[str] = None
    comentario: Optional[str] = None
    calidad_rutina: Optional[int] = None
    comunicacion: Optional[int] = None
    disponibilidad: Optional[int] = None
    resultados: Optional[int] = None
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    # ✅ AGREGADO: Nombre del alumno
    nombreAlumno: Optional[str] = None
    nombre_alumno: Optional[str] = None
    fotoAlumno: Optional[str] = None

    class Config:
        from_attributes = True


class EstadisticasEntrenador(BaseModel):
    id_entrenador: int
    promedio_calificacion: float
    total_resenas: int
    resenas_recientes: List[ResenaOut] = []

    class Config:
        from_attributes = True