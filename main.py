# main.py
from fastapi import FastAPI, HTTPException, Depends, APIRouter
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Header

from google.oauth2 import id_token
from google.auth.transport.requests import Request

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import insert, select  # <-- Core

from config.database import get_db
from models import Usuario

import os, datetime, jwt

from routers import (
    usuarios_router,
    ejercicios_router,
    rutinas_router,
    asignaciones_router,
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "*"],
)

CLIENT_ID    = "144363202163-juhhgsrj47dp46co5bevehtmrpo54h9n.apps.googleusercontent.com"
JWT_SECRET   = os.getenv("JWT_SECRET", "cambia-esto-en-produccion")
JWT_ALG      = "HS256"
JWT_EXP_DAYS = 7

# --- roles válidos que el usuario puede elegir (desde el front)
VALID_ROLES = {"alumno", "entrenador"}

auth_router = APIRouter(prefix="/auth", tags=["Auth"])

class GoogleCred(BaseModel):
    credential: str
    rol: str | None = None  # "alumno" | "entrenador"


# --- util: rol como string (soporta Enum y str) ---
def _role_str(obj) -> str:
    r = getattr(obj, "rol", obj)
    if hasattr(r, "value"):  # Enum
        r = r.value
    return (str(r) if r is not None else "alumno").lower()


