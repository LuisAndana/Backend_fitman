# models/rutina_generada.py
from sqlalchemy import Integer, String, ForeignKey, DateTime, Text, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from config.database import Base


class RutinaGenerada(Base):
    __tablename__ = "rutinas_generadas"

    id_rutina_generada: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    duracion_minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    dificultad: Mapped[str] = mapped_column(String(50), nullable=False)
    ejercicios: Mapped[str] = mapped_column(JSON, nullable=False)  # Almacena JSON
    prompt_usado: Mapped[str] = mapped_column(Text, nullable=True)
    fecha_generacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    modelo_ia: Mapped[str] = mapped_column(String(100), default="gemini-pro", nullable=False)