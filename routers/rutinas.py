# routers/rutinas.py - VERSIÓN CORREGIDA PARA GUARDAR CORRECTAMENTE

from fastapi import APIRouter, HTTPException, status, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import json
from db import get_connection


# ============================================================
# 🔹 MODELOS PYDANTIC
# ============================================================

class EjercicioRutina(BaseModel):
    """Modelo de ejercicio dentro de una rutina"""
    nombre: str
    series: int
    repeticiones: str
    descanso: str
    notas: Optional[str] = None


class DiaRutina(BaseModel):
    """Modelo de día dentro de una rutina"""
    dia: str
    musculo: str
    ejercicios: List[EjercicioRutina]


class RutinaCreate(BaseModel):
    """Modelo de entrada para crear rutina"""
    nombre: str
    descripcion: str
    creado_por: Optional[int] = None
    id_cliente: Optional[int] = None  # Para compatibilidad con IA
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


# ============================================================
# 🔹 ROUTER PRINCIPAL
# ============================================================

router = APIRouter()


# ============================================================
# 🔹 ENDPOINT DE CREACIÓN - VERSIÓN CORREGIDA
# ============================================================

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
def crear_rutina(payload: Dict[str, Any] = Body(...)):
    """
    ✅ Crear una rutina - VERSIÓN CORREGIDA
    Acepta tanto la estructura manual como la de IA
    """
    cn = None
    cur = None
    try:
        print("\n" + "=" * 100)
        print("🔍 POST /api/rutinas/ - Guardando rutina")
        print("=" * 100)

        print(f"\n📥 DATOS RECIBIDOS:")
        print(f"Keys: {list(payload.keys())}")

        # ========================================
        # NORMALIZACIÓN DE CAMPOS
        # ========================================

        # El endpoint de IA envía "id_cliente", pero la BD espera "creado_por"
        creado_por = payload.get('creado_por') or payload.get('id_cliente')

        # Campos básicos
        nombre = payload.get('nombre', '').strip()
        descripcion = payload.get('descripcion', '').strip()
        objetivo = payload.get('objetivo', '').strip()
        grupo_muscular = payload.get('grupo_muscular', 'general').strip()
        nivel = payload.get('nivel', 'intermedio').strip()
        dias_semana = payload.get('dias_semana', 4)
        total_ejercicios = payload.get('total_ejercicios', 0)
        minutos_aproximados = payload.get('minutos_aproximados', 0)
        fecha_creacion = payload.get('fecha_creacion')
        generada_por = payload.get('generada_por', 'IA').strip()
        dias = payload.get('dias', [])

        print(f"\n📋 DATOS NORMALIZADOS:")
        print(f"   nombre: {nombre}")
        print(f"   descripcion: {descripcion}")
        print(f"   creado_por: {creado_por} (de id_cliente o creado_por)")
        print(f"   dias_semana: {dias_semana}")
        print(f"   dias (count): {len(dias) if isinstance(dias, list) else 0}")

        # ========================================
        # VALIDACIONES
        # ========================================

        if not nombre:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El campo 'nombre' es obligatorio y no puede estar vacío"
            )

        if not descripcion:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El campo 'descripcion' es obligatorio y no puede estar vacío"
            )

        if not creado_por:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El campo 'creado_por' o 'id_cliente' es obligatorio"
            )

        try:
            creado_por = int(creado_por)
            if creado_por <= 0:
                raise ValueError("El ID debe ser mayor a 0")
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El campo 'creado_por' debe ser un número entero positivo: {str(e)}"
            )

        print(f"   ✅ Validaciones pasadas")

        # ========================================
        # PREPARAR DATOS PARA BD
        # ========================================

        # Convertir días a JSON si existen
        if dias and isinstance(dias, list):
            # Asegurarse de que sea serializable
            dias_json = json.dumps(dias, ensure_ascii=False)
        else:
            dias_json = "[]"

        # Fecha de creación
        if not fecha_creacion:
            fecha_creacion = datetime.now().isoformat()

        print(f"\n📦 DATOS PREPARADOS PARA BD:")
        print(f"   nombre: {nombre}")
        print(f"   descripcion: {descripcion[:50]}...")
        print(f"   creado_por: {creado_por}")
        print(f"   dias_json length: {len(dias_json)} chars")

        # ========================================
        # INSERTAR EN BD
        # ========================================

        print(f"\n🔗 CONECTANDO A BD...")
        cn = get_connection()
        cur = cn.cursor()
        print(f"✅ Conectado")

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
            nombre,
            descripcion,
            creado_por,
            objetivo if objetivo else '',
            grupo_muscular,
            nivel,
            int(dias_semana) if dias_semana else 4,
            int(total_ejercicios) if total_ejercicios else 0,
            int(minutos_aproximados) if minutos_aproximados else 0,
            fecha_creacion,
            generada_por,
            dias_json
        )

        print(f"\n💾 EJECUTANDO INSERT...")
        print(f"SQL: {sql}")
        print(f"VALUES: {values[:3]}... (mostrando primeros 3)")

        cur.execute(sql, values)
        print(f"✅ INSERT ejecutado")

        cn.commit()
        print(f"✅ COMMIT realizado")

        new_id = cur.lastrowid
        print(f"✅ Rutina creada con ID: {new_id}")

        # ========================================
        # PREPARAR RESPUESTA
        # ========================================

        rutina_guardada = {
            "id_rutina": new_id,
            "nombre": nombre,
            "descripcion": descripcion,
            "creado_por": creado_por,
            "objetivo": objetivo,
            "grupo_muscular": grupo_muscular,
            "nivel": nivel,
            "dias_semana": int(dias_semana) if dias_semana else 4,
            "total_ejercicios": int(total_ejercicios) if total_ejercicios else 0,
            "minutos_aproximados": int(minutos_aproximados) if minutos_aproximados else 0,
            "fecha_creacion": fecha_creacion,
            "generada_por": generada_por,
            "dias": dias if dias else []
        }

        print(f"\n" + "=" * 100)
        print(f"✅ ¡RUTINA GUARDADA EXITOSAMENTE!")
        print(f"   ID: {new_id}")
        print(f"   Nombre: {nombre}")
        print(f"=" * 100 + "\n")

        return {
            "mensaje": "✅ Rutina creada exitosamente",
            "id_rutina": new_id,
            "rutina": rutina_guardada
        }

    except HTTPException:
        # Re-lanzar excepciones HTTP
        raise

    except Exception as e:
        print(f"\n❌ ERROR INESPERADO:")
        print(f"   Tipo: {type(e).__name__}")
        print(f"   Mensaje: {str(e)}")

        import traceback
        print(f"\n📋 TRACEBACK COMPLETO:")
        print(traceback.format_exc())

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear rutina: {str(e)}"
        )

    finally:
        # Cerrar conexiones
        if cur:
            cur.close()
            print(f"🔒 Cursor cerrado")
        if cn:
            cn.close()
            print(f"🔒 Conexión cerrada")


