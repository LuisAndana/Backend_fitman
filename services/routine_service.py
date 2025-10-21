# services/routine_service.py
from sqlalchemy.orm import Session
from models.routine import Rutina
from models.routine_exercise import RutinaEjercicio
from schemas.routine import RutinaCreate

def create_routine(db: Session, creator_id: int, data: RutinaCreate):
    r = Rutina(nombre=data.nombre, descripcion=data.descripcion, creado_por=creator_id)
    db.add(r); db.flush()
    for it in data.items:
        db.add(RutinaEjercicio(
            id_rutina=r.id_rutina, id_ejercicio=it.id_ejercicio,
            series=it.series, repeticiones=it.repeticiones, descanso_segundos=it.descanso_segundos
        ))
    db.commit(); db.refresh(r)
    return r
