# main.py - VERSIÓN CORREGIDA

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, defer
from sqlalchemy.exc import IntegrityError
from sqlalchemy import insert, select

import os
import datetime
import jwt
from pathlib import Path

# ============================================================
# IMPORTS DE ROUTERS CON MANEJO DE ERRORES
# ============================================================

# Cliente-Entrenador
from routers.cliente_entrenador import router as cliente_entrenador_router

# Progresión
from routers import progresion


# IA Router - con manejo de errores
try:
    from routers.ia import router as ia_router

    IA_ROUTER_DISPONIBLE = True
    print("✅ Router IA importado correctamente")
except ImportError as e:
    print(f"⚠️ No se pudo importar router IA: {e}")
    ia_router = None
    IA_ROUTER_DISPONIBLE = False

# Otros routers
from routers import (
    usuarios_router,
    entrenadores_router,
    ejercicios_router,
    rutinas_router,
    asignaciones_router,
    resenas_router,
    mensajes_router,
    pagos_router,
    cliente_entrenador
)

# Utilidades
from utils.dependencies import get_db
from utils.passwords import verify_password, hash_password
from models.user import Usuario

# Google OAuth
from google.oauth2 import id_token
from google.auth.transport.requests import Request as GRequest

# ============================================================
# CONFIGURACIÓN
# ============================================================

