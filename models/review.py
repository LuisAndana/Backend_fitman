# models/review.py
from sqlalchemy import Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from config.database import Base


class Resena(Base):
    __tablename__ = "resenas"

    id_resena: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_entrenador: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_alumno: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    calificacion: Mapped[float] = mapped_column(Float, nullable=False)
    titulo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    calidad_rutina: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comunicacion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disponibilidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resultados: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)