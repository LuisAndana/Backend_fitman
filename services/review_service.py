# services/review_service_fixed.py
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from models.review import Resena
from models.user import Usuario
from schemas.review import ResenaCreate, ResenaUpdate, EstadisticasEntrenador
from datetime import datetime


def crear_resena(db: Session, id_alumno: int, data: ResenaCreate) -> Resena:
    """Crea una nueva reseña del alumno hacia el entrenador"""
    # Crear diccionario con solo los campos que vienen en data
    resena_data = {
        "id_entrenador": data.id_entrenador,
        "id_alumno": id_alumno,
        "calificacion": data.calificacion,
        "fecha_creacion": datetime.utcnow(),
        "fecha_actualizacion": datetime.utcnow()
    }

    # Agregar campos opcionales solo si vienen en data
    if hasattr(data, 'titulo') and data.titulo is not None:
        resena_data["titulo"] = data.titulo
    if hasattr(data, 'comentario') and data.comentario is not None:
        resena_data["comentario"] = data.comentario
    if hasattr(data, 'calidad_rutina') and data.calidad_rutina is not None:
        resena_data["calidad_rutina"] = data.calidad_rutina
    if hasattr(data, 'comunicacion') and data.comunicacion is not None:
        resena_data["comunicacion"] = data.comunicacion
    if hasattr(data, 'disponibilidad') and data.disponibilidad is not None:
        resena_data["disponibilidad"] = data.disponibilidad
    if hasattr(data, 'resultados') and data.resultados is not None:
        resena_data["resultados"] = data.resultados

    # Crear la reseña con solo los campos que tienen valor
    resena = Resena(**resena_data)

    db.add(resena)
    db.commit()
    db.refresh(resena)

    print(f"[DEBUG] Reseña creada con ID: {resena.id_resena}")
    return resena


def obtener_resena(db: Session, id_resena: int) -> Resena | None:
    """Obtiene una reseña específica"""
    resena = db.query(Resena).filter(Resena.id_resena == id_resena).first()
    if resena:
        print(f"[DEBUG] Reseña encontrada: ID={resena.id_resena}")
    else:
        print(f"[DEBUG] Reseña con ID={id_resena} no encontrada")
    return resena


def actualizar_resena(db: Session, id_resena: int, data: ResenaUpdate) -> Resena | None:
    """Actualiza una reseña existente"""
    resena = obtener_resena(db, id_resena)
    if not resena:
        return None

    # Solo actualizar campos que vienen en el payload
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:  # Solo actualizar si el valor no es None
            setattr(resena, field, value)

    resena.fecha_actualizacion = datetime.utcnow()
    db.add(resena)
    db.commit()
    db.refresh(resena)

    print(f"[DEBUG] Reseña {id_resena} actualizada")
    return resena


def eliminar_resena(db: Session, id_resena: int) -> bool:
    """Elimina una reseña"""
    resena = obtener_resena(db, id_resena)
    if not resena:
        return False

    db.delete(resena)
    db.commit()
    print(f"[DEBUG] Reseña {id_resena} eliminada")
    return True


def obtener_resenas_entrenador(db: Session, id_entrenador: int, limit: int = 10) -> list[Resena]:
    """Obtiene todas las reseñas de un entrenador"""
    resenas = db.query(Resena) \
        .filter(Resena.id_entrenador == id_entrenador) \
        .order_by(Resena.fecha_creacion.desc()) \
        .limit(limit) \
        .all()

    print(f"[DEBUG] Encontradas {len(resenas)} reseñas para entrenador {id_entrenador}")
    return resenas


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

    # En el esquema original era 'promedio_calificacion', corregir el nombre
    return EstadisticasEntrenador(
        id_entrenador=id_entrenador,
        promedio_calificacion=round(calificacion_promedio, 2),  # Cambio aquí
        total_resenas=len(resenas),
        resenas_recientes=[r for r in resenas[:5]]
    )


def obtener_resenas_por_alumno(db: Session, id_alumno: int, id_entrenador: int) -> Resena | None:
    """Obtiene la reseña del alumno hacia el entrenador (si existe)"""
    resena = db.query(Resena).filter(
        Resena.id_alumno == id_alumno,
        Resena.id_entrenador == id_entrenador
    ).first()

    if resena:
        print(f"[DEBUG] Encontrada reseña del alumno {id_alumno} para entrenador {id_entrenador}")
    return resena


# Funciones adicionales de utilidad
def obtener_todas_resenas(db: Session, limit: int = 100) -> list[Resena]:
    """Obtiene todas las reseñas del sistema (para debugging)"""
    resenas = db.query(Resena).limit(limit).all()
    print(f"[DEBUG] Total de reseñas en el sistema: {len(resenas)}")
    return resenas


def contar_resenas_total(db: Session) -> int:
    """Cuenta el total de reseñas en el sistema"""
    total = db.query(func.count(Resena.id_resena)).scalar()
    print(f"[DEBUG] Total de reseñas en BD: {total}")
    return total or 0