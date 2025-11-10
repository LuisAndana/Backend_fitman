"""
models/exercise.py - Modelo para tabla de ejercicios
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

# ============================================================
# BASE
# ============================================================

Base = declarative_base()

# ============================================================
# ENUMS (en minúsculas, coinciden con MySQL)
# ============================================================

class TipoDificultad(str, enum.Enum):
    """Enum para niveles de dificultad"""
    PRINCIPIANTE = "principiante"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"


class TipoEjercicio(str, enum.Enum):
    """Enum para tipos de ejercicio"""
    FUERZA = "fuerza"
    CARDIO = "cardio"
    FLEXIBILIDAD = "flexibilidad"
    HIBRIDO = "hibrido"
    ISOMETRICO = "isometrico"


# ============================================================
# MODELO PRINCIPAL
# ============================================================

class Ejercicio(Base):
    """
    Modelo de ejercicio en la base de datos
    """
    __tablename__ = "ejercicios"

    id_ejercicio = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(255), nullable=False, index=True)
    descripcion = Column(Text, nullable=True)

    # Categorización
    grupo_muscular = Column(String(100), nullable=False, index=True)
    dificultad = Column(
        SQLEnum(TipoDificultad, name="tipodificultad"),
        nullable=False,
        default=TipoDificultad.INTERMEDIO,
        index=True
    )
    tipo = Column(
        SQLEnum(TipoEjercicio, name="tipoentrenamiento"),
        nullable=False,
        default=TipoEjercicio.FUERZA
    )

    # Parámetros por defecto
    series = Column(Integer, nullable=True, default=3)
    repeticiones = Column(Integer, nullable=True, default=10)
    descanso_segundos = Column(Integer, nullable=True, default=60)

    # Información adicional
    equipo_requerido = Column(String(200), nullable=True)
    alternativas = Column(String(500), nullable=True)
    notas_tecnicas = Column(Text, nullable=True)
    video_url = Column(String(500), nullable=True)

    # Auditoría
    activo = Column(Integer, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ========================================================
    # Conversión a diccionario
    # ========================================================
    def to_dict(self):
        """Devuelve un diccionario con los datos del ejercicio"""
        return {
            'id_ejercicio': self.id_ejercicio,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'grupo_muscular': self.grupo_muscular,
            'dificultad': self.dificultad.value if self.dificultad else None,
            'tipo': self.tipo.value if self.tipo else None,
            'series': self.series,
            'repeticiones': self.repeticiones,
            'descanso_segundos': self.descanso_segundos,
            'equipo_requerido': self.equipo_requerido,
            'alternativas': self.alternativas,
            'notas_tecnicas': self.notas_tecnicas,
            'video_url': self.video_url
        }


# ============================================================
# 🔹 Relación con RutinaEjercicio (definida al final)
# ============================================================

try:
    from models.rutina_ejercicio import RutinaEjercicio
    Ejercicio.rutina_ejercicios = relationship(
        "RutinaEjercicio",
        back_populates="ejercicio",
        cascade="all, delete"
    )
except ImportError:
    # Evita error circular si el modelo aún no está importado
    pass
