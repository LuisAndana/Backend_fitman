# models/payment.py
from sqlalchemy import Integer, Float, ForeignKey, DateTime, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from config.database import Base
import enum


class EstadoPago(str, enum.Enum):
    pendiente = "pendiente"
    confirmado = "confirmado"
    cancelado = "cancelado"
    reembolsado = "reembolsado"


class Pago(Base):
    __tablename__ = "pagos"

    id_pago: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_cliente: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_entrenador: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    estado: Mapped[EstadoPago] = mapped_column(
        SAEnum(EstadoPago, name="estadopago", native_enum=False),
        default=EstadoPago.pendiente,
        nullable=False
    )
    metodo_pago: Mapped[str | None] = mapped_column(String(50), nullable=True)
    referencia_externa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    periodo_mes: Mapped[int] = mapped_column(Integer, nullable=False)
    periodo_anio: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_pago: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_confirmacion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fecha_vencimiento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Suscripcion(Base):
    __tablename__ = "suscripciones"

    id_suscripcion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_cliente: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_entrenador: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    monto_mensual: Mapped[float] = mapped_column(Float, nullable=False)
    activa: Mapped[bool] = mapped_column(Integer, default=1, nullable=False)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fecha_cancelacion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)