# schemas/assignment.py
from pydantic import BaseModel
from typing import Literal

class AsignacionCreate(BaseModel):
    id_rutina: int
    id_alumno: int

class AsignacionOut(BaseModel):
    id_asignacion: int
    estado: Literal["activa","completada","cancelada"]
    class Config: from_attributes = True
