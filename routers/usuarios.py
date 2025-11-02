# routers/usuarios.py
from __future__ import annotations
import re, os, uuid, traceback, json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Union, Literal
from schemas.user import (
    Modalidad, TrainerOut, TrainersFacets, TrainersResponse,
    TrainerDetail, PerfilEntrenador
)

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body, Request
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict, model_validator, AliasChoices, constr
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update, select, insert, text

# Tipos del listado de entrenadores
from schemas.user import Modalidad, TrainerOut, TrainersFacets, TrainersResponse

# Dependencias
try:
    from utils.dependencies import get_db, get_current_user  # type: ignore
except Exception:
    from utils.dependencies import get_db, get_current_user  # type: ignore

from models.user import Usuario, RolEnum
from utils.security import hash_password, verify_password, create_token

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

MIN_PASSWORD_LEN = 10
SPECIALS_RE = r"[!@#$%^&*()\-\_=+\[\]{};:,.<>/?\\|`~\"']"

ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
CONTENTTYPE_TO_EXT = {"image/png": ".png","image/jpeg": ".jpg","image/jpg": ".jpg","image/webp": ".webp","image/gif": ".gif"}
MAX_AVATAR_BYTES = 4 * 1024 * 1024

UPLOADS_DIR = os.path.join(os.getcwd(), "uploads"); os.makedirs(UPLOADS_DIR, exist_ok=True)
PERFILES_DIR = Path(os.getcwd()) / "data" / "perfiles"; PERFILES_DIR.mkdir(parents=True, exist_ok=True)

def _perfil_path(user_id: int) -> Path: return PERFILES_DIR / f"{user_id}.json"

_SEXO_APP_TO_DB = {
    "masculino":"Masculino","hombre":"Masculino","m":"Masculino","male":"Masculino","h":"Masculino",
    "femenino":"Femenino","mujer":"Femenino","f":"Femenino","female":"Femenino",
    "otro":"Otro","x":"Otro","nd":"Otro","n/d":"Otro","no binario":"Otro","non-binary":"Otro",
}
_SEXO_DB_TO_APP = {"Masculino":"Masculino","Femenino":"Femenino","Otro":"Otro","HOMBRE":"Masculino","MUJER":"Femenino","OTRO":"Otro"}

def absolutize_url(request: Request, url: str | None) -> str | None:
    if not url: return None
    s = str(url)
    if s.startswith(("http://","https://","data:")): return s
    base = str(request.base_url).rstrip("/")
    return f"{base}{s if s.startswith('/') else '/'+s}"

def sexo_app_to_db(v: str | None) -> str | None:
    if v is None: return None
    key = str(v).strip().lower()
    if not key: return None
    mapped = _SEXO_APP_TO_DB.get(key)
    if not mapped:
        raise HTTPException(status_code=422, detail="sexo debe ser Masculino, Femenino u Otro")
    return mapped

def sexo_db_to_app(v: str | None) -> str | None:
    if v is None: return None
    return _SEXO_DB_TO_APP.get(str(v), None)

def normalize_for_db(raw: Optional[str]) -> Optional[str]:
    if not raw: return None
    r = raw.strip().lower()
    mapa = {"alumno":"alumno","cliente":"alumno","user":"alumno","empleado":"alumno","entrenador":"entrenador","coach":"entrenador","trainer":"entrenador"}
    return mapa.get(r)

def normalize_for_app(raw: Optional[str]) -> Optional[str]:
    if not raw: return None
    r = raw.strip().lower()
    return "cliente" if r=="alumno" else r

def db_to_app_role(db_value: Optional[RolEnum | str]) -> Optional[str]:
    if db_value is None: return None
    return normalize_for_app(db_value.value if isinstance(db_value, RolEnum) else str(db_value))

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

    def _only_modalidades(mods: list[str]) -> list[Modalidad]:
        allowed = {"Online", "Presencial"}
        return [m for m in mods if m in allowed]


