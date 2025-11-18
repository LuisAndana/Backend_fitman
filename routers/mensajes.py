# routers/mensajes.py - VERSIÓN SIN AUTENTICACIÓN (SOLO DESARROLLO)
# ⚠️ ADVERTENCIA: Esta versión NO requiere autenticación
# Solo usar para desarrollo/testing, NO en producción

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from utils.dependencies import get_db
from models.user import Usuario
from schemas.message import MensajeCreate, MensajeOut, ConversacionOut, MensajesHistorico
from services.message_service import (
    enviar_mensaje,
    obtener_mensaje,
    marcar_como_leido,
    marcar_conversacion_como_leida,
    obtener_conversaciones,
    contar_no_leidos,
    eliminar_mensaje, obtener_conversacion,
)

router = APIRouter(prefix="/mensajes", tags=["mensajes"])


@router.post("", response_model=MensajeOut, status_code=status.HTTP_201_CREATED)
def enviar_mensaje_endpoint(
    user_id: int = Query(..., description="ID del usuario remitente"),
    payload: MensajeCreate = None,
    db: Session = Depends(get_db),
):
    if payload is None:
        raise HTTPException(status_code=400, detail="Body del request es requerido")

    remitente = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
    if not remitente:
        raise HTTPException(status_code=404, detail="Usuario remitente no encontrado")

    if user_id == payload.id_destinatario:
        raise HTTPException(status_code=400, detail="No puedes enviarte mensajes a ti mismo")

    destinatario = db.query(Usuario).filter(
        Usuario.id_usuario == payload.id_destinatario
    ).first()
    if not destinatario:
        raise HTTPException(status_code=404, detail="Usuario destinatario no encontrado")

    mensaje = enviar_mensaje(db, user_id, payload)
    return mensaje

@router.get("/{id_mensaje}", response_model=MensajeOut)
def obtener_mensaje_endpoint(
    id_mensaje: int,
    user_id: int = Query(..., description="ID del usuario que solicita el mensaje"),
    db: Session = Depends(get_db),
):
    mensaje = obtener_mensaje(db, id_mensaje)
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")

    if mensaje.id_remitente != user_id and mensaje.id_destinatario != user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este mensaje")

    if mensaje.id_destinatario == user_id and not mensaje.leido:
        marcar_como_leido(db, id_mensaje)
        mensaje.leido = True

    return mensaje


@router.post("/{id_mensaje}/marcar-leido", status_code=status.HTTP_204_NO_CONTENT)
def marcar_leido_endpoint(
    id_mensaje: int,
    user_id: int = Query(..., description="ID del usuario destinatario"),
    db: Session = Depends(get_db),
):
    mensaje = obtener_mensaje(db, id_mensaje)
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")

    if mensaje.id_destinatario != user_id:
        raise HTTPException(status_code=403, detail="Solo el destinatario puede marcar como leído")

    marcar_como_leido(db, id_mensaje)
    return None


@router.get("/conversacion/{id_otro_usuario}", response_model=MensajesHistorico)
def obtener_conversacion_endpoint(
        id_otro_usuario: int,
        user_id: int = Query(..., description="ID del usuario actual"),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
):
    """
    🔧 MODIFICADO: Obtiene la conversación entre dos usuarios

    Antes requería autenticación, ahora usa user_id como parámetro
    """
    # Validar que no sea el mismo usuario
    if user_id == id_otro_usuario:
        raise HTTPException(
            status_code=400,
            detail="No puedes obtener conversación contigo mismo"
        )

    # Validar que ambos usuarios existen
    usuario_actual = db.query(Usuario).filter(
        Usuario.id_usuario == user_id
    ).first()
    if not usuario_actual:
        raise HTTPException(status_code=404, detail="Usuario actual no encontrado")

    otro_usuario = db.query(Usuario).filter(
        Usuario.id_usuario == id_otro_usuario
    ).first()
    if not otro_usuario:
        raise HTTPException(status_code=404, detail="Otro usuario no encontrado")

    # Marcar mensajes como leídos
    marcar_conversacion_como_leida(db, user_id, id_otro_usuario)

    # Obtener mensajes
    mensajes = obtener_conversacion(
        db,
        user_id,
        id_otro_usuario,
        limit=limit,
        offset=offset
    )

    return MensajesHistorico(
        mensajes=mensajes[::-1],  # Invertir orden para mostrar cronológicamente
        total=len(mensajes)
    )