# ============================================================
# 🔹 OBTENER TODAS LAS RUTINAS
# ============================================================

@router.get("/", response_model=List[Dict[str, Any]])
def listar_rutinas():
    """
    Listar todas las rutinas
    """
    cn = None
    cur = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        sql = """
            SELECT 
                id_rutina, nombre, descripcion, creado_por,
                objetivo, grupo_muscular, nivel, dias_semana,
                total_ejercicios, minutos_aproximados,
                fecha_creacion, generada_por, contenido_dias
            FROM rutinas
            ORDER BY fecha_creacion DESC
        """

        cur.execute(sql)
        rutinas = cur.fetchall()

        # Parsear el JSON de contenido_dias
        for rutina in rutinas:
            if rutina.get('contenido_dias'):
                try:
                    rutina['dias'] = json.loads(rutina['contenido_dias'])
                except:
                    rutina['dias'] = []
            else:
                rutina['dias'] = []

            # Convertir fecha a string si es necesario
            if rutina.get('fecha_creacion'):
                if isinstance(rutina['fecha_creacion'], datetime):
                    rutina['fecha_creacion'] = rutina['fecha_creacion'].isoformat()

        return rutinas

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar rutinas: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if cn:
            cn.close()


# ============================================================
# 🔹 OBTENER RUTINA POR ID
# ============================================================

@router.get("/{id_rutina}", response_model=Dict[str, Any])
def obtener_rutina(id_rutina: int):
    """
    Obtener una rutina específica por ID
    """
    cn = None
    cur = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        sql = """
            SELECT 
                id_rutina, nombre, descripcion, creado_por,
                objetivo, grupo_muscular, nivel, dias_semana,
                total_ejercicios, minutos_aproximados,
                fecha_creacion, generada_por, contenido_dias
            FROM rutinas
            WHERE id_rutina = %s
        """

        cur.execute(sql, (id_rutina,))
        rutina = cur.fetchone()

        if not rutina:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rutina con ID {id_rutina} no encontrada"
            )

        # Parsear el JSON de contenido_dias
        if rutina.get('contenido_dias'):
            try:
                rutina['dias'] = json.loads(rutina['contenido_dias'])
            except:
                rutina['dias'] = []
        else:
            rutina['dias'] = []

        # Convertir fecha a string si es necesario
        if rutina.get('fecha_creacion'):
            if isinstance(rutina['fecha_creacion'], datetime):
                rutina['fecha_creacion'] = rutina['fecha_creacion'].isoformat()

        return rutina

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener rutina: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if cn:
            cn.close()


