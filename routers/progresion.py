# routers/progresion.py
from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from db import get_connection
from sqlalchemy.orm import Session
from utils.dependencies import get_db
import json

router = APIRouter()


# ============================================================
# 🔹 MODELOS PYDANTIC
# ============================================================

class MetricaProgreso(BaseModel):
    """Métricas individuales de progreso"""
    ejercicio: str
    peso_inicial: float
    peso_actual: float
    mejora_porcentaje: float
    tendencia: str  # "mejorando", "estancado", "bajando"


class DashboardProgreso(BaseModel):
    """Dashboard general del progreso del cliente"""
    id_cliente: int
    nombre_cliente: str
    dias_entrenando: int
    sesiones_completadas: int
    rutinas_activas: int
    ultima_rutina: Optional[str] = None
    ultimo_entrenamiento: Optional[str] = None
    progreso_general: float  # Porcentaje 0-100


class HistorialProgreso(BaseModel):
    """Entrada del historial de progreso"""
    fecha: str
    rutina: str
    objetivo: Optional[str] = None
    duracion_meses: int
    ejercicios_totales: int
    estado: str
    entrenador: Optional[str] = None


class AlertaProgreso(BaseModel):
    """Alerta de progreso o estancamiento"""
    id_alerta: int
    tipo: str  # "rutina_expira", "sin_rutina", "nueva_rutina", "objetivo_cerca"
    titulo: str
    mensaje: str
    fecha: str
    prioridad: str  # "alta", "media", "baja"
    leida: bool = False


class ObjetivoProgreso(BaseModel):
    """Objetivo de progreso del cliente basado en rutinas"""
    id_objetivo: int
    tipo: str  # "rutina", "consistencia", "fuerza"
    descripcion: str
    fecha_inicio: str
    fecha_fin: Optional[str] = None
    progreso: float
    estado: str  # "activo", "completado", "expirado"


