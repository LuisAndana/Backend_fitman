# routers/rutinas.py - VERSIÓN ULTRA FLEXIBLE PARA DIAGNOSTICAR

from fastapi import APIRouter, HTTPException, status, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
from db import get_connection


# ============================================================
# 📋 MODELOS PYDANTIC
# ============================================================

class EjercicioRutina(BaseModel):
    """Estructura de un ejercicio dentro de la rutina"""
    id_ejercicio: Optional[int] = None
    nombre: str
    descripcion: Optional[str] = None
    grupo_muscular: str
    dificultad: str
    tipo: str
    series: Optional[int] = None
    repeticiones: Optional[int] = None
    descanso_segundos: Optional[int] = None
    notas: Optional[str] = None

    class Config:
        extra = "allow"  # Permite campos adicionales


class DiaRutina(BaseModel):
    """Estructura de un día dentro de la rutina"""
    numero_dia: int
    nombre_dia: str
    descripcion: Optional[str] = None
    grupos_enfoque: List[str] = []
    ejercicios: List[EjercicioRutina] = []

    class Config:
        extra = "allow"


class RutinaCreate(BaseModel):
    """Modelo para crear una rutina completa"""
    nombre: str
    descripcion: str
    creado_por: int
    objetivo: Optional[str] = None
    grupo_muscular: Optional[str] = "general"
    nivel: Optional[str] = "intermedio"
    dias_semana: Optional[int] = 4
    total_ejercicios: Optional[int] = 0
    minutos_aproximados: Optional[int] = 0
    fecha_creacion: Optional[str] = None
    generada_por: Optional[str] = "IA"
    dias: Optional[List[DiaRutina]] = []
    ejercicios: Optional[List[EjercicioRutina]] = []

    class Config:
        extra = "allow"  # Permite campos adicionales


class RutinaUpdate(BaseModel):
    """Modelo para actualizar una rutina"""
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    objetivo: Optional[str] = None
    grupo_muscular: Optional[str] = None
    nivel: Optional[str] = None
    dias_semana: Optional[int] = None
    total_ejercicios: Optional[int] = None
    minutos_aproximados: Optional[int] = None
    dias: Optional[List[DiaRutina]] = None
    ejercicios: Optional[List[EjercicioRutina]] = None


class RutinaOut(BaseModel):
    """Modelo de respuesta de rutina"""
    id_rutina: Optional[int] = None
    nombre: str
    descripcion: str
    creado_por: int
    objetivo: Optional[str] = None
    grupo_muscular: Optional[str] = None
    nivel: Optional[str] = None
    dias_semana: Optional[int] = None
    total_ejercicios: Optional[int] = None
    minutos_aproximados: Optional[int] = None
    fecha_creacion: Optional[str] = None
    generada_por: Optional[str] = None
    dias: Optional[List[DiaRutina]] = []

    class Config:
        from_attributes = True
        extra = "allow"


class UsuarioCreate(BaseModel):
    email: str
    nombre: str
    apellido: str
    rol: str


class UsuarioOut(BaseModel):
    id_usuario: int
    email: str
    nombre: str
    apellido: str
    rol: str


class EntrenadorOut(BaseModel):
    id_usuario: int
    nombre: str
    email: str


# ============================================================
# 🔹 ROUTER PRINCIPAL
# ============================================================

router = APIRouter()


