# services/review_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from models.review import Resena
from models.user import Usuario
from schemas.review import ResenaCreate, ResenaUpdate, EstadisticasEntrenador
from datetime import datetime


def crear_resena(db: Session, id_alumno: int, data: ResenaCreate) -> dict:
    """Crea una nueva reseña del alumno hacia el entrenador"""
    resena_data = {
        "id_entrenador": data.id_entrenador,
        "id_alumno": id_alumno,
        "calificacion": data.calificacion,
        "fecha_creacion": datetime.utcnow(),
        "fecha_actualizacion": datetime.utcnow()
    }

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

    resena = Resena(**resena_data)
    db.add(resena)
    db.commit()
    db.refresh(resena)

    print(f"[DEBUG] Reseña creada con ID: {resena.id_resena}")
    return _enriquecer_resena(db, resena)


def obtener_resena(db: Session, id_resena: int) -> dict | None:
    """Obtiene una reseña específica"""
    resena = db.query(Resena).filter(Resena.id_resena == id_resena).first()
    if resena:
        print(f"[DEBUG] Reseña encontrada: ID={resena.id_resena}")
        return _enriquecer_resena(db, resena)
    else:
        print(f"[DEBUG] Reseña con ID={id_resena} no encontrada")
    return None


def actualizar_resena(db: Session, id_resena: int, data: ResenaUpdate) -> dict | None:
    """Actualiza una reseña existente"""
    resena = db.query(Resena).filter(Resena.id_resena == id_resena).first()
    if not resena:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(resena, field, value)

    resena.fecha_actualizacion = datetime.utcnow()
    db.add(resena)
    db.commit()
    db.refresh(resena)

    print(f"[DEBUG] Reseña {id_resena} actualizada")
    return _enriquecer_resena(db, resena)


def eliminar_resena(db: Session, id_resena: int) -> bool:
    """Elimina una reseña"""
    resena = db.query(Resena).filter(Resena.id_resena == id_resena).first()
    if not resena:
        return False

    db.delete(resena)
    db.commit()
    print(f"[DEBUG] Reseña {id_resena} eliminada")
    return True


def obtener_resenas_entrenador(db: Session, id_entrenador: int, limit: int = 10) -> list[dict]:
    """Obtiene todas las reseñas de un entrenador"""
    resenas = db.query(Resena) \
        .filter(Resena.id_entrenador == id_entrenador) \
        .order_by(Resena.fecha_creacion.desc()) \
        .limit(limit) \
        .all()

    print(f"[DEBUG] Encontradas {len(resenas)} reseñas para entrenador {id_entrenador}")

    # ✅ Enriquecer cada reseña con datos del alumno
    resenas_enriquecidas = [_enriquecer_resena(db, r) for r in resenas]
    return resenas_enriquecidas


def obtener_estadisticas_entrenador(db: Session, id_entrenador: int) -> EstadisticasEntrenador:
    """Calcula estadísticas de calificación de un entrenador"""
    resenas = db.query(Resena) \
        .filter(Resena.id_entrenador == id_entrenador) \
        .order_by(Resena.fecha_creacion.desc()) \
        .limit(100) \
        .all()

    if not resenas:
        return EstadisticasEntrenador(
            id_entrenador=id_entrenador,
            promedio_calificacion=0.0,
            total_resenas=0,
            resenas_recientes=[]
        )

    calificacion_promedio = sum(r.calificacion for r in resenas) / len(resenas)

    # ✅ Enriquecer las reseñas recientes
    resenas_recientes_enriquecidas = [_enriquecer_resena(db, r) for r in resenas[:5]]

    return EstadisticasEntrenador(
        id_entrenador=id_entrenador,
        promedio_calificacion=round(calificacion_promedio, 2),
        total_resenas=len(resenas),
        resenas_recientes=resenas_recientes_enriquecidas
    )


def obtener_resenas_por_alumno(db: Session, id_alumno: int, id_entrenador: int) -> dict | None:
    """Obtiene la reseña del alumno hacia el entrenador (si existe)"""
    resena = db.query(Resena).filter(
        Resena.id_alumno == id_alumno,
        Resena.id_entrenador == id_entrenador
    ).first()

    if resena:
        print(f"[DEBUG] Encontrada reseña del alumno {id_alumno} para entrenador {id_entrenador}")
        return _enriquecer_resena(db, resena)
    return None


def _enriquecer_resena(db: Session, resena: Resena) -> dict:
    """
    Enriquece una reseña con datos del alumno (nombre, foto)
    """
    alumno = db.query(Usuario).filter(Usuario.id_usuario == resena.id_alumno).first()

    resena_dict = {
        "id_resena": resena.id_resena,
        "id_entrenador": resena.id_entrenador,
        "id_alumno": resena.id_alumno,
        "calificacion": resena.calificacion,
        "titulo": resena.titulo,
        "comentario": resena.comentario,
        "calidad_rutina": resena.calidad_rutina,
        "comunicacion": resena.comunicacion,
        "disponibilidad": resena.disponibilidad,
        "resultados": resena.resultados,
        "fecha_creacion": resena.fecha_creacion,
        "fecha_actualizacion": resena.fecha_actualizacion,
        # ✅ AGREGAR ESTA LÍNEA:
        "fecha_resena": resena.fecha_creacion,  # ← Para que el frontend lo reciba
        # ✅ Agregar datos del alumno
        "nombreAlumno": alumno.nombre if alumno else "Cliente Anónimo",
        "nombre_alumno": alumno.nombre if alumno else "Cliente Anónimo",
        "fotoAlumno": alumno.foto_url if alumno else None,
    }

    return resena_dict


def obtener_todas_resenas(db: Session, limit: int = 100) -> list[dict]:
    """Obtiene todas las reseñas del sistema (para debugging)"""
    resenas = db.query(Resena).limit(limit).all()
    resenas_enriquecidas = [_enriquecer_resena(db, r) for r in resenas]
    print(f"[DEBUG] Total de reseñas en el sistema: {len(resenas_enriquecidas)}")
    return resenas_enriquecidas


def contar_resenas_total(db: Session) -> int:
    """Cuenta el total de reseñas en el sistema"""
    total = db.query(func.count(Resena.id_resena)).scalar()
    print(f"[DEBUG] Total de reseñas en BD: {total}")
    return total or 0