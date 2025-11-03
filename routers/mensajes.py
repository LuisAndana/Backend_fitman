# routers/mensajes.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from utils.dependencies import get_db, get_current_user
from models.user import Usuario
from schemas.message import MensajeCreate, MensajeOut, ConversacionOut, MensajesHistorico
from services.message_service import (
    enviar_mensaje,
    obtener_mensaje,
    marcar_como_leido,
    marcar_conversacion_como_leida,
    obtener_conversacion,
    obtener_conversaciones,
    contar_no_leidos,
    eliminar_mensaje,
)

router = APIRouter(prefix="/mensajes", tags=["mensajes"])


@router.post("", response_model=MensajeOut, status_code=status.HTTP_201_CREATED)
def enviar_mensaje_endpoint(
        payload: MensajeCreate,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Envía un mensaje a otro usuario"""
    if current.id_usuario == payload.id_destinatario:
        raise HTTPException(
            status_code=400,
            detail="No puedes enviarte mensajes a ti mismo"
        )

    destinatario = db.query(Usuario).filter(
        Usuario.id_usuario == payload.id_destinatario
    ).first()
    if not destinatario:
        raise HTTPException(status_code=404, detail="Usuario destinatario no encontrado")

    mensaje = enviar_mensaje(db, current.id_usuario, payload)
    return mensaje


@router.get("/{id_mensaje}", response_model=MensajeOut)
def obtener_mensaje_endpoint(
        id_mensaje: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene un mensaje específico"""
    mensaje = obtener_mensaje(db, id_mensaje)
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")

    if mensaje.id_remitente != current.id_usuario and mensaje.id_destinatario != current.id_usuario:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para ver este mensaje"
        )

    if mensaje.id_destinatario == current.id_usuario and not mensaje.leido:
        marcar_como_leido(db, id_mensaje)
        mensaje.leido = True

    return mensaje


@router.post("/{id_mensaje}/marcar-leido", status_code=status.HTTP_204_NO_CONTENT)
def marcar_leido_endpoint(
        id_mensaje: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Marca un mensaje como leído"""
    mensaje = obtener_mensaje(db, id_mensaje)
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")

    if mensaje.id_destinatario != current.id_usuario:
        raise HTTPException(
            status_code=403,
            detail="Solo el destinatario puede marcar como leído"
        )

    marcar_como_leido(db, id_mensaje)
    return None


@router.get("/conversacion/{id_otro_usuario}", response_model=MensajesHistorico)
def obtener_conversacion_endpoint(
        id_otro_usuario: int,
        current: Usuario = Depends(get_current_user),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
):
    """Obtiene la conversación entre el usuario actual y otro usuario"""
    if current.id_usuario == id_otro_usuario:
        raise HTTPException(
            status_code=400,
            detail="No puedes obtener conversación contigo mismo"
        )

    otro_usuario = db.query(Usuario).filter(
        Usuario.id_usuario == id_otro_usuario
    ).first()
    if not otro_usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    marcar_conversacion_como_leida(db, current.id_usuario, id_otro_usuario)

    mensajes = obtener_conversacion(
        db,
        current.id_usuario,
        id_otro_usuario,
        limit=limit,
        offset=offset
    )

    return MensajesHistorico(
        mensajes=mensajes[::-1],
        total=len(mensajes)
    )


@router.get("/mis-conversaciones/lista", response_model=List[ConversacionOut])
def obtener_conversaciones_endpoint(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene todas las conversaciones del usuario actual"""
    conversaciones = obtener_conversaciones(db, current.id_usuario)
    return conversaciones


@router.get("/no-leidos/contar")
def contar_no_leidos_endpoint(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Cuenta los mensajes no leídos del usuario actual"""
    total = contar_no_leidos(db, current.id_usuario)
    return {"no_leidos": total}


@router.post("/marcar-conversacion-leida/{id_otro_usuario}", status_code=status.HTTP_204_NO_CONTENT)
def marcar_conversacion_leida_endpoint(
        id_otro_usuario: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Marca una conversación completa como leída"""
    marcar_conversacion_como_leida(db, current.id_usuario, id_otro_usuario)
    return None


@router.delete("/{id_mensaje}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_mensaje_endpoint(
        id_mensaje: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Elimina un mensaje (solo el remitente puede hacerlo)"""
    mensaje = obtener_mensaje(db, id_mensaje)
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")

    if mensaje.id_remitente != current.id_usuario:
        raise HTTPException(
            status_code=403,
            detail="Solo el remitente puede eliminar el mensaje"
        )

    eliminar_mensaje(db, id_mensaje)
    return None