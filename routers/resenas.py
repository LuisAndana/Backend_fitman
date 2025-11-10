# routers/resenas.py - VERSIÓN SIN AUTENTICACIÓN (SOLO DESARROLLO)
# ⚠️ ADVERTENCIA: Esta versión NO requiere autenticación
# Solo usar para desarrollo/testing, NO en producción

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from utils.dependencies import get_db
from models.user import Usuario
from schemas.review import ResenaCreate, ResenaUpdate, ResenaOut, EstadisticasEntrenador
from services.review_service import (
    crear_resena,
    obtener_resena,
    actualizar_resena,
    eliminar_resena,
    obtener_resenas_entrenador,
    obtener_estadisticas_entrenador,
    obtener_resenas_por_alumno,
)

router = APIRouter(prefix="/resenas", tags=["resenas"])


@router.post("", response_model=ResenaOut, status_code=status.HTTP_201_CREATED)
def crear_resena_endpoint(
        user_id: int = Query(..., description="ID del alumno que crea la reseña"),
        payload: ResenaCreate = None,
        db: Session = Depends(get_db),
):
    """
    🔧 MODIFICADO: Crea una nueva reseña/calificación para un entrenador

    Antes requería autenticación, ahora usa user_id como parámetro
    """
    if payload is None:
        raise HTTPException(status_code=400, detail="Body del request es requerido")

    # Validar que el usuario existe
    usuario = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Validar que el entrenador existe
    entrenador = db.query(Usuario).filter(Usuario.id_usuario == payload.id_entrenador).first()
    if not entrenador:
        raise HTTPException(status_code=404, detail="Entrenador no encontrado")

    # No puede calificarse a sí mismo
    if user_id == payload.id_entrenador:
        raise HTTPException(
            status_code=400,
            detail="No puedes calificarte a ti mismo"
        )

    # Verificar si ya existe una reseña
    resena_existente = obtener_resenas_por_alumno(
        db,
        user_id,
        payload.id_entrenador
    )
    if resena_existente:
        raise HTTPException(
            status_code=409,
            detail="Ya has calificado a este entrenador"
        )

    resena = crear_resena(db, user_id, payload)
    return resena


@router.get("/{id_resena}", response_model=ResenaOut)
def obtener_resena_endpoint(
        id_resena: int,
        db: Session = Depends(get_db),
):
    """
    Obtiene una reseña específica

    Este endpoint ya no requería autenticación, se mantiene igual
    """
    resena = obtener_resena(db, id_resena)
    if not resena:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    return resena


@router.patch("/{id_resena}", response_model=ResenaOut)
def actualizar_resena_endpoint(
        id_resena: int,
        user_id: int = Query(..., description="ID del alumno que actualiza la reseña"),
        payload: ResenaUpdate = None,
        db: Session = Depends(get_db),
):
    """
    🔧 MODIFICADO: Actualiza una reseña (solo el autor puede hacerlo)

    Antes requería autenticación, ahora usa user_id como parámetro
    """
    if payload is None:
        raise HTTPException(status_code=400, detail="Body del request es requerido")

    resena = obtener_resena(db, id_resena)
    if not resena:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")

    # Solo el autor puede editar
    if resena.id_alumno != user_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para editar esta reseña"
        )

    resena_actualizada = actualizar_resena(db, id_resena, payload)
    return resena_actualizada


@router.delete("/{id_resena}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_resena_endpoint(
        id_resena: int,
        user_id: int = Query(..., description="ID del alumno que elimina la reseña"),
        db: Session = Depends(get_db),
):
    """
    🔧 MODIFICADO: Elimina una reseña (solo el autor puede hacerlo)

    Antes requería autenticación, ahora usa user_id como parámetro
    """
    resena = obtener_resena(db, id_resena)
    if not resena:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")

    # Solo el autor puede eliminar
    if resena.id_alumno != user_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para eliminar esta reseña"
        )

    eliminar_resena(db, id_resena)
    return None


@router.get("/entrenador/{id_entrenador}/resenas", response_model=List[ResenaOut])
def obtener_resenas_endpoint(
        id_entrenador: int,
        limit: int = Query(10, ge=1, le=100),
        db: Session = Depends(get_db),
):
    """
    Obtiene todas las reseñas de un entrenador

    Este endpoint ya no requería autenticación, se mantiene igual
    """
    # Validar que el entrenador existe
    entrenador = db.query(Usuario).filter(Usuario.id_usuario == id_entrenador).first()
    if not entrenador:
        raise HTTPException(status_code=404, detail="Entrenador no encontrado")

    resenas = obtener_resenas_entrenador(db, id_entrenador, limit=limit)
    return resenas


