# services/assignment_service.py
from sqlalchemy.orm import Session
from models.assignment import Asignacion

def assign_routine(db: Session, id_rutina: int, id_alumno: int):
    a = Asignacion(id_rutina=id_rutina, id_alumno=id_alumno)
    db.add(a); db.commit(); db.refresh(a); return a
3