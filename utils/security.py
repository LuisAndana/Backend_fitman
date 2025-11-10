# utils/security.py
from __future__ import annotations

from jose import jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


from dotenv import load_dotenv, find_dotenv

# ✅ Sin dependencias nativas, sin límite de 72 bytes
pwd_ctx = CryptContext(
    schemes=["pbkdf2_sha256"],   # puedes añadir "bcrypt" si MAÑANA quieres verificar hashes viejos
    deprecated="auto"
)

def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_ctx.verify(plain, hashed)
    except UnknownHashError:
        return False

def needs_update(hashed: str) -> bool:
    try:
        return pwd_ctx.needs_update(hashed)
    except UnknownHashError:
        return True


def create_token(
    data: Dict[str, Any],
    expires_in: int = 60 * 60,  # 1 hora por defecto
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """
    Crea un JWT firmado. 'data' debe incluir al menos 'sub' (id de usuario).
    """
    now = datetime.now(timezone.utc)

    # Normaliza 'sub' a string
    if "sub" in data:
        data = {**data, "sub": str(data["sub"])}

    payload: Dict[str, Any] = {
        **data,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    token: str = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    return token

# Cargar .env (usa el .env en la raíz del proyecto)
load_dotenv(find_dotenv(usecwd=True))

JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secreto")
JWT_ALG: str = os.getenv("JWT_ALG", "HS256")

def decode_token(
    token: str,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    leeway_seconds: int = 10,
) -> Dict[str, Any]:
    """
    Valida y decodifica un JWT. Lanza ValueError con mensaje claro si es inválido/expirado.
    """
    try:
        options = {"require": ["exp", "iat"], "verify_exp": True}
        kwargs: Dict[str, Any] = {
            "key": JWT_SECRET,
            "algorithms": [JWT_ALG],
            "options": options,
            "leeway": leeway_seconds,
        }
        if issuer:
            kwargs["issuer"] = issuer
        if audience:
            kwargs["audience"] = audience

        payload = jwt.decode(token, **kwargs)

        # Normaliza 'sub' a string por consistencia
        if "sub" in payload:
            payload["sub"] = str(payload["sub"])
        return payload

    except jwt.ExpiredSignatureError:
        raise ValueError("El token ha expirado")
    except jwt.InvalidIssuerError:
        raise ValueError("Issuer inválido")
    except jwt.InvalidAudienceError:
        raise ValueError("Audiencia inválida")
    except jwt.InvalidTokenError:
        raise ValueError("Token inválido")