# routers/cliente_entrenador.py
"""
Router DEFINITIVO SIN AUTENTICACIÓN
Se eliminaron las dependencias de autenticación (get_current_user)
y ahora los endpoints reciben el id_cliente o id_entrenador como parámetro
para poder probarlos fácilmente desde /docs.

Tabla: usuarios
Columnas reales: estatura_cm, problemas, peso_kg, enfermedades, foto_url
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import Optional, List

# Dependencias
from utils.dependencies import get_db
from models.user import Usuario
from models.cliente_entrenador import ClienteEntrenador

router = APIRouter(prefix="/cliente-entrenador", tags=["Cliente-Entrenador"])

# ============================================================
# SCHEMAS (Pydantic)
# ============================================================

from pydantic import BaseModel


class ClienteEntrenadorCreate(BaseModel):
    id_cliente: int
    id_entrenador: int
    notas: Optional[str] = None


class ClienteOut(BaseModel):
    id_usuario: int
    nombre: str
    apellido: Optional[str] = None
    email: str
    foto_url: Optional[str] = None
    avatar_url: Optional[str] = None
    ciudad: Optional[str] = None
    edad: Optional[int] = None
    peso: Optional[float] = None
    estatura: Optional[int] = None
    imc: Optional[float] = None
    peso_kg: Optional[float] = None
    sexo: Optional[str] = None
    antecedentes: Optional[str] = None
    problemas_medicos: Optional[str] = None
    enfermedades: Optional[List[str]] = None
    condiciones_medicas: Optional[List[str]] = None
    fecha_nacimiento: Optional[str] = None
    rol: Optional[str] = None  # ← AGREGADO


    class Config:
        from_attributes = True


class EntrenadorOut(BaseModel):
    id_usuario: int
    nombre: str
    especialidad: Optional[str] = None
    rating: Optional[float] = None
    foto_url: Optional[str] = None
    email: str
    ciudad: Optional[str] = None
    rol: Optional[str] = None  # ← AGREGADO



class ClienteConRelacionOut(BaseModel):
    cliente: ClienteOut
    fecha_contratacion: str
    estado: str
    notas: Optional[str] = None


class EntrenadorConRelacionOut(BaseModel):
    entrenador: EntrenadorOut
    fecha_contratacion: str
    estado: str
    notas: Optional[str] = None


class ClienteEntrenadorOut(BaseModel):
    id_relacion: int
    id_cliente: int
    id_entrenador: int
    fecha_contratacion: str
    estado: str
    activo: bool
    notas: Optional[str] = None


# ============================================================
# HELPERS
# ============================================================

def _rol_str(u: Usuario) -> str:
    r = getattr(u, "rol", None)
    if r is None:
        return ""
    return (r.value if hasattr(r, "value") else str(r)).strip().lower()


def _nombre_completo(u: Usuario) -> str:
    n = getattr(u, "nombre", None) or getattr(u, "nombres", "") or ""
    a = getattr(u, "apellido", None) or getattr(u, "apellidos", "") or ""
    return f"{n} {a}".strip()


def _obtener_apellido(u: Usuario) -> Optional[str]:
    return getattr(u, "apellido", None) or getattr(u, "apellidos", None)


def _parse_enfermedades(valor: any) -> Optional[List[str]]:
    if not valor:
        return None

    if isinstance(valor, list):
        return [str(e).strip().strip('[]"\'') for e in valor if e]

    if isinstance(valor, str):
        valor = valor.strip().strip('[]"\'')
        if valor:
            return [e.strip() for e in valor.split(",") if e.strip()]

    return None


def _cliente_out(u: Usuario) -> ClienteOut:
    sexo_value = None
    if hasattr(u, 'sexo'):
        sexo = getattr(u, 'sexo')
        if sexo:
            sexo_value = sexo.value if hasattr(sexo, 'value') else str(sexo)

    enfermedades = getattr(u, "enfermedades", None)

    cliente_dict = {
        "id_usuario": int(u.id_usuario),
        "nombre": getattr(u, "nombre", ""),
        "apellido": _obtener_apellido(u),
        "email": u.email,
        "foto_url": getattr(u, "foto_url", None),
        "avatar_url": getattr(u, "avatar_url", None),
        "ciudad": getattr(u, "ciudad", None),
        "edad": getattr(u, "edad", None),
        "peso": float(getattr(u, "peso_kg", None)) if getattr(u, "peso_kg", None) else None,
        "estatura": getattr(u, "estatura_cm", None),
        "imc": float(getattr(u, "imc", None)) if getattr(u, "imc", None) else None,
        "peso_kg": float(getattr(u, "peso_kg", None)) if getattr(u, "peso_kg", None) else None,
        "sexo": sexo_value,
        "antecedentes": getattr(u, "problemas", None),
        "problemas_medicos": getattr(u, "problemas", None),
        "enfermedades": _parse_enfermedades(enfermedades),
        "condiciones_medicas": None,
        "fecha_nacimiento": None,
        "rol": _rol_str(u)  # ← AGREGADO
    }

    return ClienteOut(**cliente_dict)


class EntrenadorOut(BaseModel):
    id_usuario: int
    nombre: str
    especialidad: Optional[str] = None
    rating: Optional[float] = None
    foto_url: Optional[str] = None
    email: str
    ciudad: Optional[str] = None
    rol: Optional[str] = None  # ← AGREGADO



# ============================================================
# ENDPOINTS SIN AUTENTICACIÓN
# ============================================================

@router.post("/contratar", response_model=ClienteEntrenadorOut, status_code=status.HTTP_201_CREATED)
def contratar_entrenador(payload: ClienteEntrenadorCreate, db: Session = Depends(get_db)):
    """Cliente contrata un entrenador (sin autenticación)"""
    try:
        if payload.id_cliente == payload.id_entrenador:
            raise HTTPException(status_code=400, detail="No puedes contratarte a ti mismo")

        trainer = db.query(Usuario).filter(Usuario.id_usuario == payload.id_entrenador).first()
        if not trainer:
            raise HTTPException(status_code=404, detail="Entrenador no encontrado")

        existing = db.query(ClienteEntrenador).filter(
            and_(
                ClienteEntrenador.id_cliente == payload.id_cliente,
                ClienteEntrenador.id_entrenador == payload.id_entrenador,
                ClienteEntrenador.activo == True
            )
        ).first()

        if existing:
            raise HTTPException(status_code=409, detail="Ya existe relación activa")

        relacion = ClienteEntrenador(
            id_cliente=payload.id_cliente,
            id_entrenador=payload.id_entrenador,
            fecha_contratacion=datetime.utcnow(),
            estado="activo",
            activo=True,
            notas=payload.notas,
        )

        db.add(relacion)
        db.commit()
        db.refresh(relacion)

        return ClienteEntrenadorOut(
            id_relacion=relacion.id_relacion,
            id_cliente=relacion.id_cliente,
            id_entrenador=relacion.id_entrenador,
            fecha_contratacion=relacion.fecha_contratacion.isoformat(),
            estado=relacion.estado,
            activo=relacion.activo,
            notas=relacion.notas,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mis-clientes/{id_entrenador}", response_model=List[ClienteConRelacionOut])
def mis_clientes(id_entrenador: int, db: Session = Depends(get_db)):
    """Entrenador obtiene su lista de clientes (sin autenticación)"""
    try:
        relaciones = db.query(ClienteEntrenador).filter(
            and_(
                ClienteEntrenador.id_entrenador == id_entrenador,
                ClienteEntrenador.activo == True,
                ClienteEntrenador.estado == "activo"
            )
        ).all()

        resultado = []
        for relacion in relaciones:
            cliente_user = db.query(Usuario).filter(
                Usuario.id_usuario == relacion.id_cliente
            ).first()

            if cliente_user:
                cliente_out = _cliente_out(cliente_user)
                resultado.append(
                    ClienteConRelacionOut(
                        cliente=cliente_out,
                        fecha_contratacion=relacion.fecha_contratacion.isoformat(),
                        estado=relacion.estado,
                        notas=relacion.notas,
                    )
                )
        return resultado

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _entrenador_out(u: Usuario) -> EntrenadorOut:
    rol_value = _rol_str(u)

    return EntrenadorOut(
        id_usuario=int(u.id_usuario),
        nombre=_nombre_completo(u),
        especialidad=getattr(u, "especialidad", None),
        rating=float(getattr(u, "rating", None)) if getattr(u, "rating", None) else None,
        foto_url=getattr(u, "foto_url", None),
        email=u.email,
        ciudad=getattr(u, "ciudad", None),
        rol=rol_value  # ← AGREGADO
    )



@router.get("/mi-entrenador/{id_cliente}", response_model=Optional[EntrenadorConRelacionOut])
def mi_entrenador(id_cliente: int, db: Session = Depends(get_db)):
    """Cliente obtiene su entrenador (sin autenticación)"""
    try:
        relacion = db.query(ClienteEntrenador).filter(
            and_(
                ClienteEntrenador.id_cliente == id_cliente,
                ClienteEntrenador.activo == True,
                ClienteEntrenador.estado == "activo"
            )
        ).first()

        if not relacion:
            return None

        entrenador_user = db.query(Usuario).filter(
            Usuario.id_usuario == relacion.id_entrenador
        ).first()

        if not entrenador_user:
            return None

        return EntrenadorConRelacionOut(
            entrenador=_entrenador_out(entrenador_user),
            fecha_contratacion=relacion.fecha_contratacion.isoformat(),
            estado=relacion.estado,
            notas=relacion.notas,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relacion", response_model=bool)
def verificar_relacion(
    id_cliente: int = Query(...),
    id_entrenador: int = Query(...),
    db: Session = Depends(get_db)
):
    """Verifica si existe relación activa (sin autenticación)"""
    try:
        relacion = db.query(ClienteEntrenador).filter(
            and_(
                ClienteEntrenador.id_cliente == id_cliente,
                ClienteEntrenador.id_entrenador == id_entrenador,
                ClienteEntrenador.activo == True,
                ClienteEntrenador.estado == "activo"
            )
        ).first()
        return relacion is not None

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{id_relacion}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_relacion(id_relacion: int, db: Session = Depends(get_db)):
    """Cancela relación (sin autenticación)"""
    try:
        relacion = db.query(ClienteEntrenador).filter(
            ClienteEntrenador.id_relacion == id_relacion
        ).first()

        if not relacion:
            raise HTTPException(status_code=404, detail="Relación no encontrada")

        relacion.estado = "cancelado"
        relacion.activo = False
        relacion.fecha_fin = datetime.utcnow()

        db.add(relacion)
        db.commit()

        return None

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
