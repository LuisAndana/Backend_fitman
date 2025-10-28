# utils/passwords.py
from __future__ import annotations
from typing import Union
import os

# Activa logs de depuración poniendo DEBUG_AUTH=1 al arrancar Uvicorn
DEBUG = os.getenv("DEBUG_AUTH") in {"1", "true", "True"}

def _log(*args):
    if DEBUG:
        print("[passwords]", *args)

def _to_str(x: Union[str, bytes, bytearray, None]) -> str:
    if x is None:
        return ""
    if isinstance(x, (bytes, bytearray)):
        return x.decode("utf-8", "ignore")
    return str(x)

def _normalize_wrappers(s: str) -> str:
    """
    Quita envolturas comunes: {bcrypt}$2b$..., {PLAIN}contraseña, etc.
    """
    st = s.strip()
    if st.startswith("{bcrypt}"):
        st = st[len("{bcrypt}"):].strip()
    if st.startswith("{PLAIN}") or st.startswith("{plain}"):
        st = st.split("}", 1)[-1].strip()
    return st

def hash_password(plain: str) -> str:
    import bcrypt
    p = _to_str(plain).strip()
    h = bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    _log("hash ->", h[:20], "... len", len(h))
    return h

def verify_password(plain: str, stored: Union[str, bytes, bytearray, None]) -> bool:
    p = _to_str(plain).strip()
    s = _normalize_wrappers(_to_str(stored))
    _log("verify prefix:", s[:20], "... len", len(s))

    # 1) bcrypt nativo
    if s.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            import bcrypt
            ok = bcrypt.checkpw(p.encode("utf-8"), s.encode("utf-8"))
            _log("path=bcrypt ->", ok)
            return ok
        except Exception as e:
            _log("bcrypt error:", repr(e))
            return False

    # 2) formatos passlib (pbkdf2, argon2, bcrypt_sha256)
    try:
        if s.startswith("$pbkdf2-sha256$") or s.startswith("pbkdf2_sha256$") or s.startswith("pbkdf2:"):
            from passlib.hash import pbkdf2_sha256
            ok = pbkdf2_sha256.verify(p, s)
            _log("path=pbkdf2_sha256 ->", ok)
            return ok
        if s.startswith("$argon2"):
            from passlib.hash import argon2
            ok = argon2.verify(p, s)
            _log("path=argon2 ->", ok)
            return ok
        if s.startswith("$bcrypt-sha256$"):
            from passlib.hash import bcrypt_sha256
            ok = bcrypt_sha256.verify(p, s)
            _log("path=bcrypt_sha256 ->", ok)
            return ok
    except Exception as e:
        _log("passlib error:", repr(e))

    # 3) texto plano (LEGADO)
    ok = (s == p)
    _log("path=plaintext ->", ok)
    return ok

__all__ = ["hash_password", "verify_password"]
