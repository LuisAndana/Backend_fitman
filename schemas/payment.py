# schemas/payment.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


from datetime import datetime

class PagoCreate(BaseModel):
    id_entrenador: int
    monto: float
    descripcion: str
    periodo_mes: int = 1                     # Pago mensual
    periodo_anio: int = datetime.now().year  # Año actual

    metodo_pago: Optional[str] = None


class PagoOut(BaseModel):
    id_pago: int
    id_cliente: int
    id_entrenador: int
    monto: float
    estado: str
    metodo_pago: Optional[str] = None
    referencia_externa: Optional[str] = None
    periodo_mes: int
    periodo_anio: int
    fecha_pago: datetime
    fecha_confirmacion: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None

    class Config:
        from_attributes = True


class SuscripcionCreate(BaseModel):
    id_entrenador: int
    monto_mensual: float


class SuscripcionUpdate(BaseModel):
    activa: Optional[bool] = None


class SuscripcionOut(BaseModel):
    id_suscripcion: int
    id_cliente: int
    id_entrenador: int
    monto_mensual: float
    activa: bool
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    fecha_cancelacion: Optional[datetime] = None

    class Config:
        from_attributes = True


class HistorialPagos(BaseModel):
    pagos: List[PagoOut]
    total_meses: int
    monto_total: float

    class Config:
        from_attributes = True