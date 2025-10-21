# routers/rutinas.py
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from db import get_connection

router = APIRouter()

# -------- Modelos --------
class RutinaCreate(BaseModel):
    nombre: str
    descripcion: str
    creado_por: int  # id_usuario del entrenador/creador

class RutinaOut(BaseModel):
    id_rutina: int
    nombre: str
    descripcion: str
    creado_por: int
    entrenador: Optional[str] = None

# -------- Endpoints --------
@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_rutina(payload: RutinaCreate):
    """
    Crea una rutina y devuelve:
      { "id": <lastrowid>, "mensaje": "Rutina creada" }
    (mismo formato que tu Flask para no romper el front)
    """
    try:
        cn = get_connection()
        cur = cn.cursor()
        sql = """
            INSERT INTO rutinas (nombre, descripcion, creado_por)
            VALUES (%s, %s, %s)
        """
        values = (payload.nombre, payload.descripcion, payload.creado_por)
        cur.execute(sql, values)
        cn.commit()
        new_id = cur.lastrowid
        return {"id": new_id, "mensaje": "Rutina creada"}
    except Exception as e:
        # Puedes loguear e si lo deseas
        raise HTTPException(status_code=500, detail="Error al crear rutina")
    finally:
        try:
            cur.close()
            cn.close()
        except Exception:
            pass

@router.get("/", response_model=List[RutinaOut])
def listar_rutinas():
    """
    Lista rutinas incluyendo el nombre del entrenador (JOIN a usuarios).
    """
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)
        cur.execute("""
            SELECT 
                r.id_rutina,
                r.nombre,
                r.descripcion,
                r.creado_por,
                u.nombre AS entrenador
            FROM rutinas r 
            JOIN usuarios u ON r.creado_por = u.id_usuario
        """)
        rows = cur.fetchall()
        # Pydantic validará/serializará a RutinaOut
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al listar rutinas")
    finally:
        try:
            cur.close()
            cn.close()
        except Exception:
            pass
