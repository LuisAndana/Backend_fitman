# routers/resenas.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from utils.dependencies import get_db, get_current_user
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
        payload: ResenaCreate,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Crea una nueva reseña/calificación para un entrenador"""
    if current.id_usuario == payload.id_entrenador:
        raise HTTPException(
            status_code=400,
            detail="No puedes calificarte a ti mismo"
        )

    resena_existente = obtener_resenas_por_alumno(
        db,
        current.id_usuario,
        payload.id_entrenador
    )
    if resena_existente:
        raise HTTPException(
            status_code=409,
            detail="Ya has calificado a este entrenador"
        )

    resena = crear_resena(db, current.id_usuario, payload)
    return resena


@router.get("/{id_resena}", response_model=ResenaOut)
def obtener_resena_endpoint(
        id_resena: int,
        db: Session = Depends(get_db),
):
    """Obtiene una reseña específica"""
    resena = obtener_resena(db, id_resena)
    if not resena:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    return resena


@router.patch("/{id_resena}", response_model=ResenaOut)
def actualizar_resena_endpoint(
        id_resena: int,
        payload: ResenaUpdate,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Actualiza una reseña (solo el autor puede hacerlo)"""
    resena = obtener_resena(db, id_resena)
    if not resena:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")

    if resena.id_alumno != current.id_usuario:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para editar esta reseña"
        )

    resena_actualizada = actualizar_resena(db, id_resena, payload)
    return resena_actualizada


@router.delete("/{id_resena}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_resena_endpoint(
        id_resena: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Elimina una reseña (solo el autor puede hacerlo)"""
    resena = obtener_resena(db, id_resena)
    if not resena:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")

    if resena.id_alumno != current.id_usuario:
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
    """Obtiene todas las reseñas de un entrenador"""
    resenas = obtener_resenas_entrenador(db, id_entrenador, limit=limit)
    return resenas


@router.get("/entrenador/{id_entrenador}/estadisticas", response_model=EstadisticasEntrenador)
def obtener_estadisticas_endpoint(
        id_entrenador: int,
        db: Session = Depends(get_db),
):
    """Obtiene las estadísticas de calificación de un entrenador"""
    stats = obtener_estadisticas_entrenador(db, id_entrenador)
    return stats


@router.get("/mi-resena/{id_entrenador}", response_model=ResenaOut | None)
def obtener_mi_resena_endpoint(
        id_entrenador: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene la reseña del usuario actual hacia un entrenador"""
    resena = obtener_resenas_por_alumno(db, current.id_usuario, id_entrenador)
    if not resena:
        return None
    return resena