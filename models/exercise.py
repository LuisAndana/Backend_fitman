# models/exercise.py
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from config.database import Base

class Ejercicio(Base):
    __tablename__ = "ejercicios"
    id_ejercicio: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(Text)
    grupo_muscular: Mapped[str | None] = mapped_column(String(100))
    imagen_url: Mapped[str | None] = mapped_column(String(255))  # :contentReference[oaicite:7]{index=7}
    en_rutinas = relationship("RutinaEjercicio", back_populates="ejercicio")
