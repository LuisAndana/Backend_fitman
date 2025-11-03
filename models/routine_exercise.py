# models/routine_exercise.py
from sqlalchemy import Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from config.database import Base


class RutinaEjercicio(Base):
    __tablename__ = "rutina_ejercicios"

    id_rutina_ejercicio: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_rutina: Mapped[int | None] = mapped_column(Integer, ForeignKey("rutinas.id_rutina"), nullable=True)
    id_ejercicio: Mapped[int | None] = mapped_column(Integer, ForeignKey("ejercicios.id_ejercicio"), nullable=True)
    series: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repeticiones: Mapped[int | None] = mapped_column(Integer, nullable=True)
    descanso_segundos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actualizado_por: Mapped[int | None] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)

    # Relaciones - SIN backrefs conflictivos
    rutina = relationship("Rutina", back_populates="ejercicios")
    ejercicio = relationship("Ejercicio")