# ============================================================
# 🔹 ACTUALIZAR RUTINA
# ============================================================

@router.put("/{id_rutina}", response_model=Dict[str, Any])
def actualizar_rutina(id_rutina: int, payload: Dict[str, Any] = Body(...)):
    """
    Actualizar una rutina existente
    """
    cn = None
    cur = None
    try:
        cn = get_connection()
        cur = cn.cursor()

        # Verificar que la rutina existe
        cur.execute("SELECT id_rutina FROM rutinas WHERE id_rutina = %s", (id_rutina,))
        if not cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rutina con ID {id_rutina} no encontrada"
            )

        # Preparar campos a actualizar
        campos = []
        valores = []

        if 'nombre' in payload:
            campos.append("nombre = %s")
            valores.append(payload['nombre'])

        if 'descripcion' in payload:
            campos.append("descripcion = %s")
            valores.append(payload['descripcion'])

        if 'objetivo' in payload:
            campos.append("objetivo = %s")
            valores.append(payload['objetivo'])

        if 'grupo_muscular' in payload:
            campos.append("grupo_muscular = %s")
            valores.append(payload['grupo_muscular'])

        if 'nivel' in payload:
            campos.append("nivel = %s")
            valores.append(payload['nivel'])

        if 'dias_semana' in payload:
            campos.append("dias_semana = %s")
            valores.append(payload['dias_semana'])

        if 'dias' in payload:
            campos.append("contenido_dias = %s")
            valores.append(json.dumps(payload['dias'], ensure_ascii=False))

        if not campos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay campos para actualizar"
            )

        # Agregar ID al final
        valores.append(id_rutina)

        sql = f"UPDATE rutinas SET {', '.join(campos)} WHERE id_rutina = %s"
        cur.execute(sql, valores)
        cn.commit()

        return {
            "mensaje": "✅ Rutina actualizada exitosamente",
            "id_rutina": id_rutina
        }

    except HTTPException:
        raise
    except Exception as e:
        if cn:
            cn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar rutina: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if cn:
            cn.close()


# ============================================================
# 🔹 ELIMINAR RUTINA
# ============================================================

@router.delete("/{id_rutina}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_rutina(id_rutina: int):
    """
    Eliminar una rutina
    """
    cn = None
    cur = None
    try:
        cn = get_connection()
        cur = cn.cursor()

        # Verificar que la rutina existe
        cur.execute("SELECT id_rutina FROM rutinas WHERE id_rutina = %s", (id_rutina,))
        if not cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rutina con ID {id_rutina} no encontrada"
            )

        # Eliminar la rutina
        cur.execute("DELETE FROM rutinas WHERE id_rutina = %s", (id_rutina,))
        cn.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        if cn:
            cn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar rutina: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if cn:
            cn.close()


# ============================================================
# 🔹 OBTENER RUTINAS POR ALUMNO
# ============================================================

@router.get("/alumno/{id_alumno}", response_model=List[Dict[str, Any]])
def obtener_rutinas_alumno(id_alumno: int):
    """
    Obtener todas las rutinas de un alumno específico
    """
    cn = None
    cur = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        sql = """
            SELECT 
                id_rutina, nombre, descripcion, creado_por,
                objetivo, grupo_muscular, nivel, dias_semana,
                total_ejercicios, minutos_aproximados,
                fecha_creacion, generada_por, contenido_dias
            FROM rutinas
            WHERE creado_por = %s
            ORDER BY fecha_creacion DESC
        """

        cur.execute(sql, (id_alumno,))
        rutinas = cur.fetchall()

        # Parsear el JSON de contenido_dias
        for rutina in rutinas:
            if rutina.get('contenido_dias'):
                try:
                    rutina['dias'] = json.loads(rutina['contenido_dias'])
                except:
                    rutina['dias'] = []
            else:
                rutina['dias'] = []

            # Convertir fecha a string si es necesario
            if rutina.get('fecha_creacion'):
                if isinstance(rutina['fecha_creacion'], datetime):
                    rutina['fecha_creacion'] = rutina['fecha_creacion'].isoformat()

        return rutinas

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener rutinas del alumno: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if cn:
            cn.close()