@router.get("/entrenador/{id_entrenador}/estadisticas", response_model=EstadisticasEntrenador)
def obtener_estadisticas_endpoint(
        id_entrenador: int,
        db: Session = Depends(get_db),
):
    """
    Obtiene las estadísticas de calificación de un entrenador

    Este endpoint ya no requería autenticación, se mantiene igual
    """
    # Validar que el entrenador existe
    entrenador = db.query(Usuario).filter(Usuario.id_usuario == id_entrenador).first()
    if not entrenador:
        raise HTTPException(status_code=404, detail="Entrenador no encontrado")

    stats = obtener_estadisticas_entrenador(db, id_entrenador)
    return stats


@router.get("/mi-resena/{id_entrenador}", response_model=ResenaOut | None)
def obtener_mi_resena_endpoint(
        id_entrenador: int,
        user_id: int = Query(..., description="ID del alumno"),
        db: Session = Depends(get_db),
):
    """
    🔧 MODIFICADO: Obtiene la reseña de un usuario hacia un entrenador

    Antes requería autenticación, ahora usa user_id como parámetro
    """
    # Validar que el usuario existe
    usuario = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Validar que el entrenador existe
    entrenador = db.query(Usuario).filter(Usuario.id_usuario == id_entrenador).first()
    if not entrenador:
        raise HTTPException(status_code=404, detail="Entrenador no encontrado")

    resena = obtener_resenas_por_alumno(db, user_id, id_entrenador)
    if not resena:
        return None
    return resena


# ============================================================
# ENDPOINTS DE PRUEBA ADICIONALES (SOLO PARA DESARROLLO)
# ============================================================

