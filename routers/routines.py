# routers/routines.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from utils.dependencies import get_db, get_current_user
from schemas.routine import RutinaCreate, RutinaOut
from services.routine_service import create_routine

router = APIRouter(prefix="/rutinas", tags=["rutinas"])

@router.post("", response_model=RutinaOut)
def create(body: RutinaCreate, db: Session = Depends(get_db), current = Depends(get_current_user())):
    return create_routine(db, current.id_usuario, body)
