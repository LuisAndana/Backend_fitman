# models/routine.py
from sqlalchemy import Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from config.database import Base


class Rutina(Base):
    __tablename__ = "rutinas"

    id_rutina: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_entrenador: Mapped[int | None] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=True)
    nombre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    objetivos: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duracion_minutos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dificultad: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)

    # Relaciones - sin backrefs conflictivos
    ejercicios = relationship("RutinaEjercicio", back_populates="rutina")