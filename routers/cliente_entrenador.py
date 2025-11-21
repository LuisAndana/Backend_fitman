# routers/cliente_entrenador.py - VERSIÓN CORREGIDA DEFINITIVA
"""
✅ SOLUCIONES APLICADAS:
1. Eliminada definición duplicada de EntrenadorOut
2. Funciones helper (_entrenador_out, _cliente_out) movidas al inicio ANTES de los endpoints
3. Validación robusta en todos los endpoints
4. Manejo correcto de campos Optional
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from utils.dependencies import get_db
from models.user import Usuario
from models.cliente_entrenador import ClienteEntrenador

router = APIRouter(prefix="/cliente-entrenador", tags=["Cliente-Entrenador"])


# ============================================================
# SCHEMAS (Pydantic) - Definidos al inicio
# ============================================================


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
    rol: Optional[str] = None

    class Config:
        from_attributes = True


class EntrenadorOut(BaseModel):
    """
    ✅ ÚNICO ESQUEMA - Todos los campos Optional con defaults
    """
    id_usuario: int
    nombre: str
    especialidad: Optional[str] = None
    rating: Optional[float] = None
    foto_url: Optional[str] = None
    email: str
    ciudad: Optional[str] = None
    rol: Optional[str] = None

    class Config:
        from_attributes = True


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
# HELPER FUNCTIONS - Definidas ANTES de los endpoints
# ============================================================


def _rol_str(u: Usuario) -> str:
    """Extrae el rol como string"""
    r = getattr(u, "rol", None)
    if r is None:
        return ""
    return (r.value if hasattr(r, "value") else str(r)).strip().lower()


def _nombre_completo(u: Usuario) -> str:
    """Obtiene nombre completo del usuario"""
    n = getattr(u, "nombre", None) or getattr(u, "nombres", "") or ""
    a = getattr(u, "apellido", None) or getattr(u, "apellidos", "") or ""
    return f"{n} {a}".strip()


def _obtener_apellido(u: Usuario) -> Optional[str]:
    """Obtiene el apellido"""
    return getattr(u, "apellido", None) or getattr(u, "apellidos", None)


def _parse_enfermedades(valor: any) -> Optional[List[str]]:
    """Parsea enfermedades desde diferentes formatos"""
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
    """
    ✅ Convierte usuario a ClienteOut
    Maneja correctamente campos null
    """
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
        "rol": _rol_str(u)
    }

    return ClienteOut(**cliente_dict)


def _entrenador_out(u: Usuario) -> EntrenadorOut:
    """
    ✅ Convierte usuario a EntrenadorOut
    Maneja correctamente campos null con defaults
    """
    rol_value = _rol_str(u)

    # ✅ Convertir rating a float, con default 0.0 si es None
    rating_value = None
    rating_raw = getattr(u, "rating", None)
    if rating_raw is not None:
        try:
            rating_value = float(rating_raw)
        except (ValueError, TypeError):
            rating_value = None

    return EntrenadorOut(
        id_usuario=int(u.id_usuario),
        nombre=_nombre_completo(u),
        especialidad=getattr(u, "especialidad", None),
        rating=rating_value,  # ✅ None es aceptado (Optional)
        foto_url=getattr(u, "foto_url", None),
        email=u.email,
        ciudad=getattr(u, "ciudad", None),
        rol=rol_value
    )


# ============================================================
# ENDPOINTS
# ============================================================


@router.post(
    "/contratar",
    response_model=ClienteEntrenadorOut,
    status_code=status.HTTP_201_CREATED
)
def contratar_entrenador(payload: ClienteEntrenadorCreate, db: Session = Depends(get_db)):
    """
    ✅ Cliente contrata un entrenador

    Validaciones:
    - No puede contratarse a sí mismo
    - Entrenador debe existir
    - No puede haber relación activa duplicada
    """
    print(f"🔍 [CONTRATAR] Cliente {payload.id_cliente} contrata entrenador {payload.id_entrenador}")

    try:
        # ✅ Validar que no sea el mismo usuario
        if payload.id_cliente == payload.id_entrenador:
            raise HTTPException(
                status_code=400,
                detail="No puedes contratarte a ti mismo"
            )

        # ✅ Validar que el entrenador existe
        trainer = db.query(Usuario).filter(
            Usuario.id_usuario == payload.id_entrenador
        ).first()

        if not trainer:
            raise HTTPException(status_code=404, detail="Entrenador no encontrado")

        # ✅ Validar que no haya relación activa duplicada
        existing = db.query(ClienteEntrenador).filter(
            and_(
                ClienteEntrenador.id_cliente == payload.id_cliente,
                ClienteEntrenador.id_entrenador == payload.id_entrenador,
                ClienteEntrenador.activo == True
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Ya existe una relación activa con este entrenador"
            )

        # ✅ Crear nueva relación
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

        print(f"✅ Relación creada: {relacion.id_relacion}")

        return ClienteEntrenadorOut(
            id_relacion=relacion.id_relacion,
            id_cliente=relacion.id_cliente,
            id_entrenador=relacion.id_entrenador,
            fecha_contratacion=relacion.fecha_contratacion.isoformat(),
            estado=relacion.estado,
            activo=relacion.activo,
            notas=relacion.notas,
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en contratar_entrenador: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al contratar: {str(e)}")


@router.get(
    "/mis-clientes/{id_entrenador}",
    response_model=List[ClienteConRelacionOut]
)
def mis_clientes(id_entrenador: int, db: Session = Depends(get_db)):
    """
    ✅ Entrenador obtiene su lista de clientes

    Solo muestra clientes con relación activa
    """
    print(f"🔍 [MIS-CLIENTES] Entrenador {id_entrenador} obtiene sus clientes")

    try:
        # ✅ Obtener todas las relaciones activas
        relaciones = db.query(ClienteEntrenador).filter(
            and_(
                ClienteEntrenador.id_entrenador == id_entrenador,
                ClienteEntrenador.activo == True,
                ClienteEntrenador.estado == "activo"
            )
        ).all()

        print(f"📊 Se encontraron {len(relaciones)} clientes")

        resultado = []
        for relacion in relaciones:
            # ✅ Obtener datos del cliente
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
            else:
                print(f"⚠️ Cliente {relacion.id_cliente} no encontrado")

        return resultado

    except Exception as e:
        print(f"❌ Error en mis_clientes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get(
    "/mi-entrenador/{id_cliente}",
    response_model=Optional[EntrenadorConRelacionOut]
)
def mi_entrenador(id_cliente: int, db: Session = Depends(get_db)):
    """
    ✅ Cliente obtiene su entrenador actual

    Retorna:
    - EntrenadorConRelacionOut si tiene entrenador activo
    - None si no tiene entrenador

    NO lanza excepción si no hay entrenador, simplemente retorna null
    """
    print(f"🔍 [MI-ENTRENADOR] Cliente {id_cliente} obtiene su entrenador")

    try:
        # ✅ Buscar relación activa
        relacion = db.query(ClienteEntrenador).filter(
            and_(
                ClienteEntrenador.id_cliente == id_cliente,
                ClienteEntrenador.activo == True,
                ClienteEntrenador.estado == "activo"
            )
        ).first()

        # ✅ Si no hay relación, retornar None sin error
        if not relacion:
            print(f"⚠️ Cliente {id_cliente} no tiene entrenador asignado")
            return None

        # ✅ Obtener datos del entrenador
        entrenador_user = db.query(Usuario).filter(
            Usuario.id_usuario == relacion.id_entrenador
        ).first()

        if not entrenador_user:
            print(f"⚠️ Entrenador {relacion.id_entrenador} no encontrado")
            return None

        # ✅ Construir respuesta
        entrenador_out = _entrenador_out(entrenador_user)

        print(f"✅ Entrenador encontrado: {entrenador_out.nombre}")

        return EntrenadorConRelacionOut(
            entrenador=entrenador_out,
            fecha_contratacion=relacion.fecha_contratacion.isoformat(),
            estado=relacion.estado,
            notas=relacion.notas,
        )

    except Exception as e:
        print(f"❌ Error en mi_entrenador: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/relacion", response_model=bool)
def verificar_relacion(
        id_cliente: int = Query(...),
        id_entrenador: int = Query(...),
        db: Session = Depends(get_db)
):
    """
    ✅ Verifica si existe relación activa entre cliente y entrenador

    Query params:
    - id_cliente: ID del cliente
    - id_entrenador: ID del entrenador
    """
    print(f"🔍 [RELACION] Verificando relación {id_cliente}-{id_entrenador}")

    try:
        relacion = db.query(ClienteEntrenador).filter(
            and_(
                ClienteEntrenador.id_cliente == id_cliente,
                ClienteEntrenador.id_entrenador == id_entrenador,
                ClienteEntrenador.activo == True,
                ClienteEntrenador.estado == "activo"
            )
        ).first()

        existe = relacion is not None
        print(f"✅ Relación existe: {existe}")
        return existe

    except Exception as e:
        print(f"❌ Error en verificar_relacion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.delete(
    "/{id_relacion}",
    status_code=status.HTTP_204_NO_CONTENT
)
def cancelar_relacion(id_relacion: int, db: Session = Depends(get_db)):
    """
    ✅ Cancela una relación cliente-entrenador
    """
    print(f"🔍 [CANCELAR] Cancelando relación {id_relacion}")

    try:
        # ✅ Obtener relación
        relacion = db.query(ClienteEntrenador).filter(
            ClienteEntrenador.id_relacion == id_relacion
        ).first()

        if not relacion:
            raise HTTPException(
                status_code=404,
                detail=f"Relación {id_relacion} no encontrada"
            )

        # ✅ Actualizar estado
        relacion.estado = "cancelado"
        relacion.activo = False
        relacion.fecha_fin = datetime.utcnow()

        db.add(relacion)
        db.commit()

        print(f"✅ Relación cancelada")
        return None

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en cancelar_relacion: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")