# ===== Schemas =====
class RegisterBody(BaseModel):
    name: Optional[str] = Field(None, alias="name")
    nombre: Optional[str] = Field(None, alias="nombre")
    surname: Optional[str] = Field(None, alias="surname")
    apellido: Optional[str] = Field(None, alias="apellido")
    email: EmailStr
    password: constr(min_length=MIN_PASSWORD_LEN)
    userType: Optional[str] = Field(None, alias="userType")
    rol: Optional[str] = Field(None, alias="rol")

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if any(ch.isspace() for ch in v): raise ValueError("La contraseña no puede contener espacios.")
        if not re.search(r"[A-Z]", v):    raise ValueError("Debe incluir al menos una letra MAYÚSCULA.")
        if not re.search(r"[a-z]", v):    raise ValueError("Debe incluir al menos una letra minúscula.")
        if not re.search(r"\d", v):       raise ValueError("Debe incluir al menos un número.")
        if not re.search(SPECIALS_RE, v): raise ValueError("Debe incluir al menos un carácter especial.")
        return v

    @model_validator(mode="after")
    def password_not_contain_personal_data(self):
        pw = self.password or ""
        email_user = (self.email or "").split("@")[0].lower() if self.email else ""
        nombres = (self.name or self.nombre or "").strip().lower()
        apellidos = (self.surname or self.apellido or "").strip().lower()
        lowers = pw.lower()
        for piece in (email_user, nombres, apellidos):
            if piece and len(piece) >= 3 and piece in lowers:
                raise ValueError("La contraseña no debe contener tu nombre, apellido o usuario del email.")
        return self

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
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    sexo: Optional[str] = None
    edad: Optional[int] = None
    peso_kg: Optional[float] = Field(default=None, validation_alias=AliasChoices("peso_kg", "pesoKg"), serialization_alias="peso_kg")
    estatura_cm: Optional[float] = Field(default=None, validation_alias=AliasChoices("estatura_cm", "estaturaCm"), serialization_alias="estatura_cm")
    problemas: Optional[str] = None
    enfermedades: Optional[Union[List[str], str]] = None
    model_config = ConfigDict(populate_by_name=True, extra="ignore")



    @field_validator("edad")
    @classmethod
    def edad_rango(cls, v):
        if v is None:
            return v
        if v < 5 or v > 120:
            raise ValueError("edad debe estar entre 5 y 120")
        return v

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

# ====== Esquemas Perfil Entrenador ======
class ItemEdu(BaseModel):
    titulo: str | None = None
    institucion: str | None = None
    inicio: str | None = None
    fin: str | None = None
    descripcion: str | None = None
    evidenciaUrl: str | None = None

class ItemDip(BaseModel):
    titulo: str | None = None
    institucion: str | None = None
    fecha: str | None = None
    evidenciaUrl: str | None = None

class ItemCur(BaseModel):
    titulo: str | None = None
    institucion: str | None = None
    fecha: str | None = None
    evidenciaUrl: str | None = None

class ItemLog(BaseModel):
    titulo: str | None = None
    anio: str | None = None
    descripcion: str | None = None
    evidenciaUrl: str | None = None

class PerfilEntrenador(BaseModel):
    resumen: Optional[str] = ""
    educacion: list[ItemEdu] = Field(default_factory=list)
    diplomas: list[ItemDip]  = Field(default_factory=list)
    cursos: list[ItemCur]    = Field(default_factory=list)
    logros: list[ItemLog]    = Field(default_factory=list)