app = FastAPI(
    title="FitCoach API",
    version="1.0.0",
    description="API para gestión de entrenadores y clientes"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "*",  # En desarrollo
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Carpeta de uploads
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Crear carpeta static si no existe
os.makedirs("static", exist_ok=True)

# ============================================================
# CONSTANTES
# ============================================================

CLIENT_ID = "144363202163-juhhgsrj47dp46co5bevehtmrpo54h9n.apps.googleusercontent.com"
JWT_SECRET = os.getenv("JWT_SECRET", "cambia-esto-en-produccion")
JWT_ALG = "HS256"
JWT_EXP_DAYS = 7
VALID_ROLES = {"alumno", "entrenador"}


# ============================================================
# FUNCIONES HELPER (sin cambios)
# ============================================================

def _role_str(obj) -> str:
    """Convierte el rol a string normalizado"""
    r = getattr(obj, "rol", obj)
    if hasattr(r, "value"):
        r = r.value
    return (str(r) if r is not None else "alumno").lower()


def make_token(user: Usuario) -> str:
    """Genera JWT token para el usuario"""
    now = datetime.datetime.utcnow()
    user_id = getattr(user, "id_usuario", None) or getattr(user, "id", None)
    if not user_id:
        raise HTTPException(status_code=500, detail="Usuario sin ID válido")
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
    """Inserta un usuario en la BD"""
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


def _normalize_rol_input(raw: str | None) -> str | None:
    """Normaliza input de rol"""
    if not raw:
        return None
    r = raw.strip().lower()
    if r in {"cliente", "user", "empleado"}:
        return "alumno"
    if r in {"coach", "trainer"}:
        return "entrenador"
    return r


def _coerce_role_value(raw: str | None):
    """Coerciona el rol al tipo de la columna"""
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
        if norm in enums or any(e.lower() == norm for e in enums):
            return next((e for e in enums if e.lower() == norm), norm)
        raise HTTPException(status_code=422, detail=f"Rol inválido. Permitidos: {', '.join(enums)}.")
    if norm not in VALID_ROLES:
        raise HTTPException(status_code=422, detail="Rol inválido. Usa 'alumno' o 'entrenador'.")
    return norm


def _is_google_only(user: Usuario) -> bool:
    """Verifica si el usuario solo tiene Google OAuth"""
    pwd = (getattr(user, "password", "") or "").strip()
    has_real = bool(pwd) and pwd.upper() not in {"GOOGLE", "GOOGLE_OAUTH_ONLY"}
    if has_real:
        return False
    provider = getattr(user, "auth_provider", None)
    has_sub = bool(getattr(user, "google_sub", None))
    is_placeholder = pwd.upper() in {"GOOGLE", "GOOGLE_OAUTH_ONLY"}
    return (provider == "google") or has_sub or is_placeholder


def _current_user(db: Session = Depends(get_db), Authorization: str | None = Header(None)) -> Usuario:
    """Extrae el usuario actual del token JWT"""
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
    user = db.query(Usuario).options(defer(Usuario.sexo)).filter(Usuario.id_usuario == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


# ============================================================
# SCHEMAS
# ============================================================

class LoginCred(BaseModel):
    email: str
    password: str


class GoogleCred(BaseModel):
    credential: str
    rol: str | None = None


# ============================================================
# RUTAS DE AUTENTICACIÓN
# ============================================================

from fastapi import APIRouter

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post("/login")
def auth_login(payload: LoginCred, db: Session = Depends(get_db)):
    """Login con email y contraseña"""
    return _password_login_logic(payload, db)


def _password_login_logic(payload: LoginCred, db: Session) -> dict:
    """Lógica de login con email/password"""
    email = payload.email.strip().lower()
    user = db.query(Usuario).options(defer(Usuario.sexo)).filter(Usuario.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if _is_google_only(user):
        raise HTTPException(status_code=400, detail="Esta cuenta está vinculada a Google. Usa 'Continuar con Google'.")

    db_pwd = getattr(user, "password", "") or ""
    if isinstance(db_pwd, (bytes, bytearray)):
        db_pwd = db_pwd.decode("utf-8", "ignore")
    db_pwd = db_pwd.rstrip()

    ok = verify_password(payload.password, db_pwd)
    if not ok and db_pwd and db_pwd == payload.password.strip():
        user.password = hash_password(payload.password.strip())
        db.add(user)
        db.commit()
        ok = True
    if not ok:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

    if not getattr(user, "auth_provider", None):
        try:
            user.auth_provider = "local"
            db.add(user)
            db.commit()
        except Exception:
            pass

    token = make_token(user)
    resp_usuario = {
        "id": getattr(user, "id_usuario", getattr(user, "id", None)),
        "nombre": getattr(user, "nombre", None) or getattr(user, "nombres", "") or "",
        "apellido": getattr(user, "apellido", None) or getattr(user, "apellidos", "") or "",
        "email": user.email,
        "rol": _role_str(user),
        "auth_provider": getattr(user, "auth_provider", "local"),
    }
    return {"ok": True, "token": token, "usuario": resp_usuario}


@auth_router.post("/google_signin")
def google_signin(payload: GoogleCred, db: Session = Depends(get_db)):
    """Login/Registro con Google OAuth"""
    try:
        info = id_token.verify_oauth2_token(payload.credential, GRequest(), CLIENT_ID)
    except Exception:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    sub = info.get("sub")
    email = info.get("email")
    if not email:
        raise HTTPException(status_code=422, detail="Google no devolvió email")

    given = (info.get("given_name") or "").strip()
    family = (info.get("family_name") or "").strip()
    name = (info.get("name") or "").strip()
    picture = info.get("picture")

    if not given and name:
        parts = name.split()
        given = parts[0]
        family = " ".join(parts[1:]) if len(parts) > 1 else ""

    cols = set(Usuario.__table__.columns.keys())
    has = lambda c: c in cols

    user = db.query(Usuario).options(defer(Usuario.sexo)).filter(Usuario.google_sub == sub).first() if has(
        "google_sub") and sub else None
    if not user:
        user = db.query(Usuario).options(defer(Usuario.sexo)).filter(Usuario.email == email).first()

    try:
        if user:
            if has("google_sub") and sub:
                user.google_sub = sub
            if has("auth_provider"):
                user.auth_provider = "google"
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
            if has("password"):
                pwd = getattr(user, "password", None)
                if not pwd or str(pwd).strip() in {"", "GOOGLE", "GOOGLE_OAUTH_ONLY"}:
                    user.password = "GOOGLE_OAUTH_ONLY"
            db.add(user)
            db.commit()
        else:
            role_value = _coerce_role_value(payload.rol) if has("rol") else None
            if has("rol") and role_value is None:
                raise HTTPException(status_code=422, detail="Debes seleccionar un rol válido.")
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
            if has("nombre"):
                values["nombre"] = given or name
            elif has("nombres"):
                values["nombres"] = given or name
            if has("apellido"):
                values["apellido"] = family
            elif has("apellidos"):
                values["apellidos"] = family
            user = _insert_user_core(db, values)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicto de claves únicas.")
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error guardando usuario") from e

    token = make_token(user)
    resp_usuario = {
        "id": getattr(user, "id_usuario", getattr(user, "id", None)),
        "nombre": getattr(user, "nombre", None) or getattr(user, "nombres", "") or "",
        "apellido": getattr(user, "apellido", None) or getattr(user, "apellidos", "") or "",
        "email": user.email,
        "rol": _role_str(user),
        "auth_provider": "google",
    }
    return {"ok": True, "token": token, "usuario": resp_usuario}


# ============================================================
# MANEJO DEL FAVICON
# ============================================================

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico") if Path("static/favicon.ico").exists() else {}



# ============================================================
# INCLUIR ROUTERS - ORDEN CORRECTO
# ============================================================

print("\n" + "=" * 60)
print("🚀 Registrando routers...")
print("=" * 60)

# Montar archivos estáticos
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    print(f"⚠️ No se pudo montar /static: {e}")

# 1. Auth
app.include_router(auth_router)
print("✔ Auth")

# 2. Usuarios
app.include_router(usuarios_router, tags=["Usuarios"])
print("✔ Usuarios")

# 3. Entrenadores
app.include_router(entrenadores_router, tags=["Entrenadores"])
print("✔ Entrenadores")

# 4. Ejercicios
app.include_router(ejercicios_router, prefix="/api/ejercicios", tags=["Ejercicios"])
print("✔ Ejercicios")

# 5. Rutinas
app.include_router(rutinas_router, prefix="/api/rutinas", tags=["Rutinas"])
print("✔ Rutinas")

# 6. Asignaciones
app.include_router(asignaciones_router, prefix="/api/asignaciones", tags=["Asignaciones"])
print("✔ Asignaciones")

# 7. Reseñas
app.include_router(resenas_router, tags=["Reseñas"])
print("✔ Reseñas")

# 8. Mensajes
app.include_router(mensajes_router, tags=["Mensajes"])
print("✔ Mensajes")

# 9. Pagos
app.include_router(pagos_router, tags=["Pagos"])
print("✔ Pagos")

# 10. Cliente-Entrenador
app.include_router(cliente_entrenador.router, prefix="/api")
app.include_router(cliente_entrenador_router, tags=["Cliente-Entrenador"])
print("✔ Cliente-Entrenador")

# 11. IA Router
app.include_router(ia_router, prefix="/api/ia", tags=["IA"])


# 12. Progresión
app.include_router(
    progresion.router,
    prefix="/progresion",
    tags=["Progresión"]
)
print("✔ Progresión")

print("=" * 60)
print("✔ Todos los routers registrados correctamente")
print("=" * 60 + "\n")


# ============================================================
# RUTAS BÁSICAS
# ============================================================


@app.get("/")
def read_root():
    """Ruta raíz de la API"""
    return {
        "nombre": "FitCoach API",
        "version": "1.0.0",
        "documentacion": "/docs",
        "redoc": "/redoc",
        "ia_router_disponible": IA_ROUTER_DISPONIBLE
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.get("/debug/routes")
def debug_routes():
    """Muestra todas las rutas registradas con detalles"""
    routes = []
    for route in app.routes:
        if hasattr(route, "methods"):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name,
                "endpoint": route.endpoint.__name__ if hasattr(route, "endpoint") else None
            })

    # Agrupar por prefijo
    ia_routes = [r for r in routes if "/api/ia" in r["path"]]

    return {
        "total": len(routes),
        "routes": routes,
        "ia_routes": ia_routes,
        "ia_router_status": "ACTIVE" if IA_ROUTER_DISPONIBLE else "INACTIVE"
    }


@app.get("/debug/ia-status")
def debug_ia_status():
    """Verifica el estado del router IA"""
    ia_routes = []
    for route in app.routes:
        if hasattr(route, "methods") and "/api/ia" in route.path:
            ia_routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, "name", "Unknown")
            })

    return {
        "ia_router_imported": IA_ROUTER_DISPONIBLE,
        "ia_routes_count": len(ia_routes),
        "ia_routes": ia_routes
    }


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    print("\n🚀 Iniciando servidor FitCoach API...")
    print("📝 Documentación disponible en: http://127.0.0.1:8000/docs")
    print("🔍 Debug de rutas en: http://127.0.0.1:8000/debug/routes")
    print("🤖 Estado IA en: http://127.0.0.1:8000/debug/ia-status\n")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)