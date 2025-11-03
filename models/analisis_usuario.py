# models/analisis_usuario.py
from sqlalchemy import Integer, String, ForeignKey, DateTime, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from config.database import Base


class AnalisisUsuario(Base):
    __tablename__ = "analisis_usuarios"

    id_analisis: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    estado_fisico: Mapped[str] = mapped_column(String(100), nullable=False)
    composicion_corporal: Mapped[str] = mapped_column(String(100), nullable=False)
    observaciones_postura: Mapped[str] = mapped_column(Text, nullable=True)
    recomendaciones: Mapped[str] = mapped_column(Text, nullable=False)
    puntuacion_forma_fisica: Mapped[float] = mapped_column(Float, nullable=False)
    imagen_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fecha_analisis: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Progreso(Base):
    __tablename__ = "progreso_usuario"

    id_progreso: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    peso_anterior: Mapped[float | None] = mapped_column(Float, nullable=True)
    peso_actual: Mapped[float] = mapped_column(Float, nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)