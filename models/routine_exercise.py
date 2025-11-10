"""
models/rutina_ejercicio.py - Relación entre rutinas y ejercicios
"""

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RutinaEjercicio(Base):
    __tablename__ = "rutinas_ejercicios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_rutina = Column(Integer, ForeignKey("rutinas.id_rutina"), nullable=False, index=True)
    id_ejercicio = Column(Integer, ForeignKey("ejercicios.id_ejercicio"), nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "id_rutina": self.id_rutina,
            "id_ejercicio": self.id_ejercicio
        }

# Relaciones se declaran al final para evitar ciclos
try:
    from models.ejercicio import Ejercicio
    from models.rutina import Rutina

    RutinaEjercicio.rutina = relationship("Rutina", back_populates="rutina_ejercicios")
    RutinaEjercicio.ejercicio = relationship("Ejercicio", back_populates="rutina_ejercicios")
except ImportError:
    pass
