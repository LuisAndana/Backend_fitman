# main.py
from fastapi import FastAPI, HTTPException, Depends, APIRouter, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session, defer
from sqlalchemy.exc import IntegrityError
from sqlalchemy import insert, select

# Unificar helpers
from utils.passwords import verify_password, hash_password
from utils.dependencies import get_db   # <- usa SIEMPRE get_db desde utils.dependencies
from models.user import Usuario

from google.oauth2 import id_token
from google.auth.transport.requests import Request as GRequest

import os, datetime, jwt

# Importa routers exportados desde routers/__init__.py
from routers import (
    usuarios_router,
    entrenadores_router,
    ejercicios_router,
    rutinas_router,
    asignaciones_router, usuarios,
)

app = FastAPI(title="FitCoach API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
    allow_headers=["Authorization","Content-Type","Accept","X-Requested-With","*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


CLIENT_ID    = "144363202163-juhhgsrj47dp46co5bevehtmrpo54h9n.apps.googleusercontent.com"
JWT_SECRET   = os.getenv("JWT_SECRET", "cambia-esto-en-produccion")
JWT_ALG      = "HS256"
JWT_EXP_DAYS = 7
VALID_ROLES  = {"alumno","entrenador"}

auth_router = APIRouter(prefix="/auth", tags=["Auth"])

def _role_str(obj) -> str:
    r = getattr(obj, "rol", obj)
    if hasattr(r, "value"):
        r = r.value
    return (str(r) if r is not None else "alumno").lower()

def make_token(user: Usuario) -> str:
    now = datetime.datetime.utcnow()
    user_id = getattr(user, "id_usuario", None) or getattr(user, "id", None)
    if not user_id:
        raise HTTPException(status_code=500, detail="Usuario sin ID válido al generar token")
    provider = getattr(user, "auth_provider", None) or "local"
    payload = {
        "sub": str(user_id),
        "email": getattr(user, "email", ""),
        "rol": _role_str(user),
        "provider": provider,
        "iat": now,
        "exp": now + datetime.timedelta(days=JWT_EXP_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def _insert_user_core(db: Session, values: dict) -> Usuario:
    cols = list(Usuario.__table__.columns)
    model_cols = {c.name for c in cols}
    computed_cols = {c.name for c in cols if getattr(c, "computed", None) is not None}
    forbidden = {"imc"} | computed_cols
    clean = {k: v for k, v in values.items() if k in model_cols and v is not None and k not in forbidden}
    if not clean:
        raise HTTPException(status_code=500, detail="No hay columnas válidas para insertar")
    res = db.execute(insert(Usuario.__table__).values(**clean))
    db.commit()
    new_id = getattr(res, "lastrowid", None) or getattr(res, "inserted_primary_key", [None])[0]
    return db.execute(select(Usuario).where(Usuario.id_usuario == new_id)).scalar_one()

class LoginCred(BaseModel):
    email: str
    password: str

class GoogleCred(BaseModel):
    credential: str
    rol: str | None = None

def _normalize_rol_input(raw: str | None) -> str | None:
    if not raw: return None
    r = raw.strip().lower()
    if r in {"cliente","user","empleado"}: return "alumno"
    if r in {"coach","trainer"}: return "entrenador"
    return r

def _coerce_role_value(raw: str | None):
    norm = _normalize_rol_input(raw)
    col = Usuario.__table__.columns.get("rol")
    if col is None:
        return None
    t = getattr(col, "type", None)
    enum_cls = getattr(t, "enum_class", None)
    if enum_cls is not None:
        if norm is None:
            raise HTTPException(status_code=422, detail="Debes seleccionar un rol.")
        for m in enum_cls:
            if str(m.value).lower() == norm or m.name.lower() == norm:
                return m
        raise HTTPException(status_code=422, detail="Rol inválido. Usa 'alumno' o 'entrenador'.")
    enums = getattr(t, "enums", None)
    if enums:
        if norm is None:
            raise HTTPException(status_code=422, detail="Debes seleccionar un rol.")
        if norm in enums or any(e.lower()==norm for e in enums):
            return next(e for e in enums if e.lower()==norm) if norm not in enums else norm
        raise HTTPException(status_code=422, detail=f"Rol inválido. Permitidos: {', '.join(enums)}.")
    if norm not in VALID_ROLES:
        raise HTTPException(status_code=422, detail="Rol inválido. Usa 'alumno' o 'entrenador'.")
    return norm

def _is_google_only(user: Usuario) -> bool:
    pwd = (getattr(user, "password", "") or "").strip()
    has_real = bool(pwd) and pwd.upper() not in {"GOOGLE","GOOGLE_OAUTH_ONLY"}
    if has_real: return False
    provider = getattr(user, "auth_provider", None)
    has_sub = bool(getattr(user, "google_sub", None))
    is_placeholder = pwd.upper() in {"GOOGLE","GOOGLE_OAUTH_ONLY"}
    return (provider=="google") or has_sub or is_placeholder

def _password_login_logic(payload: LoginCred, db: Session) -> dict:
    email = payload.email.strip().lower()
    user = db.query(Usuario).options(defer(Usuario.sexo)).filter(Usuario.email==email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if _is_google_only(user):
        raise HTTPException(status_code=400, detail="Esta cuenta está vinculada a Google. Usa 'Continuar con Google'.")

    db_pwd = getattr(user, "password", "") or ""
    if isinstance(db_pwd, (bytes, bytearray)): db_pwd = db_pwd.decode("utf-8", "ignore")
    db_pwd = db_pwd.rstrip()

    ok = verify_password(payload.password, db_pwd)
    if not ok and db_pwd and db_pwd == payload.password.strip():
        user.password = hash_password(payload.password.strip())
        db.add(user); db.commit(); ok = True
    if not ok:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

    if not getattr(user, "auth_provider", None):
        try:
            user.auth_provider = "local"; db.add(user); db.commit()
        except Exception: pass

    token = make_token(user)
    resp_usuario = {
        "id": getattr(user,"id_usuario", getattr(user,"id",None)),
        "nombre":   getattr(user,"nombre",None) or getattr(user,"nombres","") or "",
        "apellido": getattr(user,"apellido",None) or getattr(user,"apellidos","") or "",
        "email": user.email,
        "rol": _role_str(user),
        "auth_provider": getattr(user,"auth_provider","local"),
    }
    return {"ok": True, "token": token, "usuario": resp_usuario}

def _current_user(db: Session = Depends(get_db), Authorization: str | None = Header(None)) -> Usuario:
    if not Authorization or not Authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Falta header Authorization Bearer")
    token = Authorization.split(" ",1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")
    user_id = payload.get("sub")
    try:
        user_id = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido (sub)")
    user = db.query(Usuario).options(defer(Usuario.sexo)).filter(Usuario.id_usuario==user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user

@auth_router.post("/login")
def auth_login(payload: LoginCred, db: Session = Depends(get_db)):
    return _password_login_logic(payload, db)

@auth_router.post("/google_signin")
def google_signin(payload: GoogleCred, db: Session = Depends(get_db)):
    try:
        info = id_token.verify_oauth2_token(payload.credential, GRequest(), CLIENT_ID)
    except Exception:
        raise HTTPException(status_code=401, detail="Token de Google inválido")
    sub   = info.get("sub")
    email = info.get("email")
    if not email:
        raise HTTPException(status_code=422, detail="Google no devolvió email")
    given  = (info.get("given_name") or "").strip()
    family = (info.get("family_name") or "").strip()
    name   = (info.get("name") or "").strip()
    picture = info.get("picture")

    if not given and name:
        parts = name.split()
        given = parts[0]; family = " ".join(parts[1:]) if len(parts) > 1 else ""

    cols = set(Usuario.__table__.columns.keys())
    has  = lambda c: c in cols

    user = db.query(Usuario).options(defer(Usuario.sexo)).filter(Usuario.google_sub==sub).first() if has("google_sub") and sub else None
    if not user:
        user = db.query(Usuario).options(defer(Usuario.sexo)).filter(Usuario.email==email).first()

    from sqlalchemy.exc import IntegrityError
    try:
        if user:
            if has("google_sub") and sub: user.google_sub = sub
            if has("auth_provider"): user.auth_provider = "google"
            if picture:
                if has("foto_url"): user.foto_url = picture
                elif has("avatar_url"): user.avatar_url = picture
            if has("nombre"): user.nombre = given or name
            elif has("nombres"): user.nombres = given or name
            if has("apellido"): user.apellido = family
            elif has("apellidos"): user.apellidos = family
            if has("rol") and payload.rol: user.rol = _coerce_role_value(payload.rol)
            if has("status"): user.status = "ACTIVO"
            if has("password"):
                pwd = getattr(user,"password",None)
                if not pwd or str(pwd).strip() in {"","GOOGLE","GOOGLE_OAUTH_ONLY"}:
                    user.password = "GOOGLE_OAUTH_ONLY"
            db.add(user); db.commit()
        else:
            role_value = _coerce_role_value(payload.rol) if has("rol") else None
            if has("rol") and role_value is None:
                raise HTTPException(status_code=422, detail="Debes seleccionar un rol válido: 'alumno' o 'entrenador'.")
            values = {
                "email": email,
                "rol": role_value if has("rol") else None,
                "fecha_registro": datetime.datetime.utcnow() if has("fecha_registro") else None,
                "password": "GOOGLE_OAUTH_ONLY" if has("password") else None,
                "google_sub": sub if has("google_sub") else None,
                "auth_provider": "google" if has("auth_provider") else None,
                "status": "ACTIVO" if has("status") else None,
            }
            if picture and (has("foto_url") or has("avatar_url")):
                values["foto_url" if has("foto_url") else "avatar_url"] = picture
            if has("nombre"): values["nombre"] = given or name
            elif has("nombres"): values["nombres"] = given or name
            if has("apellido"): values["apellido"] = family
            elif has("apellidos"): values["apellidos"] = family
            user = _insert_user_core(db, values)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicto de claves únicas (email/google_sub).")
    except HTTPException:
        db.rollback(); raise
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=500, detail="Error guardando usuario") from e

    token = make_token(user)
    resp_usuario = {
        "id": getattr(user,"id_usuario", getattr(user,"id",None)),
        "nombre":   getattr(user,"nombre",None) or getattr(user,"nombres","") or "",
        "apellido": getattr(user,"apellido",None) or getattr(user,"apellidos","") or "",
        "email": user.email,
        "rol": _role_str(user),
        "auth_provider": "google",
    }
    return {"ok": True, "token": token, "usuario": resp_usuario}

# Routers
app.include_router(auth_router)
app.include_router(usuarios_router,     tags=["Usuarios"])
app.include_router(entrenadores_router, tags=["Entrenadores"])
app.include_router(ejercicios_router,   prefix="/api/ejercicios",   tags=["Ejercicios"])
app.include_router(rutinas_router,      prefix="/api/rutinas",      tags=["Rutinas"])
app.include_router(asignaciones_router, prefix="/api/asignaciones", tags=["Asignaciones"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
