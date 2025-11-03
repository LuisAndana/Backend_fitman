# models/assignment.py
from sqlalchemy import Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from config.database import Base


class Asignacion(Base):
    __tablename__ = "asignaciones"

    id_asignacion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario: Mapped[int | None] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=True)
    id_rutina: Mapped[int | None] = mapped_column(Integer, ForeignKey("rutinas.id_rutina"), nullable=True)
    fecha_asignacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    estado: Mapped[str | None] = mapped_column(String(50), default="activa", nullable=True)
    fecha_inicio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notas: Mapped[str | None] = mapped_column(String(500), nullable=True)