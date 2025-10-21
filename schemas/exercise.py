# schemas/exercise.py
from pydantic import BaseModel
from typing import Optional

class EjercicioBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    grupo_muscular: Optional[str] = None
    imagen_url: Optional[str] = None

class EjercicioCreate(EjercicioBase): pass
class EjercicioOut(EjercicioBase):
    id_ejercicio: int
    class Config: from_attributes = True
