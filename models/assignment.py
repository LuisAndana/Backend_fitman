# models/assignment.py
from sqlalchemy import Integer, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from config.database import Base

class EstadoAsignacion(str, Enum):
    activa = "activa"
    completada = "completada"
    cancelada = "cancelada"

class Asignacion(Base):
    __tablename__ = "asignaciones"
    id_asignacion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_rutina: Mapped[int | None] = mapped_column(ForeignKey("rutinas.id_rutina"))
    id_alumno: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id_usuario"))
    fecha_asignacion: Mapped[DateTime | None] = mapped_column(DateTime)
    estado: Mapped[str] = mapped_column(Enum("activa","completada","cancelada"), default="activa")  # :contentReference[oaicite:9]{index=9}

    rutina = relationship("Rutina", back_populates="asignaciones")
    alumno = relationship("Usuario")
