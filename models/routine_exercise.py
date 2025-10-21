# models/routine_exercise.py
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from config.database import Base

class RutinaEjercicio(Base):
    __tablename__ = "rutina_ejercicios"
    id_rutina_ejercicio: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_rutina: Mapped[int | None] = mapped_column(ForeignKey("rutinas.id_rutina"))
    id_ejercicio: Mapped[int | None] = mapped_column(ForeignKey("ejercicios.id_ejercicio"))
    series: Mapped[int | None] = mapped_column(Integer)
    repeticiones: Mapped[int | None] = mapped_column(Integer)
    descanso_segundos: Mapped[int | None] = mapped_column(Integer)  # :contentReference[oaicite:8]{index=8}

    rutina = relationship("Rutina", back_populates="ejercicios")
    ejercicio = relationship("Ejercicio", back_populates="en_rutinas")
