# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from utils.dependencies import get_db
from schemas.auth import LoginIn, TokenOut
from services.user_service import get_by_email
from utils.security import verify_password, create_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = get_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password):
        # OJO: tus datos iniciales tienen passwords en texto plano; si importas esos,
        # tendrás que rehacer hash al crear usuarios nuevos.
        raise HTTPException(status_code=400, detail="Credenciales inválidas")
    token = create_token({"sub": user.id_usuario, "rol": user.rol})
    return {"access_token": token}