@router.get("/conversacion/{id_otro_usuario}", response_model=MensajesHistorico)
def obtener_historial_endpoint(
    id_otro_usuario: int,
    user_id: int = Query(..., description="ID del usuario actual"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if user_id == id_otro_usuario:
        raise HTTPException(status_code=400, detail="No puedes obtener conversación contigo mismo")

    usuario_actual = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
    if not usuario_actual:
        raise HTTPException(status_code=404, detail="Usuario actual no encontrado")

    otro_usuario = db.query(Usuario).filter(Usuario.id_usuario == id_otro_usuario).first()
    if not otro_usuario:
        raise HTTPException(status_code=404, detail="Otro usuario no encontrado")

    # Marca como leídos
    marcar_conversacion_como_leida(db, user_id, id_otro_usuario)

    # Obtener mensajes (esta función ya NO existe, se reemplaza)
    from sqlalchemy import or_, and_, desc
    from models.message import Mensaje

    mensajes = db.query(Mensaje).filter(
        or_(
            and_(Mensaje.id_remitente == user_id, Mensaje.id_destinatario == id_otro_usuario),
            and_(Mensaje.id_remitente == id_otro_usuario, Mensaje.id_destinatario == user_id),
        )
    ).order_by(desc(Mensaje.fecha_envio)).limit(limit).offset(offset).all()

    return MensajesHistorico(
        mensajes=mensajes[::-1],
        total=len(mensajes)
    )


@router.get("/mis-conversaciones/lista", response_model=List[ConversacionOut])
def obtener_conversaciones_endpoint(
    user_id: int = Query(..., description="ID del usuario"),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return obtener_conversaciones(db, user_id)




@router.post("/marcar-conversacion-leida/{id_otro_usuario}", status_code=status.HTTP_204_NO_CONTENT)
def marcar_conversacion_leida_endpoint(
    id_otro_usuario: int,
    user_id: int = Query(..., description="ID del usuario actual"),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    otro_usuario = db.query(Usuario).filter(Usuario.id_usuario == id_otro_usuario).first()
    if not otro_usuario:
        raise HTTPException(status_code=404, detail="Otro usuario no encontrado")

    marcar_conversacion_como_leida(db, user_id, id_otro_usuario)
    return None



@router.delete("/{id_mensaje}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_mensaje_endpoint(
    id_mensaje: int,
    user_id: int = Query(..., description="ID del usuario remitente"),
    db: Session = Depends(get_db),
):
    mensaje = obtener_mensaje(db, id_mensaje)
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")

    if mensaje.id_remitente != user_id:
        raise HTTPException(
            status_code=403,
            detail="Solo el remitente puede eliminar el mensaje"
        )

    eliminar_mensaje(db, id_mensaje)
    return None

# ============================================================
# ENDPOINTS DE PRUEBA ADICIONALES (SOLO PARA DESARROLLO)
# ============================================================

@router.get("/test/todos", response_model=List[MensajeOut])
def obtener_todos_mensajes_test(
        db: Session = Depends(get_db),
        limit: int = Query(100, le=500),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Lista TODOS los mensajes del sistema (para debugging)
    """
    from models.message import Mensaje
    mensajes = db.query(Mensaje).limit(limit).all()
    return mensajes


@router.get("/test/usuario/{user_id}/todos", response_model=List[MensajeOut])
def obtener_todos_mensajes_usuario_test(
        user_id: int,
        db: Session = Depends(get_db),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Lista TODOS los mensajes de un usuario específico (enviados y recibidos)
    """
    from models.message import Mensaje
    from sqlalchemy import or_

    mensajes = db.query(Mensaje).filter(
        or_(
            Mensaje.id_remitente == user_id,
            Mensaje.id_destinatario == user_id
        )
    ).all()

    return mensajes


@router.post("/test/crear-conversacion-prueba", response_model=dict)
def crear_conversacion_prueba(
        user1_id: int = Query(..., description="ID del primer usuario"),
        user2_id: int = Query(..., description="ID del segundo usuario"),
        num_mensajes: int = Query(10, description="Número de mensajes a crear"),
        db: Session = Depends(get_db),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Crea una conversación de prueba entre dos usuarios con mensajes automáticos
    """
    from datetime import datetime, timedelta
    import random

    # Validar usuarios
    user1 = db.query(Usuario).filter(Usuario.id_usuario == user1_id).first()
    user2 = db.query(Usuario).filter(Usuario.id_usuario == user2_id).first()

    if not user1 or not user2:
        raise HTTPException(status_code=404, detail="Uno o ambos usuarios no existen")

    if user1_id == user2_id:
        raise HTTPException(status_code=400, detail="Los usuarios deben ser diferentes")

    mensajes_creados = []
    mensajes_ejemplo = [
        "Hola, ¿cómo estás?",
        "Todo bien, gracias. ¿Y tú?",
        "Muy bien también, gracias por preguntar",
        "¿Qué planes tienes para hoy?",
        "Estoy trabajando en el gimnasio",
        "¡Qué bien! Yo también voy a entrenar",
        "¿A qué hora entrenas normalmente?",
        "Por las tardes, después del trabajo",
        "Perfecto, podemos coordinar",
        "Sí, me parece genial",
        "¿Cuál es tu rutina favorita?",
        "Me gusta mucho el entrenamiento funcional",
        "Excelente elección",
        "¿Y tú qué prefieres?",
        "Yo prefiero pesas y cardio",
        "También es muy bueno",
        "¿Llevamos mucho tiempo entrenando?",
        "Sí, varios años ya",
        "Se nota en los resultados",
        "Gracias, tú también te ves muy bien"
    ]

    for i in range(min(num_mensajes, len(mensajes_ejemplo))):
        # Alternar entre los usuarios
        remitente_id = user1_id if i % 2 == 0 else user2_id
        destinatario_id = user2_id if i % 2 == 0 else user1_id

        mensaje_data = MensajeCreate(
            id_destinatario=destinatario_id,
            contenido=mensajes_ejemplo[i % len(mensajes_ejemplo)]
        )

        mensaje = enviar_mensaje(db, remitente_id, mensaje_data)

        # Simular que algunos mensajes ya fueron leídos
        if random.random() > 0.3:
            mensaje.leido = True
            mensaje.fecha_lectura = datetime.utcnow() - timedelta(minutes=random.randint(1, 60))
            db.add(mensaje)

        mensajes_creados.append({
            "id": mensaje.id_mensaje,
            "remitente": remitente_id,
            "destinatario": destinatario_id,
            "contenido": mensaje.contenido[:50] + "..." if len(mensaje.contenido) > 50 else mensaje.contenido
        })

    db.commit()

    return {
        "mensaje": f"Conversación de prueba creada con {len(mensajes_creados)} mensajes",
        "usuarios": {
            "user1": {"id": user1_id, "nombre": user1.nombre},
            "user2": {"id": user2_id, "nombre": user2.nombre}
        },
        "mensajes_creados": len(mensajes_creados),
        "primeros_mensajes": mensajes_creados[:3]
    }


@router.delete("/test/limpiar-conversacion", status_code=status.HTTP_204_NO_CONTENT)
def limpiar_conversacion_test(
        user1_id: int = Query(..., description="ID del primer usuario"),
        user2_id: int = Query(..., description="ID del segundo usuario"),
        db: Session = Depends(get_db),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Elimina TODOS los mensajes entre dos usuarios (para limpiar pruebas)
    """
    from models.message import Mensaje
    from sqlalchemy import and_, or_

    # Eliminar todos los mensajes entre los dos usuarios
    mensajes_eliminados = db.query(Mensaje).filter(
        or_(
            and_(Mensaje.id_remitente == user1_id, Mensaje.id_destinatario == user2_id),
            and_(Mensaje.id_remitente == user2_id, Mensaje.id_destinatario == user1_id)
        )
    ).delete()

    db.commit()

    return None


@router.get("/test/estadisticas")
def obtener_estadisticas_mensajes(
        db: Session = Depends(get_db),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Obtiene estadísticas generales del sistema de mensajería
    """
    from models.message import Mensaje
    from sqlalchemy import func

    total_mensajes = db.query(func.count(Mensaje.id_mensaje)).scalar()
    mensajes_leidos = db.query(func.count(Mensaje.id_mensaje)).filter(
        Mensaje.leido == True
    ).scalar()
    mensajes_no_leidos = db.query(func.count(Mensaje.id_mensaje)).filter(
        Mensaje.leido == False
    ).scalar()

    # Usuarios con más mensajes enviados
    top_remitentes = db.query(
        Mensaje.id_remitente,
        Usuario.nombre,
        func.count(Mensaje.id_mensaje).label("total")
    ).join(
        Usuario, Usuario.id_usuario == Mensaje.id_remitente
    ).group_by(
        Mensaje.id_remitente, Usuario.nombre
    ).order_by(
        func.count(Mensaje.id_mensaje).desc()
    ).limit(5).all()

    # Usuarios con más mensajes recibidos
    top_destinatarios = db.query(
        Mensaje.id_destinatario,
        Usuario.nombre,
        func.count(Mensaje.id_mensaje).label("total")
    ).join(
        Usuario, Usuario.id_usuario == Mensaje.id_destinatario
    ).group_by(
        Mensaje.id_destinatario, Usuario.nombre
    ).order_by(
        func.count(Mensaje.id_mensaje).desc()
    ).limit(5).all()

    return {
        "estadisticas_generales": {
            "total_mensajes": total_mensajes,
            "mensajes_leidos": mensajes_leidos,
            "mensajes_no_leidos": mensajes_no_leidos,
            "porcentaje_leidos": round((mensajes_leidos / total_mensajes * 100) if total_mensajes > 0 else 0, 2)
        },
        "top_remitentes": [
            {"id": r[0], "nombre": r[1], "mensajes_enviados": r[2]}
            for r in top_remitentes
        ],
        "top_destinatarios": [
            {"id": d[0], "nombre": d[1], "mensajes_recibidos": d[2]}
            for d in top_destinatarios
        ]
    }
@router.get("/no-leidos/contar")
def contar_no_leidos_endpoint(
    user_id: int = Query(..., description="ID del usuario"),
    db: Session = Depends(get_db)
):
    return {"no_leidos": contar_no_leidos(db, user_id)}


def _usuario_conversacion_usuario_conversacion(u: Usuario) -> dict:
    rol_value = u.rol.value if hasattr(u.rol, "value") else str(u.rol) if u.rol else None

    return {
        "id_usuario": u.id_usuario,
        "nombre": u.nombre,
        "apellido": u.apellido,
        "foto_url": u.foto_url,
        "email": u.email,
        "rol": rol_value
    }


