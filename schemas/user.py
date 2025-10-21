# schemas/user.py
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal

class UsuarioBase(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    rol: Literal["entrenador","alumno"]

class UsuarioCreate(UsuarioBase):
    password: str

class UsuarioOut(UsuarioBase):
    id_usuario: int
    class Config:
        from_attributes = True
