# schemas/message.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MensajeCreate(BaseModel):
    id_destinatario: int
    contenido: str


class MensajeOut(BaseModel):
    id_mensaje: int
    id_remitente: int
    id_destinatario: int
    contenido: str
    leido: bool
    fecha_envio: datetime
    fecha_lectura: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConversacionOut(BaseModel):
    id_usuario: int
    nombre_completo: str
    foto_url: Optional[str] = None
    ultimo_mensaje: Optional[str] = None
    fecha_ultimo_mensaje: Optional[datetime] = None
    mensajes_no_leidos: int

    class Config:
        from_attributes = True


class MensajesHistorico(BaseModel):
    mensajes: List[MensajeOut]
    total: int

    class Config:
        from_attributes = True