# models/user.py
from __future__ import annotations
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from .database import Base
from typing import Optional
from datetime import datetime
from .database import Base

from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy import String, DateTime, Text, JSON, Enum as SAEnum, Integer, Computed
from sqlalchemy.dialects.mysql import DECIMAL as MyDECIMAL, TINYINT as MyTINYINT

from config.database import Base
import enum


class RolEnum(str, enum.Enum):
    alumno = "alumno"
    entrenador = "entrenador"


# models/user.py
class SexoEnum(str, enum.Enum):
    Masculino = "Masculino"
    Femenino  = "Femenino"
    Otro      = "Otro"

# …
sexo: Mapped[Optional["SexoEnum"]] = mapped_column(
    SAEnum("Masculino", "Femenino", "Otro", name="sexoenum", native_enum=False),
    nullable=True
)



class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    nombre:   Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    email:    Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Usa el Enum de Python para que coincida con la BD
    rol: Mapped[RolEnum] = mapped_column(
        SAEnum(RolEnum, name="rolenum", native_enum=True, validate_strings=True),
        nullable=False
    )

    fecha_registro: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # ⚠️ AQUI EL CAMBIO: usa "Masculino/Femenino/Otro"
    sexo: Mapped[Optional[SexoEnum]] = mapped_column(
        SAEnum(SexoEnum, name="sexoenum", native_enum=True, validate_strings=True),
        nullable=True
    )

    edad:        Mapped[Optional[int]]   = mapped_column(MyTINYINT(unsigned=True), nullable=True)
    peso_kg:     Mapped[Optional[float]] = mapped_column(MyDECIMAL(5, 2), nullable=True)
    estatura_cm: Mapped[Optional[float]] = mapped_column(MyDECIMAL(5, 2), nullable=True)
    problemas:   Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    enfermedades:Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    foto_url:    Mapped[Optional[str]]   = mapped_column(String(255), nullable=True)

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

    class Trainer(Base):
        __tablename__ = "entrenadores"

        id = Column(Integer, primary_key=True, index=True)
        usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)

        nombre = Column(String(150), nullable=False, index=True)
        especialidad = Column(String(100), nullable=False, index=True)
        rating = Column(Float, default=0, nullable=False)
        precio_mensual = Column(Integer, default=0, nullable=False)
        ciudad = Column(String(100), nullable=False, index=True)
        pais = Column(String(5), nullable=True)
        experiencia = Column(Integer, default=0, nullable=False)

        modalidades = Column(JSON, nullable=False, default=[])  # ["Online","Presencial"]
        etiquetas = Column(JSON, nullable=False, default=[])  # ["Fuerza","Técnica"]

        foto_url = Column(String(500), nullable=True)
        whatsapp = Column(String(20), nullable=True)
        bio = Column(String(1000), nullable=True)

        activo = Column(Boolean, default=True, nullable=False)
