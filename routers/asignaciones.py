# routers/asignaciones.py
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from db import get_connection

router = APIRouter()

# -------- Modelos --------
class AsignacionCreate(BaseModel):
    id_rutina: int
    id_alumno: int

class AsignacionOut(BaseModel):
    id_asignacion: int
    rutina: str
    descripcion: str
    estado: Optional[str] = None
    fecha_asignacion: Optional[datetime] = None  # si tu DB devuelve string, puedes cambiar a Optional[str]

# -------- Endpoints --------
@router.post("/", status_code=status.HTTP_201_CREATED)
def asignar_rutina(payload: AsignacionCreate):
    """
    Crea una asignación y devuelve: { "id": <lastrowid>, "mensaje": "Rutina asignada" }
    (se mantiene el mismo formato que tu Flask para no romper el front)
    """
    cn = None
    cur = None
    try:
        cn = get_connection()
        cur = cn.cursor()
        sql = "INSERT INTO asignaciones (id_rutina, id_alumno) VALUES (%s, %s)"
        values = (payload.id_rutina, payload.id_alumno)
        cur.execute(sql, values)
        cn.commit()
        new_id = cur.lastrowid
        return {"id": new_id, "mensaje": "Rutina asignada"}
    except Exception:
        raise HTTPException(status_code=500, detail="Error al asignar rutina")
    finally:
        try:
            if cur: cur.close()
            if cn: cn.close()
        except Exception:
            pass

@router.get("/{id_alumno}", response_model=List[AsignacionOut])
def listar_asignaciones(id_alumno: int):
    """
    Lista las asignaciones de un alumno con datos de la rutina.
    """
    cn = None
    cur = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)
        cur.execute("""
            SELECT 
                a.id_asignacion,
                r.nombre AS rutina,
                r.descripcion,
                a.estado,
                a.fecha_asignacion
            FROM asignaciones a 
            JOIN rutinas r ON a.id_rutina = r.id_rutina 
            WHERE a.id_alumno = %s
        """, (id_alumno,))
        rows = cur.fetchall()
        return rows
    except Exception:
        raise HTTPException(status_code=500, detail="Error al listar asignaciones")
    finally:
        try:
            if cur: cur.close()
            if cn: cn.close()
        except Exception:
            pass
