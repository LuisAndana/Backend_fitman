# models/message.py
from sqlalchemy import Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from config.database import Base


class Mensaje(Base):
    __tablename__ = "mensajes"

    id_mensaje: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_remitente: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_destinatario: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    leido: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fecha_envio: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_lectura: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)