# models/user.py
from __future__ import annotations
from sqlalchemy import Integer, String, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.mysql import DECIMAL, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from config.database import Base
import enum


class RolEnum(str, enum.Enum):
    alumno = "alumno"
    entrenador = "entrenador"


class SexoEnum(str, enum.Enum):
    Masculino = "Masculino"
    Femenino = "Femenino"
    Otro = "Otro"


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    rol: Mapped[RolEnum] = mapped_column(
        SAEnum(RolEnum, name="rolenum", native_enum=False, validate_strings=True),
        nullable=False
    )

    fecha_registro: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    sexo: Mapped[SexoEnum | None] = mapped_column(
        SAEnum(SexoEnum, name="sexoenum", native_enum=False, validate_strings=True),
        nullable=True
    )

    edad: Mapped[int | None] = mapped_column(TINYINT(unsigned=True), nullable=True)
    peso_kg: Mapped[float | None] = mapped_column(DECIMAL(5, 2), nullable=True)
    estatura_cm: Mapped[float | None] = mapped_column(DECIMAL(5, 2), nullable=True)
    problemas: Mapped[str | None] = mapped_column(Text, nullable=True)
    enfermedades: Mapped[str | None] = mapped_column(Text, nullable=True)
    foto_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imc: Mapped[float | None] = mapped_column(DECIMAL(5, 2), nullable=True)
    perfil_historial: Mapped[str | None] = mapped_column(Text, nullable=True)
    perfil_entrenador: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Campos adicionales
    especialidad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pais: Mapped[str | None] = mapped_column(String(80), nullable=True)
    precio_mensual: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(DECIMAL(3, 2), default=0.0)
    experiencia: Mapped[int] = mapped_column(Integer, default=0)
    modalidades: Mapped[str | None] = mapped_column(Text, nullable=True)
    etiquetas: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(30), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    auth_provider: Mapped[str] = mapped_column(String(50), default="local")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVO")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    # NO AGREGUES RELACIONES AQUI - Causa conflictos con Rutina