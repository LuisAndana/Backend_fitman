from __future__ import annotations
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session, defer
from typing import Generator, Optional
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
import os

from config.database import SessionLocal
from models.user import Usuario

# Configuración del JWT
JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

# -------------------------------
# Sesión de base de datos
# -------------------------------
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------
# Autenticación obligatoria
# -------------------------------
def get_current_user(
    db: Session = Depends(get_db),
    Authorization: str | None = Header(None),
) -> Usuario:
    """Obtiene el usuario actual (requiere token válido)"""
    if not Authorization or not Authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Falta header Authorization Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = Authorization.split(" ", 1)[1].strip()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token sin 'sub'")

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="User ID inválido")

    user = (
        db.query(Usuario)
        .options(defer(Usuario.sexo))
        .filter(Usuario.id_usuario == user_id)
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return user

# -------------------------------
# Autenticación opcional
# -------------------------------
def get_optional_user(
    db: Session = Depends(get_db),
    Authorization: Optional[str] = Header(None),
) -> Optional[Usuario]:
    """
    Intenta obtener el usuario actual.
    Si no hay token o es inválido, devuelve None en lugar de lanzar error.
    """
    if not Authorization or not Authorization.lower().startswith("bearer "):
        return None

    token = Authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except (ExpiredSignatureError, JWTError):
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return None

    return (
        db.query(Usuario)
        .options(defer(Usuario.sexo))
        .filter(Usuario.id_usuario == user_id)
        .first()
    )
