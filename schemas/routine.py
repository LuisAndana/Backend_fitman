# schemas/routine.py
from pydantic import BaseModel
from typing import Optional, List

class REItem(BaseModel):
    id_ejercicio: int
    series: int
    repeticiones: int
    descanso_segundos: int

class RutinaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    items: List[REItem] = []

class RutinaOut(BaseModel):
    id_rutina: int
    nombre: str
    descripcion: Optional[str]
    class Config: from_attributes = True
