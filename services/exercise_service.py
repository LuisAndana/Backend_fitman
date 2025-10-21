# services/exercise_service.py
from sqlalchemy.orm import Session
from models.exercise import Ejercicio
from schemas.exercise import EjercicioCreate

def create_exercise(db: Session, data: EjercicioCreate):
    e = Ejercicio(**data.model_dump())
    db.add(e); db.commit(); db.refresh(e); return e

def list_exercises(db: Session):
    return db.query(Ejercicio).all()
