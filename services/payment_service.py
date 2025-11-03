# services/payment_service.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from models.payment import Pago, Suscripcion, EstadoPago
from schemas.payment import PagoCreate, SuscripcionCreate, SuscripcionUpdate
from datetime import datetime, timedelta


def crear_pago(db: Session, id_cliente: int, data: PagoCreate) -> Pago:
    """Crea un nuevo registro de pago"""
    pago = Pago(
        id_cliente=id_cliente,
        id_entrenador=data.id_entrenador,
        monto=data.monto,
        periodo_mes=data.periodo_mes,
        periodo_anio=data.periodo_anio,
        metodo_pago=data.metodo_pago,
        estado=EstadoPago.pendiente,
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago


def obtener_pago(db: Session, id_pago: int) -> Pago | None:
    """Obtiene un pago específico"""
    return db.query(Pago).filter(Pago.id_pago == id_pago).first()


def confirmar_pago(db: Session, id_pago: int, referencia_externa: str | None = None) -> bool:
    """Confirma un pago pendiente"""
    pago = obtener_pago(db, id_pago)
    if not pago:
        return False

    pago.estado = EstadoPago.confirmado
    pago.fecha_confirmacion = datetime.utcnow()
    if referencia_externa:
        pago.referencia_externa = referencia_externa

    db.add(pago)
    db.commit()
    return True


def cancelar_pago(db: Session, id_pago: int) -> bool:
    """Cancela un pago"""
    pago = obtener_pago(db, id_pago)
    if not pago:
        return False

    pago.estado = EstadoPago.cancelado
    db.add(pago)
    db.commit()
    return True


def obtener_pagos_cliente(
        db: Session,
        id_cliente: int,
        id_entrenador: int | None = None,
        limite: int = 50
) -> list[Pago]:
    """Obtiene los pagos de un cliente"""
    query = db.query(Pago).filter(Pago.id_cliente == id_cliente)

    if id_entrenador:
        query = query.filter(Pago.id_entrenador == id_entrenador)

    return query.order_by(desc(Pago.fecha_pago)).limit(limite).all()


def obtener_pagos_entrenador(
        db: Session,
        id_entrenador: int,
        estado: EstadoPago | None = None
) -> list[Pago]:
    """Obtiene los pagos recibidos por un entrenador"""
    query = db.query(Pago).filter(Pago.id_entrenador == id_entrenador)

    if estado:
        query = query.filter(Pago.estado == estado)

    return query.order_by(desc(Pago.fecha_pago)).all()


def crear_suscripcion(db: Session, id_cliente: int, data: SuscripcionCreate) -> Suscripcion:
    """Crea una suscripción entre cliente y entrenador"""
    suscripcion_existente = db.query(Suscripcion).filter(
        and_(
            Suscripcion.id_cliente == id_cliente,
            Suscripcion.id_entrenador == data.id_entrenador,
            Suscripcion.activa == True
        )
    ).first()

    if suscripcion_existente:
        return suscripcion_existente

    suscripcion = Suscripcion(
        id_cliente=id_cliente,
        id_entrenador=data.id_entrenador,
        monto_mensual=data.monto_mensual,
        activa=True,
    )
    db.add(suscripcion)
    db.commit()
    db.refresh(suscripcion)
    return suscripcion


def obtener_suscripcion(db: Session, id_suscripcion: int) -> Suscripcion | None:
    """Obtiene una suscripción específica"""
    return db.query(Suscripcion).filter(Suscripcion.id_suscripcion == id_suscripcion).first()


def actualizar_suscripcion(
        db: Session,
        id_suscripcion: int,
        data: SuscripcionUpdate
) -> Suscripcion | None:
    """Actualiza una suscripción"""
    suscripcion = obtener_suscripcion(db, id_suscripcion)
    if not suscripcion:
        return None

    if data.activa is not None:
        suscripcion.activa = data.activa
        if not data.activa:
            suscripcion.fecha_cancelacion = datetime.utcnow()

    db.add(suscripcion)
    db.commit()
    db.refresh(suscripcion)
    return suscripcion


def cancelar_suscripcion(db: Session, id_suscripcion: int) -> bool:
    """Cancela una suscripción activa"""
    suscripcion = obtener_suscripcion(db, id_suscripcion)
    if not suscripcion:
        return False

    suscripcion.activa = False
    suscripcion.fecha_cancelacion = datetime.utcnow()
    suscripcion.fecha_fin = datetime.utcnow()

    db.add(suscripcion)
    db.commit()
    return True


def obtener_suscripciones_cliente(db: Session, id_cliente: int) -> list[Suscripcion]:
    """Obtiene todas las suscripciones de un cliente"""
    return db.query(Suscripcion).filter(Suscripcion.id_cliente == id_cliente).all()


def obtener_suscripciones_entrenador(db: Session, id_entrenador: int) -> list[Suscripcion]:
    """Obtiene todos los suscriptores de un entrenador"""
    return db.query(Suscripcion).filter(
        and_(
            Suscripcion.id_entrenador == id_entrenador,
            Suscripcion.activa == True
        )
    ).all()


def generar_pago_automatico(db: Session, id_suscripcion: int) -> Pago | None:
    """Genera automáticamente un pago mensual para una suscripción activa"""
    suscripcion = obtener_suscripcion(db, id_suscripcion)
    if not suscripcion or not suscripcion.activa:
        return None

    ahora = datetime.utcnow()
    mes = ahora.month
    anio = ahora.year

    pago_existente = db.query(Pago).filter(
        and_(
            Pago.id_cliente == suscripcion.id_cliente,
            Pago.id_entrenador == suscripcion.id_entrenador,
            Pago.periodo_mes == mes,
            Pago.periodo_anio == anio
        )
    ).first()

    if pago_existente:
        return pago_existente

    pago = Pago(
        id_cliente=suscripcion.id_cliente,
        id_entrenador=suscripcion.id_entrenador,
        monto=suscripcion.monto_mensual,
        periodo_mes=mes,
        periodo_anio=anio,
        estado=EstadoPago.pendiente,
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago