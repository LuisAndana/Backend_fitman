# routers/usuarios.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update, select, insert            # ✅ SQLAlchemy correcto
from typing import Optional, List, Union
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict, model_validator, AliasChoices, constr
from datetime import datetime
import os, uuid, traceback, json


# --- IMPORTS DE DEPENDENCIAS (evitar paquete PyPI "dependencies") ---
try:
    # si 'routers' está dentro de un paquete (padre con __init__.py) y dependencies.py está en la raíz del paquete
    from utils.dependencies import get_db, get_current_user  # type: ignore
except Exception:
    try:
        # si tu app es un paquete tipo "app"
        from app.dependencies import get_db, get_current_user  # type: ignore
    except Exception:
        # último recurso: import absoluto local, siempre y cuando el cwd sea la raíz del proyecto
        from utils.dependencies import get_db, get_current_user  # type: ignore

from models.user import Usuario, RolEnum
from utils.security import hash_password, verify_password, create_token

# OJO: el prefijo /usuarios ya se aplica en main.py -> app.include_router(usuarios_router, prefix="/usuarios", ...)
router = APIRouter(prefix="/usuarios", tags=["usuarios"])

# ====================== Helpers ======================
def normalize_for_db(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    r = raw.strip().lower()
    mapa = {
        "alumno": "alumno",
        "cliente": "alumno",   # alias app
        "user": "alumno",
        "empleado": "alumno",
        "entrenador": "entrenador",
        "coach": "entrenador",
        "trainer": "entrenador",
    }
    return mapa.get(r)  # None si no coincide

def normalize_for_app(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    r = raw.strip().lower()
    if r == "alumno":
        return "cliente"
    if r == "entrenador":
        return "entrenador"
    return r

def db_to_app_role(db_value: Optional[RolEnum | str]) -> Optional[str]:
    if db_value is None:
        return None
    if isinstance(db_value, RolEnum):
        return normalize_for_app(db_value.value)
    return normalize_for_app(str(db_value))
def _enum_values_from_db() -> set[str]:
    """Intenta leer los valores del Enum de la columna 'rol'."""
    try:
        return set(getattr(Usuario.__table__.c.rol.type, "enums", []) or [])
    except Exception:
        return set()
# ---- helper: insert Core sin 'imc' ni columnas computadas ----
def _insert_user_core(db: Session, values: dict) -> Usuario:
    # columnas reales del modelo
    cols = list(Usuario.__table__.columns)
    model_cols = {c.name for c in cols}

    # identifica columnas computadas en el modelo (si el modelo las marcó)
    computed_cols = {c.name for c in cols if getattr(c, "computed", None) is not None}

    # black-list explícita por si el modelo no marca "computed"
    forbidden = {"imc"} | computed_cols

    # limpia input: sin None, solo columnas válidas y no prohibidas
    clean = {k: v for k, v in values.items() if k in model_cols and v is not None and k not in forbidden}

    if not clean:
        raise HTTPException(status_code=500, detail="No hay columnas válidas para insertar")

    print("[auth] CORE INSERT keys:", list(clean.keys()))
    res = db.execute(insert(Usuario.__table__).values(**clean))
    db.commit()

    new_id = getattr(res, "lastrowid", None) or getattr(res, "inserted_primary_key", [None])[0]
    return db.execute(select(Usuario).where(Usuario.id_usuario == new_id)).scalar_one()


def _enum_values_from_model() -> set[str]:
    """Valores del Enum Python (RolEnum)."""
    try:
        return {e.value for e in RolEnum}
    except Exception:
        return set()

def _normalize_alias(raw: str) -> str:
    r = (raw or "").strip().lower()
    alias = {
        "cliente": "alumno",
        "user": "alumno",
        "empleado": "alumno",
        "coach": "entrenador",
        "trainer": "entrenador",
    }
    return alias.get(r, r)  # alumno|entrenador

def _resolve_role(candidate_raw: str) -> tuple[str, "RolEnum"]:
    """
    Devuelve (role_str_para_db, role_enum_para_modelo).
    Toma lo que venga, aplica alias y busca un valor que exista
    en la tabla y en RolEnum; si no coinciden, hace el cruce alumno↔cliente.
    """
    if not candidate_raw:
        raise HTTPException(status_code=422, detail="rol requerido")

    norm = _normalize_alias(candidate_raw)  # alumno|entrenador

    db_vals   = _enum_values_from_db()     # p.ej. {'cliente','entrenador'} o {'alumno','entrenador'} o vacío
    py_vals   = _enum_values_from_model()  # p.ej. {'alumno','entrenador'} o {'cliente','entrenador'} o vacío
    prefer    = norm

    # 1) Si DB expone enum y contiene 'norm', úsalo
    if db_vals and prefer in db_vals:
        db_str = prefer
    # 2) Si DB expone enum y no contiene 'norm', intenta cruce alumno↔cliente
    elif db_vals:
        swap = {"alumno": "cliente", "cliente": "alumno"}.get(prefer, prefer)
        if swap in db_vals:
            db_str = swap
        else:
            raise HTTPException(status_code=422, detail=f"rol inválido (permitidos: {', '.join(sorted(db_vals))})")
    else:
        # DB no expone enums (o no pudimos leerlos): usa normalizado
        db_str = prefer

    # Ahora construimos el RolEnum del modelo Python
    # Intento 1: con el normalizado
    try:
        py_enum = RolEnum(prefer)
    except Exception:
        # Intento 2: con el cruce alumno↔cliente
        swap = {"alumno": "cliente", "cliente": "alumno"}.get(prefer, prefer)
        try:
            py_enum = RolEnum(swap)
        except Exception:
            if py_vals:
                raise HTTPException(status_code=422, detail=f"rol no permitido por el modelo (permitidos: {', '.join(sorted(py_vals))})")
            raise HTTPException(status_code=422, detail="rol no permitido por el modelo")

    return db_str, py_enum

def _computed_column_names() -> set[str]:
    """
    Devuelve los nombres de columnas marcadas como Computed en el modelo
    y, por seguridad, añade 'imc' si existe en la tabla (por si el modelo
    no declara Computed pero MySQL sí la tiene generada).
    """
    names: set[str] = set()
    for c in Usuario.__table__.columns:
        # SQLAlchemy expone .computed en columnas 'Computed'
        if getattr(c, "computed", None) is not None:
            names.add(c.name)
    # fallback defensivo
    if "imc" in Usuario.__table__.columns.keys():
        names.add("imc")
    return names

def _unset_columns(instance: Usuario, colnames: set[str]) -> None:
    """
    Quita atributos del estado del objeto para que SQLAlchemy
    NO los incluya en el INSERT.
    """
    for name in colnames:
        if hasattr(instance, name):
            try:
                delattr(instance, name)   # marca como NEVER_SET
            except Exception:
                pass
def _computed_column_names() -> set[str]:
    """
    Devuelve columnas generadas (Computed) del modelo.
    Incluye 'imc' como fallback defensivo si existe en la tabla.
    """
    names: set[str] = set()
    for c in Usuario.__table__.columns:
        if getattr(c, "computed", None) is not None:
            names.add(c.name)
    if "imc" in Usuario.__table__.columns.keys():
        names.add("imc")
    return names

def _unset_columns(instance: Usuario, colnames: set[str]) -> None:
    """
    Elimina atributos del objeto para que SQLAlchemy NO los incluya en el INSERT.
    """
    for name in colnames:
        if hasattr(instance, name):
            try:
                delattr(instance, name)
            except Exception:
                # fallback silencioso; evita romper si la attr está gestionada por SA
                instance.__dict__.pop(name, None)

def resolve_role_for_db(candidate_raw: Optional[str], allowed_roles: Optional[set[str]]) -> str:
    """
    Devuelve un string listo para guardar en DB y que luego pueda convertirse a RolEnum.
    - Normaliza alias app ('cliente' -> 'alumno', 'coach' -> 'entrenador', etc.).
    - Si la columna Enum permite un conjunto concreto, intenta mapear al permitido.
    - Lanza 422 si no hay forma de encajarlo.
    """
    if not candidate_raw:
        raise HTTPException(status_code=422, detail="rol requerido")

    base = candidate_raw.strip().lower()
    alias = {
        "cliente": "alumno",
        "user": "alumno",
        "empleado": "alumno",
        "coach": "entrenador",
        "trainer": "entrenador",
    }
    norm = alias.get(base, base)  # alumno|entrenador|cliente -> alumno|entrenador

    if allowed_roles:
        if norm in allowed_roles:
            return norm
        # intentos cruzados comunes tabla<->app
        if norm == "alumno" and "cliente" in allowed_roles:
            return "cliente"
        if norm == "cliente" and "alumno" in allowed_roles:
            return "alumno"
        raise HTTPException(
            status_code=422,
            detail=f"rol inválido (permitidos: {', '.join(sorted(allowed_roles))})"
        )

    # Si no pudimos leer enums de la columna, asumimos que el modelo Python manda.
    return norm

# ====================== Schemas ======================
class RegisterBody(BaseModel):
    # Compat español/inglés
    name: Optional[str] = Field(None, alias="name")
    nombre: Optional[str] = Field(None, alias="nombre")
    surname: Optional[str] = Field(None, alias="surname")
    apellido: Optional[str] = Field(None, alias="apellido")
    email: EmailStr
    password: str
    userType: Optional[str] = Field(None, alias="userType")
    rol: Optional[str] = Field(None, alias="rol")

class RegisterUserOut(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: EmailStr
    rol: str

class RegisterResponse(BaseModel):
    id: int
    mensaje: str
    usuario: RegisterUserOut

class UsuarioOut(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: EmailStr
    rol: str

class LoginBody(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    ok: bool
    mensaje: str
    token: str
    usuario: UsuarioOut

class PerfilOut(BaseModel):
    id: int
    nombre: str
    apellido: str
    nombre_completo: Optional[str] = None
    email: EmailStr
    rol: str
    sexo: Optional[str] = None
    edad: Optional[int] = None
    peso_kg: Optional[float] = None
    estatura_cm: Optional[float] = None
    imc: Optional[float] = None
    problemas: Optional[str] = None
    enfermedades: Optional[List[str]] = None
    foto_url: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class UpdatePerfilBody(BaseModel):
    # Acepta snake_case **y** camelCase en la ENTRADA
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    sexo: Optional[str] = None
    edad: Optional[int] = None

    # clave: mapea pesoKg -> peso_kg y estaturaCm -> estatura_cm
    peso_kg: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("peso_kg", "pesoKg"),
        serialization_alias="peso_kg"
    )
    estatura_cm: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("estatura_cm", "estaturaCm"),
        serialization_alias="estatura_cm"
    )

    problemas: Optional[str] = None
    enfermedades: Optional[Union[List[str], str]] = None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator("sexo")
    @classmethod
    def sexo_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v2 = v.strip().capitalize()
        if not v2:
            return None
        if v2 not in ["Masculino", "Femenino", "Otro"]:
            raise ValueError("sexo debe ser Masculino, Femenino u Otro")
        return v2


# ====================== CREATE ======================
def _create_user(db: Session, payload: RegisterBody) -> RegisterResponse:
    first = (payload.name or payload.nombre or "").strip()
    last  = (payload.surname or payload.apellido or "").strip()
    email = payload.email.strip().lower()
    password = (payload.password or "").strip()
    rol_input = payload.userType or payload.rol
    rol_db = normalize_for_db(rol_input)

    if rol_db is None:
        raise HTTPException(status_code=400, detail="Rol inválido. Usa: alumno/cliente o entrenador")
    if not all([first, last, email, password]):
        raise HTTPException(status_code=400, detail="Faltan datos obligatorios")

    # Elige el campo correcto que existe en el MODELO (singular o plural)
    model_cols = set(Usuario.__table__.columns.keys())
    first_col = "nombre"   if "nombre"   in model_cols else ("nombres"   if "nombres"   in model_cols else None)
    last_col  = "apellido" if "apellido" in model_cols else ("apellidos" if "apellidos" in model_cols else None)

    if not first_col or not last_col:
        raise HTTPException(status_code=500, detail="El modelo Usuario no define columnas de nombre/apellido")

    # La tabla acepta 'entrenador' | 'alumno'
    if rol_db not in ("alumno", "entrenador"):
        raise HTTPException(status_code=422, detail="rol inválido (usa alumno o entrenador)")

    try:
        values = {
            first_col: first,
            last_col:  last,
            "email":   email,
            "password": hash_password(password),
            "rol":      rol_db,                      # string que acepta la tabla
            "fecha_registro": datetime.utcnow(),
        }
        user = _insert_user_core(db, values)

        return RegisterResponse(
            id=user.id_usuario,
            mensaje="Usuario creado con éxito",
            usuario=RegisterUserOut(
                id=user.id_usuario,
                nombre=getattr(user, first_col),
                apellido=getattr(user, last_col),
                email=user.email,
                rol=db_to_app_role(user.rol),
            ),
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El email ya está registrado")


# Acepta /usuarios y /usuarios/ (compat)
@router.post("",  response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)   # /usuarios
@router.post("/", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)   # /usuarios/
def crear_usuario_directo(payload: RegisterBody, db: Session = Depends(get_db)):
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="DB no inicializada (get_db devolvió None)")
        return _create_user(db, payload)
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno al registrar")

class UserCreate(BaseModel):
    # aceptamos ambas variantes
    nombre: str | None = None
    nombres: str | None = None
    apellido: str | None = None
    apellidos: str | None = None
    email: EmailStr
    password: constr(min_length=6)
    # el front usa 'alumno' | 'entrenador' (a veces 'cliente' en tu BD)
    rol: str

# Compat: /usuarios/register
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    first = (payload.nombres or payload.nombre or "").strip()
    last  = (payload.apellidos or payload.apellido or "").strip()
    if not first or not last:
        raise HTTPException(status_code=422, detail="Faltan nombres/apellidos")

    if db.query(Usuario).filter(Usuario.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email ya registrado")

    # Rol DB: 'alumno'|'entrenador' (mapeo de alias)
    candidate = (payload.rol or "").strip().lower()
    alias = {"cliente": "alumno", "user": "alumno", "empleado": "alumno",
             "coach": "entrenador", "trainer": "entrenador"}
    role_db = alias.get(candidate, candidate)
    if role_db not in ("alumno", "entrenador"):
        raise HTTPException(status_code=422, detail="rol inválido (usa alumno o entrenador)")

    # Campos reales del MODELO
    model_cols = set(Usuario.__table__.columns.keys())
    first_col = "nombre"   if "nombre"   in model_cols else ("nombres"   if "nombres"   in model_cols else None)
    last_col  = "apellido" if "apellido" in model_cols else ("apellidos" if "apellidos" in model_cols else None)
    if not first_col or not last_col:
        raise HTTPException(status_code=500, detail="El modelo Usuario no define columnas de nombre/apellido")

    try:
        values = {
            "email": payload.email,
            first_col: first,
            last_col:  last,
            "password": hash_password(payload.password) if "password" in model_cols else None,
            "rol": role_db if "rol" in model_cols else None,
            "fecha_registro": datetime.utcnow() if "fecha_registro" in model_cols else None,
            # Opcionales: solo si EXISTEN en el modelo
            "auth_provider": "local" if "auth_provider" in model_cols else None,
            "status": "ACTIVO" if "status" in model_cols else None,
        }
        # El helper ya filtra por columnas reales del modelo y quita None
        user = _insert_user_core(db, values)
        return {"ok": True, "id": user.id_usuario}

    except IntegrityError as ie:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email ya registrado") from ie
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print("[/usuarios/register][ERROR]", type(e).__name__, repr(e))
        raise HTTPException(status_code=500, detail="Error interno al registrar")


# ====================== LOGIN (compat dentro de /usuarios) ======================
@router.post("/login", response_model=LoginResponse)
def login_usuario(payload: LoginBody, db: Session = Depends(get_db)):
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="DB no inicializada (get_db devolvió None)")

        email = payload.email.strip().lower()
        password = payload.password.strip()
        if not email or not password:
            raise HTTPException(status_code=400, detail="Faltan credenciales")

        user: Optional[Usuario] = db.query(Usuario).filter(Usuario.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if not verify_password(password, user.password):
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")

        ok = verify_password(password, user.password)
        if not ok:
            # Fallback LEGADO: si lo guardado era texto plano y coincide, acepta y rehashea
            # (solo recomendado para migración/desarrollo)
            if user.password == password:
                # rehash y guarda
                user.password = hash_password(password)
                db.add(user)
                db.commit()
                db.refresh(user)
                ok = True

        if not ok:
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")

        usuario = UsuarioOut(
            id=user.id_usuario,
            nombre=user.nombre,
            apellido=user.apellido,
            email=user.email,
            rol=db_to_app_role(user.rol),
        )
        token = create_token({
            "sub": str(user.id_usuario),  # asegurar string
            "rol": user.rol.value if isinstance(user.rol, RolEnum) else str(user.rol)
        })

        return LoginResponse(ok=True, mensaje="Login exitoso", token=token, usuario=usuario)

    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno en login")

# ====================== PERFIL ======================
@router.get("/me", response_model=PerfilOut)
def obtener_mi_perfil(current: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=500, detail="DB no inicializada (get_db devolvió None)")
    u = db.query(Usuario).filter(Usuario.id_usuario == current.id_usuario).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # enfermedades -> lista
    enfs: Optional[List[str]] = None
    raw = getattr(u, "enfermedades", None)
    if raw:
        try:
            if isinstance(raw, list):
                enfs = [s for s in raw if isinstance(s, str) and s.strip()]
            else:
                s = str(raw).strip()
                if s.startswith("["):
                    enfs = [x for x in json.loads(s) if isinstance(x, str) and x.strip()]
                else:
                    enfs = [x.strip() for x in s.split(",") if x.strip()]
        except Exception:
            enfs = [x.strip() for x in str(raw).split(",") if x.strip()]

    updated_at_str = None
    if getattr(u, "updated_at", None):
        try:   updated_at_str = u.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        except: updated_at_str = str(u.updated_at)

    return PerfilOut(
        id=u.id_usuario,
        nombre=u.nombre,
        apellido=u.apellido,
        nombre_completo=f"{u.nombre} {u.apellido}".strip(),
        email=u.email,
        rol=db_to_app_role(u.rol),
        sexo=u.sexo,
        edad=u.edad,
        peso_kg=float(u.peso_kg) if u.peso_kg is not None else None,
        estatura_cm=float(u.estatura_cm) if u.estatura_cm is not None else None,
        imc=getattr(u, "imc", None),
        problemas=u.problemas,
        enfermedades=enfs,
        foto_url=u.foto_url,
        updated_at=updated_at_str
    )


@router.patch("/perfil", response_model=PerfilOut)
def actualizar_perfil(
    body: dict = Body(...),                      # <-- Body CRUDO, no Pydantic
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    uid = int(current.id_usuario)

    # Logs de diagnóstico
    print("PATCH /usuarios/perfil RAW BODY:", body)
    try:
        print("DB URL (router):", str(db.bind.url))
    except Exception:
        pass

    # Helper para aceptar snake_case y camelCase
    def pick(*keys):
        for k in keys:
            if k in body and body[k] is not None:
                return body[k]
        return None

    values = {}

    # Campos simples
    for key in ("nombre", "apellido", "sexo", "edad", "problemas"):
        v = pick(key)
        if v is not None:
            values[key] = v.strip() if isinstance(v, str) else v

    # Alias: camelCase o snake_case
    v_peso = pick("peso_kg", "pesoKg")
    if v_peso is not None:
        values["peso_kg"] = v_peso

    v_est = pick("estatura_cm", "estaturaCm")
    if v_est is not None:
        values["estatura_cm"] = v_est

    # Enfermedades: lista o string
    enfs = pick("enfermedades")
    if enfs is not None:
        values["enfermedades"] = json.dumps(enfs, ensure_ascii=False) if isinstance(enfs, list) else enfs

    values["updated_at"] = datetime.utcnow()

    # Nada que actualizar => devuelve perfil
    to_update = {k: v for k, v in values.items() if v is not None}
    if not to_update:
        return obtener_mi_perfil(current=current, db=db)

    # BEFORE
    before = db.execute(
        select(
            Usuario.id_usuario, Usuario.sexo, Usuario.edad, Usuario.peso_kg,
            Usuario.estatura_cm, Usuario.problemas, Usuario.enfermedades
        ).where(Usuario.id_usuario == uid)
    ).first()
    print("BEFORE row:", before)

    # UPDATE explícito (misma sesión)
    stmt = update(Usuario).where(Usuario.id_usuario == uid).values(**to_update)
    result = db.execute(stmt)
    db.commit()
    print("Rows updated:", result.rowcount, "VALUES:", to_update)

    # AFTER
    after = db.execute(
        select(
            Usuario.id_usuario, Usuario.sexo, Usuario.edad, Usuario.peso_kg,
            Usuario.estatura_cm, Usuario.problemas, Usuario.enfermedades
        ).where(Usuario.id_usuario == uid)
    ).first()
    print("AFTER row:", after)

    # Devuelve el perfil actualizado
    u = db.query(Usuario).filter(Usuario.id_usuario == uid).first()
    return obtener_mi_perfil(current=u, db=db)



@router.post("/perfil/avatar")
def subir_avatar(avatar: UploadFile = File(...), current: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=500, detail="DB no inicializada (get_db devolvió None)")

    uploads_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    ext = os.path.splitext(avatar.filename)[1].lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    path_abs = os.path.join(uploads_dir, filename)

    with open(path_abs, "wb") as f:
        f.write(avatar.file.read())

    url = f"/uploads/{filename}"  # Asegúrate de montar estáticos en main.py:
    # from fastapi.staticfiles import StaticFiles
    # app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    u: Usuario = current
    u.foto_url = url
    if hasattr(u, "updated_at"):
        try:
            u.updated_at = datetime.utcnow()
        except Exception:
            pass

    db.add(u)
    db.commit()
    db.refresh(u)

    return {"url": url}