# ============================================================
# 🔹 ENDPOINTS CON DATOS REALES
# ============================================================
@router.post("/alertas/analizar/{id_cliente}")
def analizar_progresion_cliente(id_cliente: int):
    """
    ✅ Analiza la progresión del cliente y genera alertas automáticas
    """
    cn = None
    try:
        print(f"\n🔍 DEBUG: POST /progresion/alertas/analizar/{id_cliente}")
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # Verificar que el cliente existe
        cur.execute("""
            SELECT id_usuario FROM usuarios 
            WHERE id_usuario = %s AND rol = 'alumno'
        """, (id_cliente,))

        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"Cliente {id_cliente} no encontrado")

        alertas_generadas = 0

        # Aquí puedes implementar la lógica de análisis
        # Por ahora retornamos una respuesta simple

        return {
            "success": True,
            "alertas_generadas": alertas_generadas,
            "mensaje": f"Análisis completado. {alertas_generadas} nuevas alertas generadas."
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en análisis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al analizar progresión: {str(e)}")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass

@router.get("/dashboard/cliente/{id_cliente}", response_model=DashboardProgreso)
def obtener_dashboard_progreso(id_cliente: int):
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # 1. Datos del cliente
        cur.execute("""
            SELECT id_usuario, nombre, apellido
            FROM usuarios
            WHERE id_usuario = %s AND rol = 'alumno'
        """, (id_cliente,))
        cliente = cur.fetchone()

        if not cliente:
            raise HTTPException(404, f"Cliente {id_cliente} no encontrado")

        # 2. Estadísticas reales
        cur.execute("""
            SELECT 
                COUNT(DISTINCT DATE(fecha_asignacion)) AS dias_entrenados,
                COUNT(*) AS total_asignaciones,
                COUNT(DISTINCT id_rutina) AS rutinas_distintas
            FROM asignaciones
            WHERE id_alumno = %s
        """, (id_cliente,))
        stats = cur.fetchone()

        # 3. Rutinas activas desde historial_rutinas
        cur.execute("""
            SELECT COUNT(*) AS rutinas_activas
            FROM historial_rutinas
            WHERE id_cliente = %s
              AND fecha_fin > NOW()
              AND estado = 'activa'
        """, (id_cliente,))
        rutinas_activas = cur.fetchone()['rutinas_activas']

        # 4. Último entrenamiento (asignaciones)
        cur.execute("""
            SELECT r.nombre AS ultima_rutina, a.fecha_asignacion AS ultimo_entrenamiento
            FROM asignaciones a
            JOIN rutinas r ON a.id_rutina = r.id_rutina
            WHERE a.id_alumno = %s
            ORDER BY a.fecha_asignacion DESC
            LIMIT 1
        """, (id_cliente,))
        ultima = cur.fetchone()

        # 5. Progreso general basado en historial
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN fecha_fin < NOW() THEN 1 END) AS expiradas,
                COUNT(*) AS total
            FROM historial_rutinas
            WHERE id_cliente = %s
        """, (id_cliente,))
        pdata = cur.fetchone()
        progreso = 0
        if pdata["total"] > 0:
            progreso = (pdata["expiradas"] / pdata["total"]) * 100

        return DashboardProgreso(
            id_cliente=id_cliente,
            nombre_cliente=f"{cliente['nombre']} {cliente['apellido']}",
            dias_entrenando=stats["dias_entrenados"],
            sesiones_completadas=stats["total_asignaciones"],
            rutinas_activas=rutinas_activas,
            ultima_rutina=ultima["ultima_rutina"] if ultima else None,
            ultimo_entrenamiento=ultima["ultimo_entrenamiento"].isoformat() if ultima else None,
            progreso_general=min(progreso, 100)
        )

    finally:
        if cn: cn.close()



@router.get("/historial/cliente/{id_cliente}", response_model=List[HistorialProgreso])
def obtener_historial_progreso(id_cliente: int, limit: int = 30, offset: int = 0):
    cn = get_connection()
    cur = cn.cursor(dictionary=True)

    # Verificar cliente
    cur.execute("""
        SELECT id_usuario FROM usuarios
        WHERE id_usuario = %s AND rol = 'alumno'
    """, (id_cliente,))
    if not cur.fetchone():
        raise HTTPException(404, f"Cliente {id_cliente} no encontrado")

    # Usar historial_rutinas real
    cur.execute("""
        SELECT 
            hr.fecha_inicio AS fecha,
            hr.nombre_rutina AS rutina,
            hr.objetivo,
            CEIL(hr.duracion_dias / 30) AS duracion_meses,
            hr.total_ejercicios,
            hr.estado,
            CONCAT(u.nombre, ' ', u.apellido) AS entrenador
        FROM historial_rutinas hr
        JOIN usuarios u ON hr.id_entrenador = u.id_usuario
        WHERE hr.id_cliente = %s
        ORDER BY hr.fecha_inicio DESC
        LIMIT %s OFFSET %s
    """, (id_cliente, limit, offset))

    data = cur.fetchall()
    historial = [
        HistorialProgreso(
            fecha=row["fecha"].isoformat(),
            rutina=row["rutina"],
            objetivo=row["objetivo"],
            duracion_meses=row["duracion_meses"],
            ejercicios_totales=row["total_ejercicios"],
            estado=row["estado"],
            entrenador=row["entrenador"]
        ) for row in data
    ]

    return historial



@router.get("/alertas/cliente/{id_cliente}", response_model=List[AlertaProgreso])
def obtener_alertas(id_cliente: int):
    cn = get_connection()
    cur = cn.cursor(dictionary=True)

    # Verificar cliente
    cur.execute("""
        SELECT id_usuario, nombre
        FROM usuarios
        WHERE id_usuario = %s AND rol = 'alumno'
    """, (id_cliente,))
    if not cur.fetchone():
        raise HTTPException(404, "Cliente no encontrado")

    alertas = []
    id_counter = 1

    # Rutinas por expirar
    cur.execute("""
        SELECT nombre_rutina, fecha_fin,
               DATEDIFF(fecha_fin, NOW()) AS dias_restantes
        FROM historial_rutinas
        WHERE id_cliente = %s
          AND estado = 'activa'
          AND fecha_fin > NOW()
          AND DATEDIFF(fecha_fin, NOW()) <= 7
    """, (id_cliente,))
    for r in cur.fetchall():
        alertas.append(AlertaProgreso(
            id_alerta=id_counter,
            tipo="rutina_expira",
            titulo="⚠️ Rutina próxima a expirar",
            mensaje=f"La rutina '{r['nombre_rutina']}' expira en {r['dias_restantes']} días",
            fecha=datetime.now().isoformat(),
            prioridad="alta",
            leida=False
        ))
        id_counter += 1

    # Sin rutinas activas
    cur.execute("""
        SELECT COUNT(*) AS activas
        FROM historial_rutinas
        WHERE id_cliente = %s
          AND estado = 'activa'
          AND fecha_fin > NOW()
    """, (id_cliente,))
    if cur.fetchone()["activas"] == 0:
        alertas.append(AlertaProgreso(
            id_alerta=id_counter,
            tipo="sin_rutina",
            titulo="📋 Sin rutina activa",
            mensaje="No tienes ninguna rutina activa.",
            fecha=datetime.now().isoformat(),
            prioridad="alta",
            leida=False
        ))
        id_counter += 1

    return alertas


@router.get("/objetivos/cliente/{id_cliente}", response_model=List[ObjetivoProgreso])
def obtener_objetivos_cliente(id_cliente: int):
    cn = get_connection()
    cur = cn.cursor(dictionary=True)

    # 1. Buscar rutina activa
    cur.execute("""
        SELECT id_historial, nombre_rutina, objetivo, fecha_inicio, fecha_fin
        FROM historial_rutinas
        WHERE id_cliente = %s 
        AND estado = 'activa'
        ORDER BY fecha_inicio DESC
        LIMIT 1
    """, (id_cliente,))

    rutina = cur.fetchone()
    if not rutina:
        return []  # sin rutina activa = sin objetivos

    # 2. Obtener ejercicios de la rutina
    cur.execute("""
        SELECT
            hre.id_ejercicio,
            e.nombre,
            hre.peso_inicial
        FROM historial_rutina_ejercicios AS hre
        INNER JOIN ejercicios AS e
            ON e.id_ejercicio = hre.id_ejercicio
        WHERE hre.id_historial = %s
    """, (rutina["id_historial"],))

    ejercicios = cur.fetchall()

    objetivos = []
    id_counter = 1

    for ej in ejercicios:
        cur.execute("""
            SELECT peso_kg 
            FROM progreso_ejercicios
            WHERE id_cliente = %s AND id_ejercicio = %s
            ORDER BY fecha_sesion DESC
            LIMIT 1
        """, (id_cliente, ej["id_ejercicio"]))

        ultimo = cur.fetchone()
        peso_actual = ultimo["peso_kg"] if ultimo else ej["peso_inicial"]

        # objetivo: +15% de mejora
        peso_objetivo = ej["peso_inicial"] * 1.15 if ej["peso_inicial"] else None

        porcentaje = 0
        if peso_objetivo:
            porcentaje = (peso_actual / peso_objetivo) * 100
            if porcentaje > 100:
                porcentaje = 100

        estado = (
            "alcanzado" if porcentaje >= 100 else
            "en_progreso" if porcentaje > 0 else
            "pendiente"
        )

        objetivos.append(ObjetivoProgreso(
            id_objetivo=id_counter,
            tipo="peso",
            descripcion=f"Incrementar peso en {ej['nombre']}",
            fecha_inicio=rutina["fecha_inicio"].isoformat(),
            fecha_fin=rutina["fecha_fin"].isoformat(),
            progreso=porcentaje,
            estado=estado
        ))
        id_counter += 1

    return objetivos


@router.get("/objetivos/cliente/{id_cliente}", response_model=List[ObjetivoProgreso])
def obtener_objetivos(id_cliente: int):
    cn = get_connection()
    cur = cn.cursor(dictionary=True)

    # validar
    cur.execute("""
        SELECT id_usuario FROM usuarios
        WHERE id_usuario = %s AND rol = 'alumno'
    """, (id_cliente,))
    if not cur.fetchone():
        raise HTTPException(404, "Cliente no encontrado")

    objetivos = []
    id_counter = 1

    # Objetivos por rutina activa
    cur.execute("""
        SELECT 
            nombre_rutina,
            objetivo,
            fecha_inicio,
            fecha_fin,
            duracion_dias,
            DATEDIFF(NOW(), fecha_inicio) AS dias_transcurridos
        FROM historial_rutinas
        WHERE id_cliente = %s
          AND estado='activa'
          AND fecha_fin > NOW()
        ORDER BY fecha_inicio DESC
    """, (id_cliente,))

    for r in cur.fetchall():
        progreso = min((r['dias_transcurridos'] / r['duracion_dias']) * 100, 100)

        objetivos.append(ObjetivoProgreso(
            id_objetivo=id_counter,
            tipo="rutina",
            descripcion=f"Completar rutina: {r['nombre_rutina']}",
            fecha_inicio=r["fecha_inicio"].isoformat(),
            fecha_fin=r["fecha_fin"].isoformat(),
            progreso=progreso,
            estado="activo"
        ))
        id_counter += 1

    return objetivos


@router.get("/alertas/cliente/{id_cliente}", response_model=List[AlertaProgreso])
def obtener_alertas_cliente(id_cliente: int):
    cn = get_connection()
    cur = cn.cursor(dictionary=True)

    alertas = []
    id_counter = 1

    # 1. Detectar ejercicios con estancamiento
    cur.execute("""
        SELECT 
            p1.id_ejercicio,
            e.nombre,
            p1.peso_kg AS peso_reciente,
            p2.peso_kg AS peso_pasado
        FROM progreso_ejercicios p1
        JOIN progreso_ejercicios p2 
            ON p1.id_ejercicio = p2.id_ejercicio
        JOIN ejercicios e 
            ON e.id_ejercicio = p1.id_ejercicio
        WHERE p1.id_cliente = %s
        AND p2.id_cliente = %s
        AND p1.numero_sesion = p2.numero_sesion + 3
    """, (id_cliente, id_cliente))

    for row in cur.fetchall():
        if row["peso_reciente"] <= row["peso_pasado"]:
            alertas.append(AlertaProgreso(
                id_alerta=id_counter,
                tipo="aumentar_peso",
                titulo="Debes aumentar el peso",
                mensaje=f"En el ejercicio {row['nombre']} te has estancado. Intenta subir el peso.",
                prioridad="media",
                fecha=datetime.now().isoformat(),
                leida=False
            ))
            id_counter += 1

    return alertas

@router.post("/progresion/historial/crear")
def crear_historial(id_rutina: int, id_cliente: int):
    cn = get_connection()
    cur = cn.cursor()

    # 1. Crear historial
    cur.execute("""
        INSERT INTO historial_rutinas(id_cliente, nombre_rutina, fecha_inicio, fecha_fin, estado)
        SELECT id_cliente, nombre, NOW(), DATE_ADD(NOW(), INTERVAL duracion_meses MONTH), 'activa'
        FROM rutinas WHERE id_rutina = %s
    """, (id_rutina,))
    id_historial = cur.lastrowid

    # 2. Copiar ejercicios
    cur.execute("""
        INSERT INTO historial_rutina_ejercicios(id_historial, id_ejercicio, nombre_ejercicio, series, repeticiones, peso_sugerido)
        SELECT %s, id_ejercicio, nombre, series, repeticiones, 0
        FROM rutina_ejercicios
        WHERE id_rutina = %s
    """, (id_historial, id_rutina))

    cn.commit()
    return {"success": True, "id_historial": id_historial}