class TrainerDetail(TrainerOut):
    email: EmailStr | None = None
    telefono: str | None = None
    perfil: PerfilEntrenador | None = None


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

    model_cols = set(Usuario.__table__.columns.keys())
    first_col = "nombre"   if "nombre"   in model_cols else ("nombres"   if "nombres"   in model_cols else None)
    last_col  = "apellido" if "apellido" in model_cols else ("apellidos" if "apellidos" in model_cols else None)
    if not first_col or not last_col:
        raise HTTPException(status_code=500, detail="El modelo Usuario no define columnas de nombre/apellido")

    if rol_db not in ("alumno", "entrenador"):
        raise HTTPException(status_code=422, detail="rol inválido (usa alumno o entrenador)")

    try:
        values = {
            first_col: first,
            last_col:  last,
            "email":   email,
            "password": hash_password(password),
            "rol":      rol_db,
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

@router.post("",  response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
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
    nombre: str | None = None
    nombres: str | None = None
    apellido: str | None = None
    apellidos: str | None = None
    email: EmailStr
    password: constr(min_length=MIN_PASSWORD_LEN)
    rol: str

    @field_validator("password")
    @classmethod
    def strong_password_uc(cls, v: str) -> str:
        if any(ch.isspace() for ch in v):
            raise ValueError("La contraseña no puede contener espacios.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Debe incluir al menos una letra MAYÚSCULA.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Debe incluir al menos una letra minúscula.")
        if not re.search(r"\d", v):
            raise ValueError("Debe incluir al menos un número.")
        if not re.search(SPECIALS_RE, v):
            raise ValueError("Debe incluir al menos un carácter especial.")
        return v

    @model_validator(mode="after")
    def password_not_contain_personal_data_uc(self):
        pw = self.password or ""
        email_user = (self.email or "").split("@")[0].lower() if self.email else ""
        nombres = (self.nombres or self.nombre or "").strip().lower()
        apellidos = (self.apellidos or self.apellido or "").strip().lower()
        lowers = pw.lower()
        for piece in (email_user, nombres, apellidos):
            if piece and len(piece) >= 3 and piece in lowers:
                raise ValueError("La contraseña no debe contener tu nombre, apellido o usuario del email.")
        return self

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    first = (payload.nombres or payload.nombre or "").strip()
    last  = (payload.apellidos or payload.apellido or "").strip()
    if not first or not last:
        raise HTTPException(status_code=422, detail="Faltan nombres/apellidos")

    if db.query(Usuario).filter(Usuario.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email ya registrado")

    candidate = (payload.rol or "").strip().lower()
    alias = {"cliente": "alumno", "user": "alumno", "empleado": "alumno", "coach": "entrenador", "trainer": "entrenador"}
    role_db = alias.get(candidate, candidate)
    if role_db not in ("alumno", "entrenador"):
        raise HTTPException(status_code=422, detail="rol inválido (usa alumno o entrenador)")

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
            "auth_provider": "local" if "auth_provider" in model_cols else None,
            "status": "ACTIVO" if "status" in model_cols else None,
        }
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

# ====================== LOGIN ======================
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
        if not ok and user.password == password:
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
            "sub": str(user.id_usuario),
            "rol": user.rol.value if isinstance(user.rol, RolEnum) else str(user.rol)
        })

        return LoginResponse(ok=True, mensaje="Login exitoso", token=token, usuario=usuario)
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno en login")

