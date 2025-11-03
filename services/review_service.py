# services/review_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from models.review import Resena
from models.user import Usuario
from schemas.review import ResenaCreate, ResenaUpdate, EstadisticasEntrenador
from datetime import datetime


def crear_resena(db: Session, id_alumno: int, data: ResenaCreate) -> Resena:
    """Crea una nueva reseña del alumno hacia el entrenador"""
    resena = Resena(
        id_entrenador=data.id_entrenador,
        id_alumno=id_alumno,
        calificacion=data.calificacion,
        titulo=data.titulo,
        comentario=data.comentario,
        calidad_rutina=data.calidad_rutina,
        comunicacion=data.comunicacion,
        disponibilidad=data.disponibilidad,
        resultados=data.resultados,
    )
    db.add(resena)
    db.commit()
    db.refresh(resena)
    return resena


def obtener_resena(db: Session, id_resena: int) -> Resena | None:
    """Obtiene una reseña específica"""
    return db.query(Resena).filter(Resena.id_resena == id_resena).first()


def actualizar_resena(db: Session, id_resena: int, data: ResenaUpdate) -> Resena | None:
    """Actualiza una reseña existente"""
    resena = obtener_resena(db, id_resena)
    if not resena:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(resena, field, value)

    resena.fecha_actualizacion = datetime.utcnow()
    db.add(resena)
    db.commit()
    db.refresh(resena)
    return resena


def eliminar_resena(db: Session, id_resena: int) -> bool:
    """Elimina una reseña"""
    resena = obtener_resena(db, id_resena)
    if not resena:
        return False

    db.delete(resena)
    db.commit()
    return True


def obtener_resenas_entrenador(db: Session, id_entrenador: int, limit: int = 10) -> list[Resena]:
    """Obtiene todas las reseñas de un entrenador"""
    return db.query(Resena) \
        .filter(Resena.id_entrenador == id_entrenador) \
        .order_by(Resena.fecha_creacion.desc()) \
        .limit(limit) \
        .all()


def obtener_estadisticas_entrenador(db: Session, id_entrenador: int) -> EstadisticasEntrenador:
    """Calcula estadísticas de calificación de un entrenador"""
    resenas = obtener_resenas_entrenador(db, id_entrenador, limit=100)

    if not resenas:
        return EstadisticasEntrenador(
            id_entrenador=id_entrenador,
            calificacion_promedio=0.0,
            total_resenas=0,
            resenas_recientes=[]
        )

    calificacion_promedio = sum(r.calificacion for r in resenas) / len(resenas)

    return EstadisticasEntrenador(
        id_entrenador=id_entrenador,
        calificacion_promedio=round(calificacion_promedio, 2),
        total_resenas=len(resenas),
        resenas_recientes=[r for r in resenas[:5]]
    )


def obtener_resenas_por_alumno(db: Session, id_alumno: int, id_entrenador: int) -> Resena | None:
    """Obtiene la reseña del alumno hacia el entrenador (si existe)"""
    return db.query(Resena).filter(
        Resena.id_alumno == id_alumno,
        Resena.id_entrenador == id_entrenador
    ).first()