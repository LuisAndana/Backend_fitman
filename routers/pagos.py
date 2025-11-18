# routers/pagos.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from utils.stripe_client import create_payment_intent

from utils.dependencies import get_db
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
        id_cliente: int = Query(..., description="ID del cliente"),
        payload: PagoCreate = None,
        db: Session = Depends(get_db),
):
    """Crea un nuevo registro de pago"""
    if payload is None:
        raise HTTPException(status_code=400, detail="Body del request es requerido")
    pago = crear_pago(db, id_cliente, payload)
    return pago


@router.get("/{id_pago}", response_model=PagoOut)
def obtener_pago_endpoint(
        id_pago: int,
        db: Session = Depends(get_db),
):
    """Obtiene detalles de un pago específico"""
    pago = obtener_pago(db, id_pago)
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    return pago


@router.post("/{id_pago}/confirmar", response_model=PagoOut)
def confirmar_pago_endpoint(
        id_pago: int,
        referencia_externa: str | None = Query(None),
        db: Session = Depends(get_db),
):
    """Confirma un pago pendiente (simulación de webhook)"""
    pago = obtener_pago(db, id_pago)
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    confirmar_pago(db, id_pago, referencia_externa)
    pago_actualizado = obtener_pago(db, id_pago)
    return pago_actualizado


@router.post("/{id_pago}/cancelar", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_pago_endpoint(
        id_pago: int,
        db: Session = Depends(get_db),
):
    """Cancela un pago pendiente"""
    pago = obtener_pago(db, id_pago)
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    cancelar_pago(db, id_pago)
    return None


@router.get("/cliente/historial", response_model=HistorialPagos)
def obtener_pagos_cliente_endpoint(
        id_cliente: int = Query(..., description="ID del cliente"),
        id_entrenador: int | None = Query(None),
        db: Session = Depends(get_db),
):
    """Obtiene el historial de pagos del cliente"""
    pagos = obtener_pagos_cliente(db, id_cliente, id_entrenador)

    total_meses = len(pagos)
    monto_total = sum(p.monto for p in pagos if p.estado == "confirmado")

    return HistorialPagos(
        pagos=pagos,
        total_meses=total_meses,
        monto_total=monto_total
    )


@router.get("/entrenador/ingresos", response_model=List[PagoOut])
def obtener_ingresos_entrenador_endpoint(
        id_entrenador: int = Query(..., description="ID del entrenador"),
        estado: str | None = Query(None),
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

    pagos = obtener_pagos_entrenador(db, id_entrenador, estado_enum)
    return pagos


@router.post("/suscripciones", response_model=SuscripcionOut, status_code=status.HTTP_201_CREATED)
def crear_suscripcion_endpoint(
        id_cliente: int = Query(..., description="ID del cliente"),
        payload: SuscripcionCreate = None,
        db: Session = Depends(get_db),
):
    """Crea una suscripción del cliente al entrenador"""
    if payload is None:
        raise HTTPException(status_code=400, detail="Body del request es requerido")
    suscripcion = crear_suscripcion(db, id_cliente, payload)
    return suscripcion


@router.get("/suscripciones/{id_suscripcion}", response_model=SuscripcionOut)
def obtener_suscripcion_endpoint(
        id_suscripcion: int,
        db: Session = Depends(get_db),
):
    """Obtiene detalles de una suscripción"""
    suscripcion = obtener_suscripcion(db, id_suscripcion)
    if not suscripcion:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    return suscripcion


@router.patch("/suscripciones/{id_suscripcion}", response_model=SuscripcionOut)
def actualizar_suscripcion_endpoint(
        id_suscripcion: int,
        payload: SuscripcionUpdate,
        db: Session = Depends(get_db),
):
    """Actualiza una suscripción"""
    suscripcion = obtener_suscripcion(db, id_suscripcion)
    if not suscripcion:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    suscripcion_actualizada = actualizar_suscripcion(db, id_suscripcion, payload)
    return suscripcion_actualizada


@router.post("/suscripciones/{id_suscripcion}/cancelar", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_suscripcion_endpoint(
        id_suscripcion: int,
        db: Session = Depends(get_db),
):
    """Cancela una suscripción activa"""
    suscripcion = obtener_suscripcion(db, id_suscripcion)
    if not suscripcion:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    cancelar_suscripcion(db, id_suscripcion)
    return None


@router.get("/suscripciones/cliente/activas", response_model=List[SuscripcionOut])
def obtener_suscripciones_cliente_endpoint(
        id_cliente: int = Query(..., description="ID del cliente"),
        db: Session = Depends(get_db),
):
    """Obtiene todas las suscripciones activas del cliente"""
    suscripciones = obtener_suscripciones_cliente(db, id_cliente)
    return suscripciones


@router.get("/suscripciones/entrenador/suscriptores", response_model=List[SuscripcionOut])
def obtener_suscriptores_endpoint(
        id_entrenador: int = Query(..., description="ID del entrenador"),
        db: Session = Depends(get_db),
):
    """Obtiene todos los suscriptores activos del entrenador"""
    suscripciones = obtener_suscripciones_entrenador(db, id_entrenador)
    return suscripciones


@router.post("/stripe/payment-intent")
def stripe_create_payment_intent(
        id_cliente: int = Query(...),
        id_entrenador: int = Query(...),
        monto: int = Query(..., description="Monto en centavos"),
        db: Session = Depends(get_db),
):
    """
    Crea un PaymentIntent REAL en Stripe
    """
    try:
        # 1️⃣ Registrar pago en BD como "pendiente"
        payload = PagoCreate(
            id_entrenador=id_entrenador,
            monto=monto / 100,          # convertir centavos → pesos (ej: 200000 → 2000)
            descripcion="Pago con Stripe",
            periodo_mes=1,
            periodo_anio=2025
        )

        pago = crear_pago(db, id_cliente, payload)

        # 2️⃣ Crear PaymentIntent real en Stripe con metadata
        intent = create_payment_intent(
            amount=monto,
            metadata={
                "id_pago": pago.id_pago,
                "id_cliente": id_cliente,
                "id_entrenador": id_entrenador
            }
        )

        # 3️⃣ Responder al cliente Angular
        return {
            "client_secret": intent.client_secret,
            "id_pago": pago.id_pago
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


        # 3️⃣ Devolvemos lo necesario para Angular
        return {
            "client_secret": intent.client_secret,
            "id_pago": pago.id_pago
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
