# routers/ejercicios.py
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Any, Dict
from db import get_connection

router = APIRouter()

# -------- Modelos --------
class EjercicioCreate(BaseModel):
    nombre: str
    descripcion: str
    grupo_muscular: str
    imagen_url: Optional[HttpUrl] = None  # si puede venir vacío, déjalo Optional[str]

class EjercicioOut(BaseModel):
    id_ejercicio: int
    nombre: str
    descripcion: str
    grupo_muscular: str
    imagen_url: Optional[str] = None

# -------- Endpoints --------
@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_ejercicio(payload: EjercicioCreate):
    """
    Crea un ejercicio y devuelve:
      { "id": <lastrowid>, "mensaje": "Ejercicio creado" }
    (mismo formato que Flask para no romper el front)
    """
    cn = None
    cur = None
    try:
        cn = get_connection()
        cur = cn.cursor()
        sql = """
            INSERT INTO ejercicios (nombre, descripcion, grupo_muscular, imagen_url)
            VALUES (%s, %s, %s, %s)
        """
        values = (payload.nombre, payload.descripcion, payload.grupo_muscular, payload.imagen_url)
        cur.execute(sql, values)
        cn.commit()
        new_id = cur.lastrowid
        return {"id": new_id, "mensaje": "Ejercicio creado"}
    except Exception:
        raise HTTPException(status_code=500, detail="Error al crear ejercicio")
    finally:
        try:
            if cur: cur.close()
            if cn: cn.close()
        except Exception:
            pass

@router.get("/", response_model=List[EjercicioOut])
def listar_ejercicios():
    """
    Lista todos los ejercicios. Si tu tabla usa otro nombre de PK,
    ajusta el alias en el SELECT para mapear a id_ejercicio.
    """
    cn = None
    cur = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)
        cur.execute("""
            SELECT 
                id_ejercicio, nombre, descripcion, grupo_muscular, imagen_url
            FROM ejercicios
        """)
        rows = cur.fetchall()
        return rows
    except Exception:
        raise HTTPException(status_code=500, detail="Error al listar ejercicios")
    finally:
        try:
            if cur: cur.close()
            if cn: cn.close()
        except Exception:
            pass