@router.get("/me", response_model=PerfilOut)
def obtener_mi_perfil(
    request: Request,
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=500, detail="DB no inicializada (get_db devolvió None)")

    u = db.query(Usuario).filter(Usuario.id_usuario == current.id_usuario).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Lee sexo crudo
    sexo_raw = None
    try:
        row = db.execute(
            text("SELECT sexo FROM usuarios WHERE id_usuario = :uid"),
            {"uid": int(u.id_usuario)}
        ).first()
        if row:
            sexo_raw = row[0]
    except Exception:
        sexo_raw = None

    # enfermedades -> lista segura
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
        try:
            updated_at_str = u.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            updated_at_str = str(u.updated_at)

    # Foto absoluta
    raw_foto = getattr(u, "foto_url", None) or getattr(u, "avatar_url", None)
    foto_abs = absolutize_url(request, raw_foto)

    return PerfilOut(
        id=u.id_usuario,
        nombre=getattr(u, "nombre", None) or getattr(u, "nombres", "") or "",
        apellido=getattr(u, "apellido", None) or getattr(u, "apellidos", "") or "",
        nombre_completo=f"{getattr(u, 'nombre', '') or getattr(u, 'nombres', '')} {getattr(u, 'apellido', '') or getattr(u, 'apellidos', '')}".strip(),
        email=u.email,
        rol=(u.rol.value if hasattr(u.rol, "value") else str(u.rol)).lower() if getattr(u, "rol", None) else None,
        sexo=sexo_db_to_app(sexo_raw),
        edad=getattr(u, "edad", None),
        peso_kg=float(u.peso_kg) if getattr(u, "peso_kg", None) is not None else None,
        estatura_cm=float(u.estatura_cm) if getattr(u, "estatura_cm", None) is not None else None,
        imc=getattr(u, "imc", None),
        problemas=getattr(u, "problemas", None),
        enfermedades=enfs,
        foto_url=foto_abs,
        updated_at=updated_at_str
    )

# ====================== PERFIL (Usuario) ======================
@router.patch("/perfil", response_model=PerfilOut)
def actualizar_perfil(
    request: Request,
    body: dict = Body(...),
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    uid = int(current.id_usuario)

    def pick(*keys):
        for k in keys:
            if k in body and body[k] is not None:
                return body[k]
        return None

    values: dict = {}

    # Campos simples
    for key in ("nombre", "apellido", "problemas"):
        v = pick(key)
        if v is not None:
            values[key] = v.strip() if isinstance(v, str) else v

    # edad
    v_edad = pick("edad", "age")
    if v_edad is not None:
        if isinstance(v_edad, str):
            v_edad = v_edad.strip()
            if v_edad == "":
                values["edad"] = None
            else:
                try:
                    e = int(v_edad)
                except ValueError:
                    raise HTTPException(status_code=422, detail="edad debe ser un entero")
                if e < 5 or e > 120:
                    raise HTTPException(status_code=422, detail="edad debe estar entre 5 y 120")
                values["edad"] = e
        else:
            try:
                e = int(v_edad)
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="edad debe ser un entero")
            if e < 5 or e > 120:
                raise HTTPException(status_code=422, detail="edad debe estar entre 5 y 120")
            values["edad"] = e

    # sexo
    raw_sex = pick("sexo")
    if raw_sex is not None:
        s_norm = sexo_app_to_db(raw_sex)
        values["sexo"] = s_norm

    # Númericos
    v_peso = pick("peso_kg", "pesoKg")
    if v_peso is not None:
        try:
            values["peso_kg"] = float(v_peso)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="peso_kg debe ser numérico")

    v_est = pick("estatura_cm", "estaturaCm")
    if v_est is not None:
        try:
            values["estatura_cm"] = float(v_est)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="estatura_cm debe ser numérico")

    # Enfermedades
    enfs = pick("enfermedades")
    if enfs is not None:
        if isinstance(enfs, list):
            clean = [str(x).strip() for x in enfs if str(x).strip()]
            values["enfermedades"] = json.dumps(clean, ensure_ascii=False)
        else:
            values["enfermedades"] = str(enfs).strip()

    values["updated_at"] = datetime.utcnow()
    to_update = {k: v for k, v in values.items() if (v is not None or k == "sexo")}
    if not to_update:
        return obtener_mi_perfil(request=request, current=current, db=db)

    stmt = update(Usuario).where(Usuario.id_usuario == uid).values(**to_update)
    db.execute(stmt)
    db.commit()

    # Devuelve el perfil con foto absoluta
    u = db.query(Usuario).filter(Usuario.id_usuario == uid).first()
    return obtener_mi_perfil(request=request, current=u, db=db)

