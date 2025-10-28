# dependencies.py
from __future__ import annotations
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session, defer
import os, jwt

from typing import Generator, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import os
from config.database import get_db
from models.user import Usuario
from config.database import SessionLocal
from utils.security import decode_token, JWT_SECRET, JWT_ALG
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

def get_current_user(
    db: Session = Depends(get_db),
    Authorization: str | None = Header(None),
) -> Usuario:
    if not Authorization or not Authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Falta header Authorization Bearer")

    token = Authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

    uid = payload.get("sub")
    try:
        uid = int(uid)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido (sub)")

    # ⚠️ Evita mapear ENUM inválidos
    user = (
        db.query(Usuario)
        .options(defer(Usuario.sexo))   # <— clave
        .filter(Usuario.id_usuario == uid)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return user

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
