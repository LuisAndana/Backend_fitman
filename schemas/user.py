# schemas/user.py
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal, List

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

# -------- Tipos de entrenadores --------
Modalidad = Literal["Online", "Presencial"]

class TrainerOut(BaseModel):
    id: int
    nombre: str
    especialidad: str
    rating: float
    precio_mensual: int
    ciudad: str
    pais: Optional[str] = None
    experiencia: int
    modalidades: List[Modalidad]
    etiquetas: List[str]
    foto_url: Optional[str] = None
    whatsapp: Optional[str] = None
    bio: Optional[str] = None

    class Config:
        from_attributes = True

class TrainersFacets(BaseModel):
    especialidades: list[str] = Field(default_factory=list)
    ciudades: list[str] = Field(default_factory=list)
    modalidades: list[Modalidad] = Field(default_factory=list)
    precioMin: int | None = None
    precioMax: int | None = None
    ratingMax: float | None = None

class TrainersResponse(BaseModel):
    items: list[TrainerOut]
    total: int
    page: int
    pageSize: int
    facets: TrainersFacets | None = None

# -------- Perfil de entrenador (para detalle) --------
class ItemEdu(BaseModel):
    titulo: str | None = None
    institucion: str | None = None
    inicio: str | None = None
    fin: str | None = None
    descripcion: str | None = None
    evidenciaUrl: str | None = None

class ItemDip(BaseModel):
    titulo: str | None = None
    institucion: str | None = None
    fecha: str | None = None
    evidenciaUrl: str | None = None

class ItemCur(BaseModel):
    titulo: str | None = None
    institucion: str | None = None
    fecha: str | None = None
    evidenciaUrl: str | None = None

class ItemLog(BaseModel):
    titulo: str | None = None
    anio: str | None = None
    descripcion: str | None = None
    evidenciaUrl: str | None = None

class PerfilEntrenador(BaseModel):
    resumen: Optional[str] = ""
    educacion: list[ItemEdu] = Field(default_factory=list)
    diplomas: list[ItemDip]  = Field(default_factory=list)
    cursos: list[ItemCur]    = Field(default_factory=list)
    logros: list[ItemLog]    = Field(default_factory=list)

class TrainerDetail(TrainerOut):
    email: EmailStr | None = None
    telefono: str | None = None
    perfil: PerfilEntrenador | None = None
