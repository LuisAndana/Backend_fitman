# services/message_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from models.message import Mensaje
from models.user import Usuario
from schemas.message import MensajeCreate
from datetime import datetime


def enviar_mensaje(db: Session, id_remitente: int, data: MensajeCreate) -> Mensaje:
    """Envía un mensaje de un usuario a otro"""
    mensaje = Mensaje(
        id_remitente=id_remitente,
        id_destinatario=data.id_destinatario,
        contenido=data.contenido,
    )
    db.add(mensaje)
    db.commit()
    db.refresh(mensaje)
    return mensaje


def obtener_mensaje(db: Session, id_mensaje: int) -> Mensaje | None:
    """Obtiene un mensaje específico"""
    return db.query(Mensaje).filter(Mensaje.id_mensaje == id_mensaje).first()


def marcar_como_leido(db: Session, id_mensaje: int) -> bool:
    """Marca un mensaje como leído"""
    mensaje = obtener_mensaje(db, id_mensaje)
    if not mensaje:
        return False

    mensaje.leido = True
    mensaje.fecha_lectura = datetime.utcnow()
    db.add(mensaje)
    db.commit()
    return True


def marcar_conversacion_como_leida(db: Session, id_usuario: int, id_otro_usuario: int) -> int:
    """Marca todos los mensajes no leídos de una conversación como leídos"""
    mensajes = db.query(Mensaje).filter(
        Mensaje.id_destinatario == id_usuario,
        Mensaje.id_remitente == id_otro_usuario,
        Mensaje.leido == False
    ).all()

    for msg in mensajes:
        msg.leido = True
        msg.fecha_lectura = datetime.utcnow()
        db.add(msg)

    db.commit()
    return len(mensajes)

def obtener_conversacion(
    db: Session,
    id_usuario1: int,
    id_usuario2: int,
    limit: int = 50,
    offset: int = 0
) -> list[Mensaje]:
    """Obtiene todos los mensajes entre dos usuarios"""

    return db.query(Mensaje).filter(
        or_(
            and_(Mensaje.id_remitente == id_usuario1, Mensaje.id_destinatario == id_usuario2),
            and_(Mensaje.id_remitente == id_usuario2, Mensaje.id_destinatario == id_usuario1)
        )
    ).order_by(desc(Mensaje.fecha_envio)).limit(limit).offset(offset).all()


def obtener_conversaciones(db: Session, id_usuario: int) -> list[dict]:
    """Obtiene todas las conversaciones con formato correcto"""

    usuarios_set = set()

    enviados = db.query(Mensaje.id_destinatario).filter(
        Mensaje.id_remitente == id_usuario
    ).distinct().all()

    recibidos = db.query(Mensaje.id_remitente).filter(
        Mensaje.id_destinatario == id_usuario
    ).distinct().all()

    for row in enviados:
        usuarios_set.add(row[0])
    for row in recibidos:
        usuarios_set.add(row[0])

    conversaciones = []

    for otro_id in usuarios_set:

        otro_usuario = db.query(Usuario).filter(
            Usuario.id_usuario == otro_id
        ).first()

        if not otro_usuario:
            continue

        ultimo_msg: Mensaje = db.query(Mensaje).filter(
            or_(
                and_(Mensaje.id_remitente == id_usuario,
                     Mensaje.id_destinatario == otro_id),
                and_(Mensaje.id_remitente == otro_id,
                     Mensaje.id_destinatario == id_usuario),
            )
        ).order_by(desc(Mensaje.fecha_envio)).first()

        if not ultimo_msg:
            continue

        no_leidos = db.query(Mensaje).filter(
            Mensaje.id_destinatario == id_usuario,
            Mensaje.id_remitente == otro_id,
            Mensaje.leido == False
        ).count()

        conversaciones.append({
            "otro_usuario": {
                "id_usuario": otro_usuario.id_usuario,
                "nombre": otro_usuario.nombre,
                "apellido": otro_usuario.apellido,
                "email": otro_usuario.email,
                "foto_url": otro_usuario.foto_url,
            },
            "ultimo_mensaje": {
    "id_mensaje": ultimo_msg.id_mensaje,
    "id_remitente": ultimo_msg.id_remitente,
    "id_destinatario": ultimo_msg.id_destinatario,
    "contenido": ultimo_msg.contenido,
    "fecha_envio": ultimo_msg.fecha_envio,
    "leido": ultimo_msg.leido,
    "es_remitente": ultimo_msg.id_remitente == id_usuario
},

            "mensajes_no_leidos": no_leidos
        })

    conversaciones.sort(
        key=lambda x: x["ultimo_mensaje"]["fecha_envio"],
        reverse=True
    )

    return conversaciones


def contar_no_leidos(db: Session, id_usuario: int) -> int:
    """Cuenta los mensajes no leídos de un usuario"""
    return db.query(Mensaje).filter(
        Mensaje.id_destinatario == id_usuario,
        Mensaje.leido == False
    ).count()


def eliminar_mensaje(db: Session, id_mensaje: int) -> bool:
    """Elimina un mensaje"""
    mensaje = obtener_mensaje(db, id_mensaje)
    if not mensaje:
        return False

    db.delete(mensaje)
    db.commit()
    return True