# models/cliente_entrenador.py
"""
Modelo para la relación entre Clientes y Entrenadores
"""
from sqlalchemy import Integer, ForeignKey, DateTime, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from config.database import Base


class ClienteEntrenador(Base):
    __tablename__ = "cliente_entrenador"

    # ID de la relación
    id_relacion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # IDs de usuario (cliente y entrenador)
    id_cliente: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    id_entrenador: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Fechas
    fecha_contratacion: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    fecha_inicio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Estado: activo, pausado, cancelado
    estado: Mapped[str] = mapped_column(
        String(50),
        default="activo",
        nullable=False,
        index=True
    )

    # Notas opcionales del entrenador sobre el cliente
    notas: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Flag para saber si está activo
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return (
            f"<ClienteEntrenador("
            f"id_relacion={self.id_relacion}, "
            f"id_cliente={self.id_cliente}, "
            f"id_entrenador={self.id_entrenador}, "
            f"estado={self.estado}, "
            f"activo={self.activo}"
            f")>"
        )