def make_token(user: Usuario) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": str(getattr(user, "id_usuario", getattr(user, "id", ""))),
        "email": getattr(user, "email", ""),
        "rol": _role_str(user),
        "provider": getattr(user, "auth_provider", None) or "google",
        "iat": now,
        "exp": now + datetime.timedelta(days=JWT_EXP_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


# ---- helper: insert Core sin 'imc' ni columnas computadas ----
def _insert_user_core(db: Session, values: dict) -> Usuario:
    cols = list(Usuario.__table__.columns)
    model_cols = {c.name for c in cols}
    computed_cols = {c.name for c in cols if getattr(c, "computed", None) is not None}

    forbidden = {"imc"} | computed_cols  # nunca tocar generadas
    clean = {k: v for k, v in values.items() if k in model_cols and v is not None and k not in forbidden}

    if not clean:
        raise HTTPException(status_code=500, detail="No hay columnas válidas para insertar")

    print("[auth] CORE INSERT keys:", list(clean.keys()))
    res = db.execute(insert(Usuario.__table__).values(**clean))
    db.commit()

    new_id = getattr(res, "lastrowid", None) or getattr(res, "inserted_primary_key", [None])[0]
    return db.execute(select(Usuario).where(Usuario.id_usuario == new_id)).scalar_one()


# ---------- utilidades de login ----------
class LoginCred(BaseModel):
    email: str
    password: str

def _check_password(stored: str | None, plain: str) -> bool:
    """Comparación simple (texto plano). No usa bcrypt."""
    return bool(stored) and str(stored) == plain

def _normalize_rol_input(raw: str | None) -> str | None:
    if not raw:
        return None
    r = raw.strip().lower()
    if r in {"cliente", "user", "empleado"}:
        return "alumno"
    if r in {"coach", "trainer"}:
        return "entrenador"
    return r

def _coerce_role_value(raw: str | None):
    """
    Convierte el rol del payload al tipo que espera la columna:
    - SAEnum(enum_class=Python Enum)  -> miembro Enum
    - SAEnum(enums=[...])             -> string permitido
    - Sin enum                        -> string normal validado
    """
    norm = _normalize_rol_input(raw)
    col = Usuario.__table__.columns.get("rol")
    if col is None:
        return None

    t = getattr(col, "type", None)
    enum_cls = getattr(t, "enum_class", None)
    if enum_cls is not None:
        if norm is None:
            raise HTTPException(status_code=422, detail="Debes seleccionar un rol.")
        for member in enum_cls:
            if str(member.value).lower() == norm or member.name.lower() == norm:
                return member
        raise HTTPException(status_code=422, detail="Rol inválido. Usa 'alumno' o 'entrenador'.")

    enums = getattr(t, "enums", None)
    if enums:
        if norm is None:
            raise HTTPException(status_code=422, detail="Debes seleccionar un rol.")
        if norm in enums:
            return norm
        for e in enums:
            if e.lower() == norm:
                return e
        raise HTTPException(status_code=422, detail=f"Rol inválido. Permitidos: {', '.join(enums)}.")

    if norm not in VALID_ROLES:
        raise HTTPException(status_code=422, detail="Rol inválido. Usa 'alumno' o 'entrenador'.")
    return norm

# ---------- SOLO-BLOQUEO SI NO HAY PASSWORD REAL ----------
def _is_google_only(user: Usuario) -> bool:
    """
    True si la cuenta debe iniciar sólo con Google (no tiene contraseña real).
    Si ya tiene contraseña real (no placeholder), permitimos login local.
    """
    pwd = (getattr(user, "password", "") or "").strip()
    has_real_password = bool(pwd) and pwd.upper() not in {"GOOGLE", "GOOGLE_OAUTH_ONLY"}
    if has_real_password:
        return False  # permitir login local

    provider = getattr(user, "auth_provider", None)
    has_sub = False
    try:
        has_sub = bool(getattr(user, "google_sub"))
    except Exception:
        pass
    is_placeholder = pwd.upper() in {"GOOGLE", "GOOGLE_OAUTH_ONLY"}

    return (provider == "google") or has_sub or is_placeholder

def _password_login_logic(payload: LoginCred, db: Session) -> dict:
    email = payload.email.strip().lower()
    user = db.query(Usuario).filter(Usuario.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    # bloquear password-login solo si es "Google-only" (sin password real)
    if _is_google_only(user):
        raise HTTPException(
            status_code=400,
            detail="Esta cuenta está vinculada a Google. Usa el botón 'Continuar con Google'."
        )

    if not _check_password(getattr(user, "password", None), payload.password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

    token = make_token(user)
    resp_usuario = {
        "id": getattr(user, "id_usuario", getattr(user, "id", None)),
        "nombre":   getattr(user, "nombre", None) or getattr(user, "nombres", "") or "",
        "apellido": getattr(user, "apellido", None) or getattr(user, "apellidos", "") or "",
        "email": user.email,
        "rol": _role_str(user),
    }
    return {"ok": True, "token": token, "usuario": resp_usuario}

def _current_user(db: Session = Depends(get_db), Authorization: str | None = Header(None)) -> Usuario:
    if not Authorization or not Authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Falta header Authorization Bearer")
    token = Authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")
    user_id = payload.get("sub")
    try:
        user_id = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido (sub)")
    user = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user

def _to_float(x):
    try:
        return float(x) if x is not None else None
    except Exception:
        return None


@auth_router.post("/login")
def auth_login(payload: LoginCred, db: Session = Depends(get_db)):
    return _password_login_logic(payload, db)

@usuarios_router.post("/login")  # compat con tu front actual
def legacy_login(payload: LoginCred, db: Session = Depends(get_db)):
    return _password_login_logic(payload, db)


# ---------- Google Sign-In ----------
@auth_router.post("/google_signin")
def google_signin(payload: GoogleCred, db: Session = Depends(get_db)):
    try:
        info = id_token.verify_oauth2_token(payload.credential, Request(), CLIENT_ID)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    sub     = info.get("sub")
    email   = info.get("email")
    if not email:
        raise HTTPException(status_code=422, detail="Google no devolvió email")

    given   = (info.get("given_name") or "").strip()
    family  = (info.get("family_name") or "").strip()
    name    = (info.get("name") or "").strip()
    picture = info.get("picture")

    if not given and name:
        parts = name.split()
        given  = parts[0]
        family = " ".join(parts[1:]) if len(parts) > 1 else ""

    cols = set(Usuario.__table__.columns.keys())
    has  = lambda c: c in cols

    # Buscar usuario por sub (si existe la col) o por email
    user = db.query(Usuario).filter(Usuario.google_sub == sub).first() if has("google_sub") and sub else None
    if not user:
        user = db.query(Usuario).filter(Usuario.email == email).first()

    try:
        if user:
            print("[auth] UPDATE existing user (ORM) id:", getattr(user, "id_usuario", None))

            if has("google_sub") and sub:
                user.google_sub = sub
            if has("auth_provider"):
                user.auth_provider = "google"

            # Preferir foto_url; si no existe, usar avatar_url
            if picture:
                if has("foto_url"):
                    user.foto_url = picture
                elif has("avatar_url"):
                    user.avatar_url = picture

            if has("nombre"):
                user.nombre = given or name
            elif has("nombres"):
                user.nombres = given or name

            if has("apellido"):
                user.apellido = family
            elif has("apellidos"):
                user.apellidos = family

            if has("rol") and payload.rol:
                user.rol = _coerce_role_value(payload.rol)

            if has("status"):
                user.status = "ACTIVO"

            # IMPORTANT: NO sobrescribir si ya tiene contraseña real.
            # Solo ponemos placeholder si está vacío (para cumplir NOT NULL).
            if has("password") and not getattr(user, "password", None):
                user.password = "GOOGLE"

            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # --- REGISTRO NUEVO: exigir rol ---
            role_value = None
            if has("rol"):
                if payload.rol is None:
                    raise HTTPException(status_code=422, detail="Debes seleccionar un rol válido: 'alumno' o 'entrenador'.")
                role_value = _coerce_role_value(payload.rol)

            values = {
                "email": email,
                "rol": role_value if has("rol") else None,
                "fecha_registro": datetime.datetime.utcnow() if has("fecha_registro") else None,
                "password": ("GOOGLE" if has("password") else None),  # placeholder corto para Google-only
                "google_sub": sub if has("google_sub") else None,
                "auth_provider": "google" if has("auth_provider") else None,
                "status": "ACTIVO" if has("status") else None,
            }

            if picture and (has("foto_url") or has("avatar_url")):
                values["foto_url" if has("foto_url") else "avatar_url"] = picture

            if has("nombre"):
                values["nombre"] = given or name
            elif has("nombres"):
                values["nombres"] = given or name

            if has("apellido"):
                values["apellido"] = family
            elif has("apellidos"):
                values["apellidos"] = family

            print("[auth] CREATE new user via CORE")
            user = _insert_user_core(db, values)

    except IntegrityError as ie:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicto de claves únicas (email/google_sub).") from ie
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print("[google_signin][ERROR]", repr(e))
        raise HTTPException(status_code=500, detail="Error guardando usuario") from e

    token = make_token(user)
    resp_usuario = {
        "id": getattr(user, "id_usuario", getattr(user, "id", None)),
        "nombre":   getattr(user, "nombre", None) or getattr(user, "nombres", "") or "",
        "apellido": getattr(user, "apellido", None) or getattr(user, "apellidos", "") or "",
        "email": user.email,
        "rol": _role_str(user),
    }
    return {"ok": True, "token": token, "usuario": resp_usuario}

@usuarios_router.get("/me", tags=["Usuarios"])
def usuarios_me(u: Usuario = Depends(_current_user)):
    """Devuelve el perfil completo del usuario autenticado."""
    resp = {
        "id": getattr(u, "id_usuario", getattr(u, "id", None)),
        "nombre":   getattr(u, "nombre", None) or getattr(u, "nombres", "") or "",
        "apellido": getattr(u, "apellido", None) or getattr(u, "apellidos", "") or "",
        "email": u.email,
        "rol": _role_str(u),
        "foto_url": getattr(u, "foto_url", None) or getattr(u, "avatar_url", None),
        "sexo": getattr(u, "sexo", None),
        "edad": getattr(u, "edad", None),
        "peso_kg": _to_float(getattr(u, "peso_kg", None)),
        "estatura_cm": _to_float(getattr(u, "estatura_cm", None)),
        "imc": _to_float(getattr(u, "imc", None)),  # columna generada
        "problemas": getattr(u, "problemas", None),
        "enfermedades": getattr(u, "enfermedades", None),
        "perfil_historial": getattr(u, "perfil_historial", None),
        "updated_at": getattr(u, "updated_at", None),
        "fecha_registro": getattr(u, "fecha_registro", None),
    }
    return {"ok": True, "usuario": resp}


# Routers
app.include_router(auth_router)
app.include_router(usuarios_router, tags=["Usuarios"])
app.include_router(ejercicios_router,  prefix="/api/ejercicios",    tags=["Ejercicios"])
app.include_router(rutinas_router,     prefix="/api/rutinas",       tags=["Rutinas"])
app.include_router(asignaciones_router,prefix="/api/asignaciones",  tags=["Asignaciones"])

for r in app.routes:
    try:
        print("ROUTE:", r.path, r.methods)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
