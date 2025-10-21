# routers/exercises.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from utils.dependencies import get_db
from schemas.exercise import EjercicioCreate, EjercicioOut
from services.exercise_service import create_exercise, list_exercises
from typing import List

router = APIRouter(prefix="/ejercicios", tags=["ejercicios"])

@router.post("", response_model=EjercicioOut)
def create(body: EjercicioCreate, db: Session = Depends(get_db)):
    return create_exercise(db, body)

@router.get("", response_model=List[EjercicioOut])
def list_(db: Session = Depends(get_db)):
    return list_exercises(db)
