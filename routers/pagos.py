# routers/pagos.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from utils.dependencies import get_db, get_current_user
from models.user import Usuario
from schemas.payment import (
    PagoCreate, PagoOut,
    SuscripcionCreate, SuscripcionOut, SuscripcionUpdate,
    HistorialPagos
)
from services.payment_service import (
    crear_pago,
    obtener_pago,
    confirmar_pago,
    cancelar_pago,
    obtener_pagos_cliente,
    obtener_pagos_entrenador,
    crear_suscripcion,
    obtener_suscripcion,
    actualizar_suscripcion,
    cancelar_suscripcion,
    obtener_suscripciones_cliente,
    obtener_suscripciones_entrenador,
)

router = APIRouter(prefix="/pagos", tags=["pagos"])


@router.post("", response_model=PagoOut, status_code=status.HTTP_201_CREATED)
def crear_pago_endpoint(
        payload: PagoCreate,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Crea un nuevo registro de pago"""
    pago = crear_pago(db, current.id_usuario, payload)
    return pago


@router.get("/{id_pago}", response_model=PagoOut)
def obtener_pago_endpoint(
        id_pago: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene detalles de un pago específico"""
    pago = obtener_pago(db, id_pago)
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    if pago.id_cliente != current.id_usuario and pago.id_entrenador != current.id_usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este pago")

    return pago


@router.post("/{id_pago}/confirmar", response_model=PagoOut)
def confirmar_pago_endpoint(
        id_pago: int,
        referencia_externa: str | None = Query(None),
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Confirma un pago pendiente (simulación de webhook)"""
    pago = obtener_pago(db, id_pago)
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    if pago.id_entrenador != current.id_usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso para confirmar este pago")

    confirmar_pago(db, id_pago, referencia_externa)
    pago_actualizado = obtener_pago(db, id_pago)
    return pago_actualizado


@router.post("/{id_pago}/cancelar", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_pago_endpoint(
        id_pago: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Cancela un pago pendiente"""
    pago = obtener_pago(db, id_pago)
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    if pago.id_cliente != current.id_usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso para cancelar este pago")

    cancelar_pago(db, id_pago)
    return None


@router.get("/cliente/historial", response_model=HistorialPagos)
def obtener_pagos_cliente_endpoint(
        id_entrenador: int | None = Query(None),
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene el historial de pagos del cliente"""
    pagos = obtener_pagos_cliente(db, current.id_usuario, id_entrenador)

    total_meses = len(pagos)
    monto_total = sum(p.monto for p in pagos if p.estado == "confirmado")

    return HistorialPagos(
        pagos=pagos,
        total_meses=total_meses,
        monto_total=monto_total
    )


@router.get("/entrenador/ingresos", response_model=List[PagoOut])
def obtener_ingresos_entrenador_endpoint(
        estado: str | None = Query(None),
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene los ingresos (pagos confirmados) del entrenador"""
    from models.payment import EstadoPago
    estado_enum = None
    if estado:
        try:
            estado_enum = EstadoPago(estado)
        except ValueError:
            raise HTTPException(status_code=400, detail="Estado de pago inválido")

    pagos = obtener_pagos_entrenador(db, current.id_usuario, estado_enum)
    return pagos


@router.post("/suscripciones", response_model=SuscripcionOut, status_code=status.HTTP_201_CREATED)
def crear_suscripcion_endpoint(
        payload: SuscripcionCreate,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Crea una suscripción del cliente al entrenador"""
    suscripcion = crear_suscripcion(db, current.id_usuario, payload)
    return suscripcion


@router.get("/suscripciones/{id_suscripcion}", response_model=SuscripcionOut)
def obtener_suscripcion_endpoint(
        id_suscripcion: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene detalles de una suscripción"""
    suscripcion = obtener_suscripcion(db, id_suscripcion)
    if not suscripcion:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    if (suscripcion.id_cliente != current.id_usuario and
            suscripcion.id_entrenador != current.id_usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso para ver esta suscripción")

    return suscripcion


@router.patch("/suscripciones/{id_suscripcion}", response_model=SuscripcionOut)
def actualizar_suscripcion_endpoint(
        id_suscripcion: int,
        payload: SuscripcionUpdate,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Actualiza una suscripción"""
    suscripcion = obtener_suscripcion(db, id_suscripcion)
    if not suscripcion:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    if suscripcion.id_cliente != current.id_usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso para actualizar esta suscripción")

    suscripcion_actualizada = actualizar_suscripcion(db, id_suscripcion, payload)
    return suscripcion_actualizada


@router.post("/suscripciones/{id_suscripcion}/cancelar", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_suscripcion_endpoint(
        id_suscripcion: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Cancela una suscripción activa"""
    suscripcion = obtener_suscripcion(db, id_suscripcion)
    if not suscripcion:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    if suscripcion.id_cliente != current.id_usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso para cancelar esta suscripción")

    cancelar_suscripcion(db, id_suscripcion)
    return None


@router.get("/suscripciones/cliente/activas", response_model=List[SuscripcionOut])
def obtener_suscripciones_cliente_endpoint(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene todas las suscripciones activas del cliente"""
    suscripciones = obtener_suscripciones_cliente(db, current.id_usuario)
    return suscripciones


@router.get("/suscripciones/entrenador/suscriptores", response_model=List[SuscripcionOut])
def obtener_suscriptores_endpoint(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene todos los suscriptores activos del entrenador"""
    suscripciones = obtener_suscripciones_entrenador(db, current.id_usuario)
    return suscripciones