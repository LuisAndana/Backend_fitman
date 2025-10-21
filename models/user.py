# models/user.py
from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy import String, DateTime, Text, JSON, Enum as SAEnum, Integer, Computed  # <-- Computed
from sqlalchemy.dialects.mysql import DECIMAL as MyDECIMAL, TINYINT as MyTINYINT

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

    nombre:   Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    email:    Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    rol:      Mapped["RolEnum"] = mapped_column(SAEnum("alumno", "entrenador", name="rolenum"), nullable=False)

    fecha_registro: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Perfil
    sexo:        Mapped[Optional["SexoEnum"]] = mapped_column(SAEnum("HOMBRE", "MUJER", "OTRO", name="sexoenum"), nullable=True)
    edad:        Mapped[Optional[int]]   = mapped_column(MyTINYINT(unsigned=True), nullable=True)
    peso_kg:     Mapped[Optional[float]] = mapped_column(MyDECIMAL(5, 2), nullable=True)
    estatura_cm: Mapped[Optional[float]] = mapped_column(MyDECIMAL(5, 2), nullable=True)
    problemas:   Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    enfermedades:Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    foto_url:    Mapped[Optional[str]]   = mapped_column(String(255), nullable=True)

    # Columna generada VIRTUAL en MySQL. SQLAlchemy no la incluirá en INSERT/UPDATE.
    # Usamos NULLIF para evitar división por cero.
    imc: Mapped[Optional[float]] = mapped_column(
        MyDECIMAL(5, 2),
        Computed("ROUND(peso_kg / POW(NULLIF(estatura_cm,0)/100, 2), 2)", persisted=False),
        nullable=True,
    )

    perfil_historial: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, server_default=func.now(), onupdate=func.now()
    )

    rutinas_creadas = relationship(
        "Rutina",
        back_populates="creado_por",
        foreign_keys="Rutina.creado_por_id",
        cascade="all, delete-orphan",
    )