# ============================================================
# 🔹 ENDPOINT DE DIAGNÓSTICO - ACEPTA CUALQUIER COSA
# ============================================================

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
def crear_rutina(payload: Dict[str, Any] = Body(...)):
    """
    ✅ Crear una rutina - VERSIÓN DIAGNÓSTICO
    Acepta CUALQUIER estructura JSON
    """
    cn = None
    try:
        print("\n" + "=" * 100)
        print("🔍 DEBUG COMPLETO: POST /api/rutinas/")
        print("=" * 100)

        print(f"\n📥 DATOS RECIBIDOS (RAW):")
        print(f"Type: {type(payload)}")
        print(f"Content: {json.dumps(payload, indent=2, default=str)}")

        # Extraer datos con defaults
        nombre = payload.get('nombre')
        descripcion = payload.get('descripcion')
        creado_por = payload.get('creado_por')
        objetivo = payload.get('objetivo', '')
        grupo_muscular = payload.get('grupo_muscular', 'general')
        nivel = payload.get('nivel', 'intermedio')
        dias_semana = payload.get('dias_semana', 4)
        total_ejercicios = payload.get('total_ejercicios', 0)
        minutos_aproximados = payload.get('minutos_aproximados', 0)
        fecha_creacion = payload.get('fecha_creacion')
        generada_por = payload.get('generada_por', 'IA')
        dias = payload.get('dias', [])
        ejercicios = payload.get('ejercicios', [])

        print(f"\n📋 DATOS PARSEADOS:")
        print(f"   nombre: {nombre} (type: {type(nombre)})")
        print(f"   descripcion: {descripcion} (type: {type(descripcion)})")
        print(f"   creado_por: {creado_por} (type: {type(creado_por)})")
        print(f"   objetivo: {objetivo}")
        print(f"   grupo_muscular: {grupo_muscular}")
        print(f"   nivel: {nivel}")
        print(f"   dias_semana: {dias_semana} (type: {type(dias_semana)})")
        print(f"   total_ejercicios: {total_ejercicios} (type: {type(total_ejercicios)})")
        print(f"   minutos_aproximados: {minutos_aproximados} (type: {type(minutos_aproximados)})")
        print(f"   fecha_creacion: {fecha_creacion}")
        print(f"   generada_por: {generada_por}")
        print(f"   dias (count): {len(dias) if isinstance(dias, list) else 'NOT A LIST'}")
        print(f"   ejercicios (count): {len(ejercicios) if isinstance(ejercicios, list) else 'NOT A LIST'}")

        # Validaciones
        print(f"\n✅ VALIDANDO...")
        if not nombre or len(str(nombre).strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="nombre es obligatorio y no puede estar vacío"
            )
        print(f"   ✓ nombre OK")

        if not descripcion or len(str(descripcion).strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="descripcion es obligatoria y no puede estar vacía"
            )
        print(f"   ✓ descripcion OK")

        if not creado_por or int(creado_por) <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="creado_por es obligatorio y debe ser > 0"
            )
        print(f"   ✓ creado_por OK")

        # Preparar datos
        fecha_creacion = fecha_creacion or datetime.now().isoformat()

        # Convertir días a JSON
        dias_json = json.dumps(dias) if dias else "[]"

        print(f"   ✓ Datos preparados")

        # Conectar a BD
        print(f"\n🔗 CONECTANDO A BD...")
        cn = get_connection()
        cur = cn.cursor()
        print(f"✅ Conectado a BD")

        # Insertar rutina
        print(f"\n💾 EJECUTANDO INSERT...")
        sql = """
            INSERT INTO rutinas (
                nombre, descripcion, creado_por, objetivo,
                grupo_muscular, nivel, dias_semana,
                total_ejercicios, minutos_aproximados,
                fecha_creacion, generada_por, contenido_dias
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            str(nombre),
            str(descripcion),
            int(creado_por),
            str(objetivo) or '',
            str(grupo_muscular) or 'general',
            str(nivel) or 'intermedio',
            int(dias_semana) or 4,
            int(total_ejercicios) or 0,
            int(minutos_aproximados) or 0,
            fecha_creacion,
            str(generada_por) or 'IA',
            dias_json
        )

        print(f"SQL: {sql}")
        print(f"VALUES: {values}")

        cur.execute(sql, values)
        print("✅ INSERT ejecutado")

        cn.commit()
        print("✅ Cambios confirmados")

        new_id = cur.lastrowid
        print(f"✅ Rutina creada con ID: {new_id}")

        print("\n" + "=" * 100)
        print("✅ ¡ÉXITO! Rutina guardada correctamente")
        print("=" * 100 + "\n")

        return {
            "id_rutina": new_id,
            "mensaje": "✅ Rutina creada exitosamente",
            "debug": {
                "datos_recibidos": payload,
                "tipos": {
                    "nombre": str(type(nombre)),
                    "descripcion": str(type(descripcion)),
                    "creado_por": str(type(creado_por)),
                }
            }
        }

    except HTTPException as he:
        print(f"\n❌ HTTPException: {he.detail}")
        print("=" * 100 + "\n")
        raise he
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print(f"   Tipo: {type(e).__name__}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        print("=" * 100 + "\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear rutina: {str(e)}"
        )
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


@router.get("/", response_model=List[RutinaOut])
def listar_rutinas():
    """✅ Listar todas las rutinas"""
    cn = None
    try:
        print("🔍 DEBUG: GET /api/rutinas/")
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        cur.execute("""
            SELECT 
                r.id_rutina, r.nombre, r.descripcion, r.creado_por,
                r.objetivo, r.grupo_muscular, r.nivel, r.dias_semana,
                r.total_ejercicios, r.minutos_aproximados,
                r.fecha_creacion, r.generada_por, r.contenido_dias
            FROM rutinas r
            ORDER BY r.fecha_creacion DESC
        """)

        rutinas = cur.fetchall()

        print(f"✅ Se obtuvieron {len(rutinas)} rutinas")

        # Convertir JSON string de vuelta a objeto
        for rutina in rutinas:
            if rutina.get('contenido_dias'):
                try:
                    rutina['dias'] = json.loads(rutina['contenido_dias'])
                except:
                    rutina['dias'] = []
            else:
                rutina['dias'] = []
            if 'contenido_dias' in rutina:
                del rutina['contenido_dias']

        return rutinas

    except Exception as e:
        print(f"❌ Error al listar rutinas: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al listar rutinas")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


@router.get("/{id_rutina}", response_model=RutinaOut)
def obtener_rutina(id_rutina: int):
    """✅ Obtener rutina específica"""
    cn = None
    try:
        print(f"🔍 DEBUG: GET /api/rutinas/{id_rutina}")
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        cur.execute("""
            SELECT 
                id_rutina, nombre, descripcion, creado_por,
                objetivo, grupo_muscular, nivel, dias_semana,
                total_ejercicios, minutos_aproximados,
                fecha_creacion, generada_por, contenido_dias
            FROM rutinas WHERE id_rutina = %s
        """, (id_rutina,))

        rutina = cur.fetchone()

        if not rutina:
            raise HTTPException(status_code=404, detail="Rutina no encontrada")

        # Convertir JSON
        if rutina.get('contenido_dias'):
            try:
                rutina['dias'] = json.loads(rutina['contenido_dias'])
            except:
                rutina['dias'] = []
        else:
            rutina['dias'] = []
        del rutina['contenido_dias']

        return rutina

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al obtener rutina")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


@router.put("/{id_rutina}", response_model=Dict[str, Any])
def actualizar_rutina(id_rutina: int, payload: Dict[str, Any] = Body(...)):
    """✅ Actualizar rutina"""
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor()

        campos = []
        valores = []

        for key, value in payload.items():
            if value is not None and key not in ['id_rutina', 'fecha_creacion']:
                if key == 'dias':
                    campos.append("contenido_dias = %s")
                    valores.append(json.dumps(value))
                else:
                    campos.append(f"{key} = %s")
                    valores.append(value)

        if not campos:
            raise HTTPException(status_code=400, detail="No hay campos para actualizar")

        valores.append(id_rutina)
        sql = f"UPDATE rutinas SET {', '.join(campos)} WHERE id_rutina = %s"

        cur.execute(sql, valores)
        cn.commit()

        return {"id_rutina": id_rutina, "mensaje": "✅ Rutina actualizada"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


@router.delete("/{id_rutina}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_rutina(id_rutina: int):
    """✅ Eliminar rutina"""
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor()

        cur.execute("DELETE FROM rutinas WHERE id_rutina = %s", (id_rutina,))
        cn.commit()

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rutina no encontrada")

        return None

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al eliminar rutina")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


# ============================================================
# 🔹 ENDPOINTS STUBS
# ============================================================

@router.get("/usuarios/", response_model=List[UsuarioOut], tags=["Usuarios"])
def listar_usuarios():
    return []


@router.get("/usuarios/{id_usuario}", response_model=UsuarioOut, tags=["Usuarios"])
def obtener_usuario(id_usuario: int):
    raise HTTPException(status_code=404, detail="Usuario no encontrado")


@router.post("/usuarios/", status_code=status.HTTP_201_CREATED, tags=["Usuarios"])
def crear_usuario(payload: UsuarioCreate):
    return {"id": 1, "mensaje": "Usuario creado"}


@router.get("/entrenadores/", response_model=List[EntrenadorOut], tags=["Entrenadores"])
def listar_entrenadores():
    return []


@router.get("/entrenadores/{id_entrenador}", response_model=EntrenadorOut, tags=["Entrenadores"])
def obtener_entrenador(id_entrenador: int):
    raise HTTPException(status_code=404, detail="Entrenador no encontrado")


@router.get("/ejercicios/", tags=["Ejercicios"])
def listar_ejercicios():
    return []


@router.get("/asignaciones/", tags=["Asignaciones"])
def listar_asignaciones():
    return []


@router.get("/resenas/", tags=["Reseñas"])
def listar_resenas():
    return []


@router.get("/mensajes/", tags=["Mensajes"])
def listar_mensajes():
    return []


@router.get("/pagos/", tags=["Pagos"])
def listar_pagos():
    return []


@router.get("/ia/status", tags=["IA"])
def ia_status():
    return {"status": "ok"}