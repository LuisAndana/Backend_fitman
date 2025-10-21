# dependencies.py
from __future__ import annotations

from typing import Generator, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import os
from config.database import get_db
from models.user import Usuario
from config.database import SessionLocal
from utils.security import decode_token
from models.user import Usuario


def get_db() -> Generator[Session, None, None]:
    """
    Crea una sesión de SQLAlchemy por request y la cierra al finalizar.
    ¡IMPORTANTE!: usar yield (no return).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

SECRET = os.getenv("JWT_SECRET", "devsecret")
ALGO = os.getenv("JWT_ALGO", "HS256")

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Usuario:
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Falta token")

    token = auth.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Token inválido")
        uid = int(sub)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido/expirado")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

    u = db.query(Usuario).filter(Usuario.id_usuario == uid).first()
    if not u:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    return u

    # 2) Decodificar y validar payload
    try:
        payload = decode_token(tok)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin 'sub'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3) Cast seguro a int (por si viene como string)
    try:
        user_id_int = int(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario inválido en el token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4) Buscar usuario en la BD
    user = db.get(Usuario, user_id_int)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no existe",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