# ====================== AVATAR ======================
def _save_avatar_and_update_user(
    request: Request,
    upload: UploadFile,
    user: Usuario,
    db: Session
) -> dict:
    content_type = (upload.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")

    data = upload.file.read()
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="La imagen supera 4 MB")

    _, ext = os.path.splitext(upload.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        ext = CONTENTTYPE_TO_EXT.get(content_type, ".jpg")
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(status_code=400, detail="Formato de imagen no permitido")

    old_url = getattr(user, "foto_url", None)
    if old_url and old_url.startswith("/uploads/"):
        try:
            old_path = os.path.join(UPLOADS_DIR, os.path.basename(old_url))
            if os.path.isfile(old_path):
                os.remove(old_path)
        except Exception:
            pass

    filename = f"{uuid.uuid4().hex}{ext}"
    path_abs = os.path.join(UPLOADS_DIR, filename)
    with open(path_abs, "wb") as f:
        f.write(data)

    rel_url = f"/uploads/{filename}"
    user.foto_url = rel_url
    if hasattr(user, "updated_at"):
        try:
            user.updated_at = datetime.utcnow()
        except Exception:
            pass
    db.add(user)
    db.commit()
    db.refresh(user)

    base_url = str(request.base_url).rstrip("/")
    public_url = f"{base_url}{rel_url}"
    return {"foto_url": public_url}

@router.post("/perfil/avatar")
def subir_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if db is None:
        raise HTTPException(status_code=500, detail="DB no inicializada (get_db devolvió None)")
    return _save_avatar_and_update_user(request, avatar, current, db)

@router.post("/avatar")
def subir_avatar_compat(
    request: Request,
    file: UploadFile = File(...),
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if db is None:
        raise HTTPException(status_code=500, detail="DB no inicializada (get_db devolvió None)")
    return _save_avatar_and_update_user(request, file, current, db)

@router.delete("/perfil/avatar", status_code=204)
def borrar_avatar(
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if db is None:
        raise HTTPException(status_code=500, detail="DB no inicializada (get_db devolvió None)")

    u: Usuario = current
    old_url = getattr(u, "foto_url", None)
    if old_url and old_url.startswith("/uploads/"):
        try:
            old_path = os.path.join(UPLOADS_DIR, os.path.basename(old_url))
            if os.path.isfile(old_path):
                os.remove(old_path)
        except Exception:
            pass

    u.foto_url = None
    if hasattr(u, "updated_at"):
        try:
            u.updated_at = datetime.utcnow()
        except Exception:
            pass

    db.add(u)
    db.commit()
    return None  # 204

@router.delete("/avatar", status_code=204)
def borrar_avatar_compat_delete(
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return borrar_avatar(current=current, db=db)

# ====== Perfil de Entrenador (/usuarios/entrenador/*) ======
@router.get("/entrenador/perfil", response_model=PerfilEntrenador)
def get_perfil_entrenador(current: Usuario = Depends(get_current_user)):
    path = _perfil_path(int(current.id_usuario))
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return PerfilEntrenador(**json.load(f))
    return PerfilEntrenador()

@router.put("/entrenador/perfil", response_model=PerfilEntrenador)
def put_perfil_entrenador(
    payload: PerfilEntrenador,
    current: Usuario = Depends(get_current_user),
):
    path = _perfil_path(int(current.id_usuario))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload.dict(), f, ensure_ascii=False, indent=2)
    return payload

@router.post("/entrenador/evidencia")
def subir_evidencia_entrenador(
    request: Request,
    file: UploadFile = File(...),
    current: Usuario = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename or "")[1].lower() or ".pdf"
    fname = f"evid_{current.id_usuario}_{uuid.uuid4().hex}{ext}"
    fpath = os.path.join(UPLOADS_DIR, fname)
    with open(fpath, "wb") as out:
        out.write(file.file.read())
    rel_url = f"/uploads/{fname}"
    return {"url": absolutize_url(request, rel_url)}


# ====================== LISTADO PÚBLICO DE ENTRENADORES ======================
entrenadores_router = APIRouter(prefix="/entrenadores", tags=["entrenadores"])

def _as_list(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    s = str(raw).strip()
    if not s:
        return []
    try:
        if s.startswith("[") or s.startswith("{"):
            val = json.loads(s)
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in s.split(",") if x.strip()]

def _nombre_completo(u: Usuario) -> str:
    n = getattr(u, "nombre", None) or getattr(u, "nombres", "") or ""
    a = getattr(u, "apellido", None) or getattr(u, "apellidos", "") or ""
    return f"{n} {a}".strip()

def _rol_str(u: Usuario) -> str:
    r = getattr(u, "rol", None)
    if r is None:
        return ""
    return (r.value if hasattr(r, "value") else str(r)).strip().lower()

def _only_modalidades(mods: list[str] | None) -> list[Modalidad]:
    if not mods:
        return []
    allowed = {"Online", "Presencial"}
    return [m for m in mods if isinstance(m, str) and m in allowed]

@entrenadores_router.get("", response_model=TrainersResponse)
def listar_entrenadores(
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = None,
    especialidad: str | None = None,
    modalidad: Modalidad | None = None,
    ratingMin: float | None = None,
    precioMax: int | None = None,
    ciudad: str | None = None,
    sort: Literal["relevance", "rating", "experience", "price_asc", "price_desc"] = "relevance",
    page: int = 1,
    pageSize: int = 12,
):
    if db is None:
        raise HTTPException(status_code=500, detail="DB no inicializada")

    usuarios: list[Usuario] = db.query(Usuario).all()
    trainers: list[TrainerOut] = []

    for u in usuarios:
        if _rol_str(u) != "entrenador":
            continue

        _esp   = getattr(u, "especialidad", "") or ""
        _mods  = _only_modalidades(_as_list(getattr(u, "modalidades", None)))
        _tags  = _as_list(getattr(u, "etiquetas", None))
        _city  = getattr(u, "ciudad", "") or ""
        _pais  = getattr(u, "pais", None)
        _price = int(getattr(u, "precio_mensual", 0) or getattr(u, "precio", 0) or 0)
        _rate  = float(getattr(u, "rating", 0) or 0)
        _exp   = int(getattr(u, "experiencia", 0) or 0)
        _wa    = getattr(u, "whatsapp", None)

        raw_foto = getattr(u, "foto_url", None) or getattr(u, "avatar_url", None)
        foto_abs = absolutize_url(request, raw_foto)

        bio_text = None
        try:
            path = _perfil_path(int(u.id_usuario))
            if path.exists():
                with path.open("r", encoding="utf-8") as f:
                    prof = json.load(f)
                    bio_text = prof.get("resumen") or None
        except Exception:
            bio_text = None

        trainers.append(TrainerOut(
            id=int(u.id_usuario),
            nombre=_nombre_completo(u) or (getattr(u, "nombre", "") or ""),
            especialidad=_esp,
            rating=_rate,
            precio_mensual=_price,
            ciudad=_city,
            pais=_pais,
            experiencia=_exp,
            modalidades=_mods,
            etiquetas=_tags,
            foto_url=foto_abs,
            whatsapp=_wa,
            bio=bio_text,
        ))

    # 2) Filtros en memoria
    q_low = (q or "").strip().lower()
    def passes(t: TrainerOut) -> bool:
        if q_low:
            blob = f"{t.nombre} {t.especialidad} {t.ciudad} {' '.join(t.etiquetas)}".lower()
            if q_low not in blob:
                return False
        if especialidad and t.especialidad != especialidad:
            return False
        if ciudad and t.ciudad != ciudad:
            return False
        if modalidad and modalidad not in t.modalidades:
            return False
        if ratingMin is not None and t.rating < ratingMin:
            return False
        if precioMax is not None and t.precio_mensual > precioMax:
            return False
        return True

    filtered = [t for t in trainers if passes(t)]

    # 3) Orden
    if sort == "rating":
        filtered.sort(key=lambda x: x.rating, reverse=True)
    elif sort == "experience":
        filtered.sort(key=lambda x: x.experiencia, reverse=True)
    elif sort == "price_asc":
        filtered.sort(key=lambda x: x.precio_mensual)
    elif sort == "price_desc":
        filtered.sort(key=lambda x: x.precio_mensual, reverse=True)
    else:
        filtered.sort(key=lambda x: (x.rating * x.experiencia) / (x.precio_mensual + 1), reverse=True)

    # 4) Facets
    especialidades = sorted({t.especialidad for t in trainers if t.especialidad})
    ciudades      = sorted({t.ciudad for t in trainers if t.ciudad})
    mods_set      = set()
    for t in trainers:
        mods_set.update(t.modalidades or [])
    precio_min = min((t.precio_mensual for t in trainers), default=None)
    precio_max = max((t.precio_mensual for t in trainers), default=None)
    rating_max = max((t.rating for t in trainers), default=None)

    facets = TrainersFacets(
        especialidades=especialidades,
        ciudades=ciudades,
        modalidades=sorted(list(mods_set)),
        precioMin=precio_min,
        precioMax=precio_max,
        ratingMax=rating_max,
    )

    # 5) Paginación
    total = len(filtered)
    page     = max(1, page)
    pageSize = max(1, min(pageSize, 50))
    start = (page - 1) * pageSize
    end   = start + pageSize
    items = filtered[start:end]

    return TrainersResponse(items=items, total=total, page=page, pageSize=pageSize, facets=facets)

# ---- DETALLE (plano, no anidado) ----
@entrenadores_router.get("/{trainer_id}", response_model=TrainerDetail)
def detalle_entrenador(
    trainer_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=500, detail="DB no inicializada")

    u: Usuario | None = db.query(Usuario).filter(Usuario.id_usuario == trainer_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Entrenador no encontrado (id inválido)")
    if _rol_str(u) != "entrenador":
        raise HTTPException(status_code=404, detail="Entrenador no encontrado (rol ≠ entrenador)")

    _esp   = getattr(u, "especialidad", "") or ""
    _mods  = _only_modalidades(_as_list(getattr(u, "modalidades", None)))
    _tags  = _as_list(getattr(u, "etiquetas", None))
    _city  = getattr(u, "ciudad", "") or ""
    _pais  = getattr(u, "pais", None)
    _price = int(getattr(u, "precio_mensual", 0) or getattr(u, "precio", 0) or 0)
    _rate  = float(getattr(u, "rating", 0) or 0)
    _exp   = int(getattr(u, "experiencia", 0) or 0)
    _wa    = getattr(u, "whatsapp", None)
    _tel   = getattr(u, "telefono", None)

    raw_foto = getattr(u, "foto_url", None) or getattr(u, "avatar_url", None)
    foto_abs = absolutize_url(request, raw_foto)

    perfil_json: PerfilEntrenador | None = None
    bio_text = None
    try:
        path = _perfil_path(int(u.id_usuario))
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                perfil_json = PerfilEntrenador(**json.load(f))
                bio_text = perfil_json.resumen or None
    except Exception:
        perfil_json = None
        bio_text = None

    return TrainerDetail(
        id=int(u.id_usuario),
        nombre=_nombre_completo(u) or (getattr(u, "nombre", "") or ""),
        especialidad=_esp,
        rating=_rate,
        precio_mensual=_price,
        ciudad=_city,
        pais=_pais,
        experiencia=_exp,
        modalidades=_mods,
        etiquetas=_tags,
        foto_url=foto_abs,
        whatsapp=_wa,
        bio=bio_text,
        email=getattr(u, "email", None),
        telefono=_tel,
        perfil=perfil_json,
    )
