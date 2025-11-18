# schemas/message.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime



# --------------------------
# Crear mensaje
# --------------------------
class MensajeCreate(BaseModel):
    id_destinatario: int
    contenido: str


# --------------------------
# Mensaje individual
# --------------------------
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


# --------------------------
# Último mensaje en lista de chats
# --------------------------
class UltimoMensaje(BaseModel):
    id_mensaje: int
    contenido: str
    fecha_envio: datetime
    leido: bool
    id_remitente: int
    id_destinatario: int

    class Config:
        from_attributes = True


# --------------------------
# Usuario dentro de la conversación
# --------------------------
class UsuarioChat(BaseModel):
    id_usuario: int
    nombre: str
    apellido: str
    foto_url: Optional[str] = None

    class Config:
        from_attributes = True


# --------------------------
# Conversación completa (LISTA DE CONVERSACIONES)
# --------------------------
class ConversacionOut(BaseModel):
    otro_usuario: UsuarioChat
    ultimo_mensaje: UltimoMensaje
    mensajes_no_leidos: int

    class Config:
        from_attributes = True


# --------------------------
# Histórico de mensajes entre dos usuarios
# --------------------------
class MensajesHistorico(BaseModel):
    mensajes: List[MensajeOut]
    total: int

    class Config:
        from_attributes = True