@router.get("/test/todas", response_model=List[ResenaOut])
def obtener_todas_resenas_test(
        db: Session = Depends(get_db),
        limit: int = Query(100, le=500),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Lista TODAS las reseñas del sistema (para debugging)
    """
    from models.review import Resena
    resenas = db.query(Resena).limit(limit).all()
    return resenas


@router.get("/test/usuario/{user_id}/resenas", response_model=List[ResenaOut])
def obtener_resenas_usuario_test(
        user_id: int,
        db: Session = Depends(get_db),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Lista todas las reseñas hechas por un usuario específico
    """
    from models.review import Resena

    resenas = db.query(Resena).filter(
        Resena.id_alumno == user_id
    ).all()

    return resenas


@router.post("/test/crear-resenas-prueba", response_model=dict)
def crear_resenas_prueba(
        id_entrenador: int = Query(..., description="ID del entrenador a reseñar"),
        num_resenas: int = Query(5, description="Número de reseñas a crear", le=20),
        db: Session = Depends(get_db),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Crea reseñas de prueba para un entrenador con datos automáticos
    """
    import random
    from datetime import datetime, timedelta

    # Validar que el entrenador existe
    entrenador = db.query(Usuario).filter(Usuario.id_usuario == id_entrenador).first()
    if not entrenador:
        raise HTTPException(status_code=404, detail="Entrenador no encontrado")

    # Buscar usuarios que puedan hacer reseñas (excluyendo al entrenador)
    usuarios_disponibles = db.query(Usuario).filter(
        Usuario.id_usuario != id_entrenador
    ).limit(num_resenas * 2).all()

    if len(usuarios_disponibles) < num_resenas:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficientes usuarios. Se necesitan {num_resenas}, hay {len(usuarios_disponibles)} disponibles"
        )

    comentarios_ejemplo = [
        "Excelente entrenador, muy profesional y atento",
        "Me ayudó mucho a alcanzar mis objetivos",
        "Muy buena experiencia, lo recomiendo",
        "Gran conocimiento y paciencia para enseñar",
        "Resultados visibles en pocas semanas",
        "Motivador y siempre puntual",
        "Rutinas personalizadas muy efectivas",
        "Explica muy bien los ejercicios",
        "Me siento mucho mejor desde que entreno con él",
        "Superó mis expectativas, muy contento",
        "Buen entrenador pero podría mejorar la comunicación",
        "Cumplió con lo prometido",
        "Muy dedicado y comprometido",
        "Excelente relación calidad-precio",
        "Me ayudó a superar mis límites",
        "Profesional y amigable",
        "Las rutinas son variadas y divertidas",
        "Siempre está disponible para dudas",
        "Un poco estricto pero efectivo",
        "Recomendado al 100%"
    ]

    resenas_creadas = []
    usuarios_usados = set()

    for i in range(num_resenas):
        # Seleccionar un usuario que no haya hecho reseña
        usuario_alumno = None
        for u in usuarios_disponibles:
            if u.id_usuario not in usuarios_usados:
                # Verificar que no tenga ya una reseña
                resena_existente = obtener_resenas_por_alumno(
                    db,
                    u.id_usuario,
                    id_entrenador
                )
                if not resena_existente:
                    usuario_alumno = u
                    usuarios_usados.add(u.id_usuario)
                    break

        if not usuario_alumno:
            continue

        # Generar calificación aleatoria (tendencia hacia calificaciones altas)
        calificacion = random.choices(
            [1, 2, 3, 4, 5],
            weights=[1, 2, 5, 15, 20],  # Mayor probabilidad de 4 y 5
            k=1
        )[0]

        # Seleccionar comentario basado en la calificación
        if calificacion >= 4:
            comentario = random.choice(comentarios_ejemplo[:10])
        elif calificacion == 3:
            comentario = random.choice(comentarios_ejemplo[10:15])
        else:
            comentario = random.choice(comentarios_ejemplo[15:])

        resena_data = ResenaCreate(
            id_entrenador=id_entrenador,
            calificacion=calificacion,
            comentario=comentario
        )

        try:
            resena = crear_resena(db, usuario_alumno.id_usuario, resena_data)

            # Simular fecha de creación aleatoria (últimos 6 meses)
            dias_atras = random.randint(1, 180)
            resena.fecha_resena = datetime.utcnow() - timedelta(days=dias_atras)
            db.add(resena)

            resenas_creadas.append({
                "id": resena.id_resena,
                "alumno": usuario_alumno.nombre,
                "calificacion": calificacion,
                "comentario": comentario[:50] + "..." if len(comentario) > 50 else comentario
            })
        except Exception as e:
            print(f"Error creando reseña: {e}")
            continue

    db.commit()

    # Recalcular estadísticas
    stats = obtener_estadisticas_entrenador(db, id_entrenador)

    return {
        "mensaje": f"Reseñas de prueba creadas para el entrenador {entrenador.nombre}",
        "entrenador": {
            "id": id_entrenador,
            "nombre": entrenador.nombre
        },
        "resenas_creadas": len(resenas_creadas),
        "estadisticas_actualizadas": {
            "promedio_calificacion": stats.promedio_calificacion,
            "total_resenas": stats.total_resenas
        },
        "primeras_resenas": resenas_creadas[:3]
    }


@router.delete("/test/limpiar-entrenador/{id_entrenador}", status_code=status.HTTP_204_NO_CONTENT)
def limpiar_resenas_entrenador_test(
        id_entrenador: int,
        db: Session = Depends(get_db),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Elimina TODAS las reseñas de un entrenador (para limpiar pruebas)
    """
    from models.review import Resena

    # Eliminar todas las reseñas del entrenador
    resenas_eliminadas = db.query(Resena).filter(
        Resena.id_entrenador == id_entrenador
    ).delete()

    db.commit()

    return None


@router.delete("/test/limpiar-usuario/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def limpiar_resenas_usuario_test(
        user_id: int,
        db: Session = Depends(get_db),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Elimina TODAS las reseñas hechas por un usuario (para limpiar pruebas)
    """
    from models.review import Resena

    # Eliminar todas las reseñas del usuario
    resenas_eliminadas = db.query(Resena).filter(
        Resena.id_alumno == user_id
    ).delete()

    db.commit()

    return None



@router.post("/test/actualizar-calificacion/{id_resena}")
def actualizar_calificacion_test(
        id_resena: int,
        nueva_calificacion: int = Query(..., ge=1, le=5, description="Nueva calificación (1-5)"),
        db: Session = Depends(get_db),
):
    """
    🔧 ENDPOINT DE PRUEBA - NO USAR EN PRODUCCIÓN

    Actualiza rápidamente la calificación de una reseña (sin validación de permisos)
    """
    from models.review import Resena

    resena = db.query(Resena).filter(Resena.id_resena == id_resena).first()
    if not resena:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")

    calificacion_anterior = resena.calificacion
    resena.calificacion = nueva_calificacion
    db.add(resena)
    db.commit()

    return {
        "mensaje": "Calificación actualizada",
        "id_resena": id_resena,
        "calificacion_anterior": calificacion_anterior,
        "calificacion_nueva": nueva_calificacion
    }