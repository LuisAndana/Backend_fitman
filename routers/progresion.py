# routers/progresion.py - VERSIÓN MEJORADA Y COMPLETA
from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import text

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
    resumen: Dict[str, Any]
    alertas_pendientes: int
    records_este_mes: int
    objetivos_activos: int


class HistorialProgreso(BaseModel):
    """Entrada del historial de progreso"""
    id_historial: int
    fecha_inicio: str
    fecha_fin: str
    rutina: str
    objetivo: Optional[str] = None
    duracion_dias: int
    dias_entrenados: int
    sesiones_completadas: int
    porcentaje_cumplimiento: float
    estado: str
    entrenador: Optional[str] = None
    peso_inicial: Optional[float] = None
    peso_final: Optional[float] = None


class AlertaProgreso(BaseModel):
    """Alerta de progreso o estancamiento"""
    id_alerta: int
    tipo_alerta: str  # "estancamiento", "rutina_expira", "sin_rutina", "record_personal"
    titulo: str
    mensaje: str
    recomendacion: Optional[str] = None
    fecha_generacion: str
    prioridad: str  # "alta", "media", "baja"
    estado: str = "pendiente"  # "pendiente", "vista", "atendida"
    nombre_ejercicio: Optional[str] = None
    peso_actual: Optional[float] = None
    peso_sugerido: Optional[float] = None
    sesiones_sin_progreso: Optional[int] = None


class ObjetivoProgreso(BaseModel):
    """Objetivo de progreso del cliente basado en rutinas"""
    id_objetivo: int
    tipo_objetivo: str  # "peso", "resistencia", "consistencia", "rutina"
    titulo: str
    descripcion: Optional[str] = None
    valor_inicial: Optional[float] = None
    valor_objetivo: float
    valor_actual: Optional[float] = None
    unidad: str
    porcentaje_completado: float
    fecha_inicio: str
    fecha_limite: str
    fecha_alcanzado: Optional[str] = None
    estado: str  # "pendiente", "en_progreso", "alcanzado", "vencido"


class EjercicioConProgreso(BaseModel):
    """Ejercicio con métricas de progreso"""
    id_ejercicio: int
    nombre: str
    grupo_muscular: str
    total_sesiones: int
    peso_inicial: Optional[float] = None
    peso_actual: Optional[float] = None
    peso_maximo: Optional[float] = None
    progreso_total: Optional[float] = None
    porcentaje_mejora: Optional[float] = None
    ultima_sesion: Optional[str] = None


class ProgresoEjercicioDetalle(BaseModel):
    """Detalle de progreso de un ejercicio específico"""
    id_progreso: int
    fecha_sesion: str
    numero_sesion: int
    peso_kg: Optional[float] = None
    series_completadas: int
    repeticiones_completadas: int
    rpe: Optional[int] = None
    calidad_tecnica: Optional[str] = None
    peso_anterior: Optional[float] = None
    diferencia_peso: Optional[float] = None
    porcentaje_mejora: Optional[float] = None
    es_record_personal: bool = False
    notas: Optional[str] = None


class RegistrarProgresoRequest(BaseModel):
    """Request para registrar progreso"""
    id_historial: int
    id_ejercicio: int
    fecha_sesion: str
    dia_rutina: Optional[str] = None
    peso_kg: Optional[float] = None
    series_completadas: int
    repeticiones_completadas: int
    tiempo_descanso_segundos: Optional [ int ] = None
    rpe: Optional[int] = None
    calidad_tecnica: Optional[str] = None
    estado_animo: Optional[str] = None
    notas: Optional[str] = None
    dolor_molestias: Optional[str] = None


# ============================================================
# 🔹 ENDPOINTS - DASHBOARD
# ============================================================

@router.get("/dashboard/cliente/{id_cliente}", response_model=DashboardProgreso)
def obtener_dashboard_completo(id_cliente: int):
    """
    ✅ Dashboard completo con todas las métricas del cliente
    """
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # 1. Verificar que el cliente existe
        cur.execute("""
            SELECT id_usuario, nombre, apellido
            FROM usuarios
            WHERE id_usuario = %s AND rol = 'alumno'
        """, (id_cliente,))
        cliente = cur.fetchone()

        if not cliente:
            raise HTTPException(404, f"Cliente {id_cliente} no encontrado")

        # 2. Estadísticas generales
        cur.execute("""
            SELECT 
                COUNT(DISTINCT DATE(fecha_sesion)) AS dias_entrenados,
                COUNT(*) AS total_sesiones,
                MIN(fecha_sesion) AS primera_sesion
            FROM progreso_ejercicios
            WHERE id_cliente = %s
        """, (id_cliente,))
        stats = cur.fetchone()

        # 3. Rutinas activas
        cur.execute("""
            SELECT COUNT(*) AS rutinas_activas
            FROM historial_rutinas
            WHERE id_cliente = %s
              AND estado = 'activa'
              AND fecha_fin > NOW()
        """, (id_cliente,))
        rutinas = cur.fetchone()

        # 4. Última rutina y entrenamiento
        cur.execute("""
            SELECT hr.nombre_rutina, pe.fecha_sesion
            FROM historial_rutinas hr
            LEFT JOIN progreso_ejercicios pe ON pe.id_cliente = hr.id_cliente
            WHERE hr.id_cliente = %s
            ORDER BY pe.fecha_sesion DESC
            LIMIT 1
        """, (id_cliente,))
        ultima = cur.fetchone()

        # 5. Alertas pendientes
        cur.execute("""
            SELECT COUNT(*) AS pendientes
            FROM alertas_progresion
            WHERE id_cliente = %s AND estado = 'pendiente'
        """, (id_cliente,))
        alertas = cur.fetchone()

        # 6. Records este mes
        cur.execute("""
            SELECT COUNT(*) AS records
            FROM progreso_ejercicios
            WHERE id_cliente = %s
              AND es_record_personal = TRUE
              AND MONTH(fecha_sesion) = MONTH(NOW())
              AND YEAR(fecha_sesion) = YEAR(NOW())
        """, (id_cliente,))
        records = cur.fetchone()

        # 7. Objetivos activos
        cur.execute("""
            SELECT COUNT(*) AS activos
            FROM objetivos_cliente
            WHERE id_cliente = %s
              AND estado IN ('pendiente', 'en_progreso')
        """, (id_cliente,))
        objetivos = cur.fetchone()

        # 8. Cumplimiento promedio
        cur.execute("""
            SELECT AVG(porcentaje_cumplimiento) AS promedio
            FROM historial_rutinas
            WHERE id_cliente = %s
        """, (id_cliente,))
        cumplimiento = cur.fetchone()

        # 9. Calcular días entrenando
        dias_entrenando = 0
        if stats["primera_sesion"]:
            dias_entrenando = (datetime.now() - stats["primera_sesion"]).days

        # 10. Progreso general (basado en cumplimiento)
        progreso_general = cumplimiento["promedio"] or 0.0

        return DashboardProgreso(
            id_cliente=id_cliente,
            nombre_cliente=f"{cliente['nombre']} {cliente['apellido']}",
            dias_entrenando=dias_entrenando,
            sesiones_completadas=stats["total_sesiones"] or 0,
            rutinas_activas=rutinas["rutinas_activas"] or 0,
            ultima_rutina=ultima["nombre_rutina"] if ultima else None,
            ultimo_entrenamiento=ultima["fecha_sesion"].isoformat() if ultima and ultima["fecha_sesion"] else None,
            progreso_general=min(progreso_general, 100.0),
            resumen={
                "total_rutinas": rutinas["rutinas_activas"] or 0,
                "rutinas_completadas": 0,  # Se puede calcular si es necesario
                "total_sesiones": stats["total_sesiones"] or 0,
                "cumplimiento_promedio": progreso_general,
                "ultima_sesion": ultima["fecha_sesion"].isoformat() if ultima and ultima["fecha_sesion"] else None
            },
            alertas_pendientes=alertas["pendientes"] or 0,
            records_este_mes=records["records"] or 0,
            objetivos_activos=objetivos["activos"] or 0
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener dashboard: {str(e)}")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


# ============================================================
# 🔹 ENDPOINTS - HISTORIAL
# ============================================================

@router.get("/historial/cliente/{id_cliente}", response_model=List[HistorialProgreso])
def obtener_historial_completo(id_cliente: int, limit: int = 30, offset: int = 0):
    """
    ✅ Historial completo de rutinas con métricas de cumplimiento
    """
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # Verificar cliente
        cur.execute("""
            SELECT id_usuario FROM usuarios
            WHERE id_usuario = %s AND rol = 'alumno'
        """, (id_cliente,))
        if not cur.fetchone():
            raise HTTPException(404, f"Cliente {id_cliente} no encontrado")

        # Obtener historial con métricas calculadas
        cur.execute("""
            SELECT 
                hr.id_historial,
                hr.nombre_rutina,
                hr.objetivo,
                hr.fecha_inicio,
                hr.fecha_fin,
                hr.estado,
                DATEDIFF(hr.fecha_fin, hr.fecha_inicio) AS duracion_dias,
                COUNT(DISTINCT DATE(pe.fecha_sesion)) AS dias_entrenados,
                COUNT(pe.id_progreso) AS sesiones_completadas,
                CONCAT(u.nombre, ' ', u.apellido) AS entrenador,
                MIN(pe.peso_kg) AS peso_inicial,
                MAX(pe.peso_kg) AS peso_final
            FROM historial_rutinas hr
            LEFT JOIN usuarios u ON hr.id_entrenador = u.id_usuario
            LEFT JOIN progreso_ejercicios pe ON pe.id_historial = hr.id_historial
            WHERE hr.id_cliente = %s
            GROUP BY hr.id_historial
            ORDER BY hr.fecha_inicio DESC
            LIMIT %s OFFSET %s
        """, (id_cliente, limit, offset))

        data = cur.fetchall()
        historial = []

        for row in data:
            duracion = row["duracion_dias"] or 1
            dias_entrenados = row["dias_entrenados"] or 0
            porcentaje = (dias_entrenados / duracion * 100) if duracion > 0 else 0

            historial.append(HistorialProgreso(
                id_historial=row["id_historial"],
                fecha_inicio=row["fecha_inicio"].isoformat(),
                fecha_fin=row["fecha_fin"].isoformat(),
                rutina=row["nombre_rutina"],
                objetivo=row["objetivo"],
                duracion_dias=duracion,
                dias_entrenados=dias_entrenados,
                sesiones_completadas=row["sesiones_completadas"] or 0,
                porcentaje_cumplimiento=min(porcentaje, 100.0),
                estado=row["estado"],
                entrenador=row["entrenador"],
                peso_inicial=row["peso_inicial"],
                peso_final=row["peso_final"]
            ))

        return historial

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en historial: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener historial: {str(e)}")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


# ============================================================
# 🔹 ENDPOINTS - EJERCICIOS CON PROGRESO
# ============================================================

# ============================================================
# 🔹 ENDPOINTS - EJERCICIOS CON PROGRESO (FIX DIVISION BY ZERO)
# ============================================================

@router.get("/historial/{id_historial}/ejercicios", response_model=List[EjercicioConProgreso])
def obtener_ejercicios_con_progreso(id_historial: int, id_cliente: int):
    """
    ✅ Obtiene ejercicios de una rutina con métricas de progreso (con protección anti división entre cero)
    """
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        cur.execute("""
            SELECT id_historial 
            FROM historial_rutinas
            WHERE id_historial = %s AND id_cliente = %s
        """, (id_historial, id_cliente))

        if not cur.fetchone():
            raise HTTPException(404, "Historial no encontrado")

        cur.execute("""
            SELECT 
                hre.id_ejercicio,
                e.nombre,
                e.grupo_muscular,
                COUNT(DISTINCT pe.id_progreso) AS total_sesiones,
                MIN(pe.peso_kg) AS peso_inicial,
                MAX(pe.peso_kg) AS peso_maximo,
                (SELECT peso_kg 
                 FROM progreso_ejercicios 
                 WHERE id_ejercicio = hre.id_ejercicio AND id_cliente = %s
                 ORDER BY fecha_sesion DESC LIMIT 1) AS peso_actual,
                MAX(pe.fecha_sesion) AS ultima_sesion
            FROM historial_rutina_ejercicios hre
            INNER JOIN ejercicios e ON e.id_ejercicio = hre.id_ejercicio
            LEFT JOIN progreso_ejercicios pe ON pe.id_ejercicio = hre.id_ejercicio 
                AND pe.id_historial = %s
            WHERE hre.id_historial = %s
            GROUP BY hre.id_ejercicio, e.nombre, e.grupo_muscular
        """, (id_cliente, id_historial, id_historial))

        ejercicios = []
        for row in cur.fetchall():

            peso_inicial = row["peso_inicial"]
            peso_actual = row["peso_actual"]

            # --- Protecciones ----
            if not peso_inicial or peso_inicial <= 0:
                progreso_total = None
                porcentaje_mejora = None
            else:
                progreso_total = (peso_actual - peso_inicial) if peso_actual else None
                porcentaje_mejora = ((progreso_total / peso_inicial) * 100) if progreso_total else None

            ejercicios.append(EjercicioConProgreso(
                id_ejercicio=row["id_ejercicio"],
                nombre=row["nombre"],
                grupo_muscular=row["grupo_muscular"],
                total_sesiones=row["total_sesiones"] or 0,
                peso_inicial=peso_inicial,
                peso_actual=peso_actual,
                peso_maximo=row["peso_maximo"],
                progreso_total=progreso_total,
                porcentaje_mejora=porcentaje_mejora,
                ultima_sesion=row["ultima_sesion"].isoformat() if row["ultima_sesion"] else None
            ))

        return ejercicios

    except Exception as e:
        print("❌ Error en ejercicios con progreso:", e)
        raise HTTPException(500, f"Error: {str(e)}")
    finally:
        if cn and cn.is_connected():
            cur.close()
            cn.close()


@router.get("/ejercicio/{id_ejercicio}/cliente/{id_cliente}/progreso",
            response_model=List[ProgresoEjercicioDetalle])
def obtener_progreso_ejercicio(id_ejercicio: int, id_cliente: int, limite: int = 50):

    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        cur.execute("""
            SELECT 
                pe.id_progreso,
                pe.fecha_sesion,
                pe.numero_sesion,
                pe.peso_kg,
                pe.series_completadas,
                pe.repeticiones_completadas,
                pe.rpe,
                pe.calidad_tecnica,
                pe.es_record_personal,
                pe.notas,
                LAG(pe.peso_kg) OVER (ORDER BY pe.fecha_sesion) AS peso_anterior
            FROM progreso_ejercicios pe
            WHERE pe.id_ejercicio = %s AND pe.id_cliente = %s
            ORDER BY pe.fecha_sesion DESC
            LIMIT %s
        """, (id_ejercicio, id_cliente, limite))

        progreso = []
        for row in cur.fetchall():

            actual = row["peso_kg"]
            anterior = row["peso_anterior"]

            if not anterior or anterior <= 0:
                diferencia = None
                porcentaje = None
            else:
                diferencia = actual - anterior
                porcentaje = (diferencia / anterior) * 100

            progreso.append(ProgresoEjercicioDetalle(
                id_progreso=row["id_progreso"],
                fecha_sesion=row["fecha_sesion"].isoformat(),
                numero_sesion=row["numero_sesion"],
                peso_kg=actual,
                series_completadas=row["series_completadas"],
                repeticiones_completadas=row["repeticiones_completadas"],
                rpe=row["rpe"],
                calidad_tecnica=row["calidad_tecnica"],
                peso_anterior=anterior,
                diferencia_peso=diferencia,
                porcentaje_mejora=porcentaje,
                es_record_personal=row["es_record_personal"] or False,
                notas=row["notas"]
            ))

        return progreso

    except Exception as e:
        print("❌ Error en progreso ejercicio:", e)
        raise HTTPException(500, f"Error: {str(e)}")
    finally:
        if cn and cn.is_connected():
            cur.close()
            cn.close()


# ============================================================
# 🔹 ENDPOINTS - ALERTAS
# ============================================================

@router.get("/alertas/cliente/{id_cliente}", response_model=List[AlertaProgreso])
def obtener_alertas_cliente(id_cliente: int):
    """
    ✅ Obtiene todas las alertas del cliente
    """
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # Verificar cliente
        cur.execute("""
            SELECT id_usuario FROM usuarios
            WHERE id_usuario = %s AND rol = 'alumno'
        """, (id_cliente,))
        if not cur.fetchone():
            raise HTTPException(404, "Cliente no encontrado")

        # Obtener alertas de la base de datos
        cur.execute("""
            SELECT 
                id_alerta,
                tipo_alerta,
                prioridad,
                titulo,
                mensaje,
                recomendacion,
                nombre_ejercicio,
                peso_actual,
                peso_sugerido,
                sesiones_sin_progreso,
                fecha_generacion,
                estado
            FROM alertas_progresion
            WHERE id_cliente = %s
            ORDER BY 
                CASE prioridad
                    WHEN 'alta' THEN 1
                    WHEN 'media' THEN 2
                    WHEN 'baja' THEN 3
                END,
                fecha_generacion DESC
        """, (id_cliente,))

        alertas_db = cur.fetchall()
        alertas = []

        for a in alertas_db:
            alertas.append(AlertaProgreso(
                id_alerta=a["id_alerta"],
                tipo_alerta=a["tipo_alerta"],
                titulo=a["titulo"],
                mensaje=a["mensaje"],
                recomendacion=a["recomendacion"],
                fecha_generacion=a["fecha_generacion"].isoformat(),
                prioridad=a["prioridad"],
                estado=a["estado"],
                nombre_ejercicio=a["nombre_ejercicio"],
                peso_actual=a["peso_actual"],
                peso_sugerido=a["peso_sugerido"],
                sesiones_sin_progreso=a["sesiones_sin_progreso"]
            ))

        # Agregar alertas dinámicas (rutinas por expirar)
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
                id_alerta=999000 + len(alertas),  # ID temporal para alertas dinámicas
                tipo_alerta="rutina_expira",
                titulo="⚠️ Rutina próxima a expirar",
                mensaje=f"La rutina '{r['nombre_rutina']}' expira en {r['dias_restantes']} días",
                recomendacion="Considera crear una nueva rutina o extender la actual",
                fecha_generacion=datetime.now().isoformat(),
                prioridad="alta",
                estado="pendiente"
            ))

        # Alerta si no tiene rutinas activas
        cur.execute("""
            SELECT COUNT(*) AS activas
            FROM historial_rutinas
            WHERE id_cliente = %s
              AND estado = 'activa'
              AND fecha_fin > NOW()
        """, (id_cliente,))

        if cur.fetchone()["activas"] == 0:
            alertas.append(AlertaProgreso(
                id_alerta=999999,
                tipo_alerta="sin_rutina",
                titulo="📋 Sin rutina activa",
                mensaje="No tienes ninguna rutina activa en este momento",
                recomendacion="Solicita a tu entrenador que te asigne una nueva rutina",
                fecha_generacion=datetime.now().isoformat(),
                prioridad="alta",
                estado="pendiente"
            ))

        return alertas

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en alertas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener alertas: {str(e)}")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


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

        # 1. Detectar ejercicios con estancamiento (mismo peso por 3+ sesiones)
        cur.execute("""
            SELECT 
                pe.id_ejercicio,
                e.nombre,
                pe.peso_kg AS peso_actual,
                COUNT(*) AS sesiones_mismo_peso,
                LAG(pe.peso_kg, 3) OVER (
                    PARTITION BY pe.id_ejercicio 
                    ORDER BY pe.fecha_sesion
                ) AS peso_hace_3_sesiones
            FROM progreso_ejercicios pe
            INNER JOIN ejercicios e ON e.id_ejercicio = pe.id_ejercicio
            WHERE pe.id_cliente = %s
              AND pe.fecha_sesion >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY pe.id_ejercicio, e.nombre, pe.peso_kg
            HAVING sesiones_mismo_peso >= 3
              AND peso_actual = peso_hace_3_sesiones
        """, (id_cliente,))

        for row in cur.fetchall():
            # Verificar si ya existe una alerta similar
            cur.execute("""
                SELECT id_alerta FROM alertas_progresion
                WHERE id_cliente = %s
                  AND id_ejercicio = %s
                  AND tipo_alerta = 'estancamiento'
                  AND estado = 'pendiente'
                  AND DATE(fecha_generacion) >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """, (id_cliente, row["id_ejercicio"]))

            if not cur.fetchone():  # Solo crear si no existe
                peso_sugerido = row["peso_actual"] * 1.05  # Sugerir 5% más

                cur.execute("""
                    INSERT INTO alertas_progresion (
                        id_cliente, id_ejercicio, tipo_alerta, prioridad,
                        titulo, mensaje, recomendacion,
                        nombre_ejercicio, peso_actual, peso_sugerido,
                        sesiones_sin_progreso, estado
                    ) VALUES (
                        %s, %s, 'estancamiento', 'media',
                        'Estancamiento detectado',
                        %s,
                        %s,
                        %s, %s, %s, %s, 'pendiente'
                    )
                """, (
                    id_cliente,
                    row["id_ejercicio"],
                    f"No has progresado en {row['nombre']} en las últimas {row['sesiones_mismo_peso']} sesiones",
                    f"Intenta aumentar el peso a {peso_sugerido:.1f}kg o aumentar las repeticiones",
                    row["nombre"],
                    row["peso_actual"],
                    peso_sugerido,
                    row["sesiones_mismo_peso"]
                ))

                alertas_generadas += 1

        # 2. Detectar records personales recientes (últimos 7 días)
        cur.execute("""
            SELECT 
                pe.id_ejercicio,
                e.nombre,
                pe.peso_kg
            FROM progreso_ejercicios pe
            INNER JOIN ejercicios e ON e.id_ejercicio = pe.id_ejercicio
            WHERE pe.id_cliente = %s
              AND pe.es_record_personal = TRUE
              AND pe.fecha_sesion >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """, (id_cliente,))

        for row in cur.fetchall():
            cur.execute("""
                SELECT id_alerta FROM alertas_progresion
                WHERE id_cliente = %s
                  AND id_ejercicio = %s
                  AND tipo_alerta = 'record_personal'
                  AND DATE(fecha_generacion) >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """, (id_cliente, row["id_ejercicio"]))

            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO alertas_progresion (
                        id_cliente, id_ejercicio, tipo_alerta, prioridad,
                        titulo, mensaje, recomendacion,
                        nombre_ejercicio, peso_actual, estado
                    ) VALUES (
                        %s, %s, 'record_personal', 'baja',
                        '🏆 ¡Nuevo Record Personal!',
                        %s,
                        'Sigue así, estás haciendo un excelente progreso',
                        %s, %s, 'pendiente'
                    )
                """, (
                    id_cliente,
                    row["id_ejercicio"],
                    f"Has establecido un nuevo récord en {row['nombre']} con {row['peso_kg']}kg",
                    row["nombre"],
                    row["peso_kg"]
                ))

                alertas_generadas += 1

        cn.commit()

        return {
            "success": True,
            "alertas_generadas": alertas_generadas,
            "mensaje": f"Análisis completado. {alertas_generadas} nuevas alertas generadas."
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en análisis: {str(e)}")
        if cn:
            cn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al analizar progresión: {str(e)}")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


# ============================================================
# 🔹 ENDPOINTS - OBJETIVOS
# ============================================================

@router.get("/objetivos/cliente/{id_cliente}", response_model=List[ObjetivoProgreso])
def obtener_objetivos_cliente(id_cliente: int):
    """
    ✅ Obtiene todos los objetivos del cliente
    """
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # Verificar cliente
        cur.execute("""
            SELECT id_usuario FROM usuarios
            WHERE id_usuario = %s AND rol = 'alumno'
        """, (id_cliente,))
        if not cur.fetchone():
            raise HTTPException(404, "Cliente no encontrado")

        # Obtener objetivos de la base de datos
        cur.execute("""
            SELECT 
                oc.id_objetivo,
                oc.tipo_objetivo,
                oc.titulo,
                oc.descripcion,
                oc.valor_inicial,
                oc.valor_objetivo,
                oc.valor_actual,
                oc.unidad,
                oc.porcentaje_completado,
                oc.estado,
                oc.fecha_inicio,
                oc.fecha_limite,
                oc.fecha_alcanzado
            FROM objetivos_cliente oc
            WHERE oc.id_cliente = %s
            ORDER BY 
                CASE estado
                    WHEN 'en_progreso' THEN 1
                    WHEN 'pendiente' THEN 2
                    WHEN 'alcanzado' THEN 3
                    WHEN 'vencido' THEN 4
                END,
                oc.fecha_limite ASC
        """, (id_cliente,))

        objetivos_db = cur.fetchall()
        objetivos = []

        for obj in objetivos_db:
            # Actualizar estado si es necesario
            estado_actual = obj["estado"]
            if obj["fecha_limite"] and datetime.now().date() > obj["fecha_limite"] and estado_actual not in [
                'alcanzado']:
                estado_actual = "vencido"

            objetivos.append(ObjetivoProgreso(
                id_objetivo=obj["id_objetivo"],
                tipo_objetivo=obj["tipo_objetivo"],
                titulo=obj["titulo"],
                descripcion=obj["descripcion"],
                valor_inicial=obj["valor_inicial"],
                valor_objetivo=obj["valor_objetivo"],
                valor_actual=obj["valor_actual"],
                unidad=obj["unidad"],
                porcentaje_completado=obj["porcentaje_completado"] or 0.0,
                fecha_inicio=obj["fecha_inicio"].isoformat(),
                fecha_limite=obj["fecha_limite"].isoformat(),
                fecha_alcanzado=obj["fecha_alcanzado"].isoformat() if obj["fecha_alcanzado"] else None,
                estado=estado_actual
            ))

        # Agregar objetivos automáticos de rutinas activas
        cur.execute("""
            SELECT 
                hr.id_historial,
                hr.nombre_rutina,
                hr.fecha_inicio,
                hr.fecha_fin,
                hr.duracion_dias,
                DATEDIFF(NOW(), hr.fecha_inicio) AS dias_transcurridos
            FROM historial_rutinas hr
            WHERE hr.id_cliente = %s
              AND hr.estado = 'activa'
              AND hr.fecha_fin > NOW()
            ORDER BY hr.fecha_inicio DESC
        """, (id_cliente,))

        id_counter = 990000  # IDs temporales para objetivos automáticos
        for rutina in cur.fetchall():
            progreso = min((rutina['dias_transcurridos'] / rutina['duracion_dias']) * 100, 100) if rutina[
                                                                                                       'duracion_dias'] > 0 else 0

            objetivos.append(ObjetivoProgreso(
                id_objetivo=id_counter,
                tipo_objetivo="rutina",
                titulo=f"Completar: {rutina['nombre_rutina']}",
                descripcion=f"Objetivo automático de rutina activa",
                valor_inicial=0,
                valor_objetivo=100,
                valor_actual=progreso,
                unidad="%",
                porcentaje_completado=progreso,
                fecha_inicio=rutina["fecha_inicio"].isoformat(),
                fecha_limite=rutina["fecha_fin"].isoformat(),
                fecha_alcanzado=None,
                estado="en_progreso" if progreso < 100 else "alcanzado"
            ))
            id_counter += 1

        return objetivos

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en objetivos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener objetivos: {str(e)}")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


# ============================================================
# 🔹 ENDPOINTS - REGISTRO DE PROGRESO
# ============================================================

@router.post("/registrar")
def registrar_progreso(progreso: RegistrarProgresoRequest):
    """
    ✅ Registra el progreso de un ejercicio en una sesión
    """
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # Verificar que el historial existe
        cur.execute("""
            SELECT id_cliente FROM historial_rutinas
            WHERE id_historial = %s
        """, (progreso.id_historial,))

        historial = cur.fetchone()
        if not historial:
            raise HTTPException(404, "Historial de rutina no encontrado")

        id_cliente = historial["id_cliente"]

        # Obtener número de sesión
        cur.execute("""
            SELECT COALESCE(MAX(numero_sesion), 0) + 1 AS siguiente_sesion
            FROM progreso_ejercicios
            WHERE id_ejercicio = %s AND id_cliente = %s
        """, (progreso.id_ejercicio, id_cliente))

        numero_sesion = cur.fetchone()["siguiente_sesion"]

        # Obtener peso máximo histórico para detectar records
        cur.execute("""
            SELECT COALESCE(MAX(peso_kg), 0) AS peso_maximo
            FROM progreso_ejercicios
            WHERE id_ejercicio = %s AND id_cliente = %s
        """, (progreso.id_ejercicio, id_cliente))

        peso_maximo = cur.fetchone()["peso_maximo"]
        es_record = False

        if progreso.peso_kg and progreso.peso_kg > peso_maximo:
            es_record = True

        # Insertar progreso
        cur.execute("""
            INSERT INTO progreso_ejercicios (
                id_historial, id_ejercicio, id_cliente,
                fecha_sesion, numero_sesion, dia_rutina,
                peso_kg, series_completadas, repeticiones_completadas,
                tiempo_descanso_segundos, rpe, calidad_tecnica,
                estado_animo, notas, dolor_molestias, es_record_personal
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            progreso.id_historial,
            progreso.id_ejercicio,
            id_cliente,
            progreso.fecha_sesion,
            numero_sesion,
            progreso.dia_rutina,
            progreso.peso_kg,
            progreso.series_completadas,
            progreso.repeticiones_completadas,
            progreso.tiempo_descanso_segundos,
            progreso.rpe,
            progreso.calidad_tecnica,
            progreso.estado_animo,
            progreso.notas,
            progreso.dolor_molestias,
            es_record
        ))

        id_progreso = cur.lastrowid
        cn.commit()

        return {
            "success": True,
            "id_progreso": id_progreso,
            "mensaje": "Progreso registrado exitosamente",
            "record_personal": es_record
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al registrar progreso: {str(e)}")
        if cn:
            cn.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if cn and cn.is_connected():
            try:
                cur.close()
                cn.close()
            except:
                pass


# ============================================================
# 🔹 ENDPOINTS AUXILIARES
# ============================================================

@router.post("/progresion/historial/crear")
def crear_historial(id_rutina: int, id_cliente: int):
    """
    Crea un nuevo historial de rutina y copia sus ejercicios
    en la tabla historial_rutina_ejercicios.
    """
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # 1) CREAR REGISTRO EN historial_rutinas
        cur.execute("""
            INSERT INTO historial_rutinas(
                id_cliente, id_rutina, nombre_rutina, objetivo,
                fecha_inicio, fecha_fin, estado, duracion_dias
            )
            SELECT 
                %s,
                id_rutina,
                nombre,
                objetivo,
                NOW(),
                DATE_ADD(NOW(), INTERVAL duracion_meses MONTH),
                'activa',
                duracion_meses * 30
            FROM rutinas
            WHERE id_rutina = %s
        """, (id_cliente, id_rutina))

        id_historial = cur.lastrowid

        # 2) INSERTAR EJERCICIOS EN historial_rutina_ejercicios
        cur.execute("""
            INSERT INTO `historial_rutina_ejercicios` (
                `id_historial`,
                `id_ejercicio`,
                `series`,
                `repeticiones`,
                `descanso_segundos`,
                `nombre_ejercicio`,
                `peso_inicial`
            )
            SELECT
                %s,
                re.`id_ejercicio`,
                re.`series`,
                re.`repeticiones`,
                re.`descanso_segundos`,
                e.`nombre`,
                0
            FROM `rutina_ejercicios` re
            INNER JOIN `ejercicios` e 
                ON e.`id_ejercicio` = re.`id_ejercicio`
            WHERE re.`id_rutina` = %s
        """, (id_historial, id_rutina))

        cn.commit()

        return {
            "success": True,
            "mensaje": "Historial creado correctamente",
            "id_historial": id_historial
        }

    except Exception as e:
        if cn:
            cn.rollback()
        print("❌ Error al crear historial:", e)
        raise HTTPException(status_code=500, detail=f"Error al crear historial: {str(e)}")

    finally:
        if cn and cn.is_connected():
            cur.close()
            cn.close()

@router.put("/alertas/{id_alerta}/atender")
def atender_alerta(id_alerta: int):
    """
    Marca una alerta como atendida
    """
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor()

        # Verificar que la alerta existe
        cur.execute("""
            SELECT id_alerta FROM alertas_progresion
            WHERE id_alerta = %s
        """, (id_alerta,))

        if not cur.fetchone():
            raise HTTPException(404, "Alerta no encontrada")

        # Actualizar estado
        cur.execute("""
            UPDATE alertas_progresion
            SET estado = 'atendida'
            WHERE id_alerta = %s
        """, (id_alerta,))

        cn.commit()

        return {"success": True, "mensaje": "Alerta atendida correctamente"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al atender alerta: {str(e)}")
        raise HTTPException(500, f"Error al atender alerta: {str(e)}")
    finally:
        if cn and cn.is_connected():
            cur.close()
            cn.close()

@router.put("/alertas/{id_alerta}/actualizar-estado")
def actualizar_estado_alerta(id_alerta: int, datos: dict):
    """
    Actualiza el estado de una alerta (pendiente, vista, atendida)
    y puede guardar la acción realizada por el entrenador.
    """
    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # Verificar que la alerta existe
        cur.execute("""
            SELECT id_alerta FROM alertas_progresion
            WHERE id_alerta = %s
        """, (id_alerta,))
        alerta = cur.fetchone()

        if not alerta:
            raise HTTPException(404, "Alerta no encontrada")

        # Obtener acción
        accion = datos.get("accion", "").strip()

        # Determinar nuevo estado
        nuevo_estado = "atendida" if accion else "vista"

        # Actualizar alerta
        cur.execute("""
            UPDATE alertas_progresion
            SET estado = %s,
                accion_realizada = %s
            WHERE id_alerta = %s
        """, (nuevo_estado, accion, id_alerta))

        cn.commit()

        return {
            "success": True,
            "mensaje": f"Alerta actualizada correctamente: {nuevo_estado}",
            "estado": nuevo_estado
        }

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Error al actualizar alerta:", e)
        raise HTTPException(500, f"Error al actualizar alerta: {str(e)}")
    finally:
        if cn and cn.is_connected():
            cur.close()
            cn.close()


@router.post("/ejercicio/{id_ejercicio}/registrar-sesion")
def registrar_sesion(
    id_ejercicio: int,
    id_cliente: int = Query(...),
    id_historial: int = Query(...),   # 👈 AGREGAR
    peso_kg: float = Query(...),
    series: int = Query(...),
    repeticiones: int = Query(...),
    rpe: int = Query(None),
    calidad_tecnica: str = Query(None),
    notas: str = Query(None),
    db: Session = Depends(get_db)
):
    # Aquí ya tienes id_historial no nulo

    """
    Registra una sesión individual dentro del progreso de un ejercicio.
    """

    cn = None
    try:
        cn = get_connection()
        cur = cn.cursor(dictionary=True)

        # Obtener número de sesión
        cur.execute("""
            SELECT COALESCE(MAX(numero_sesion), 0) + 1 AS siguiente
            FROM progreso_ejercicios
            WHERE id_cliente = %s AND id_ejercicio = %s
        """, (id_cliente, id_ejercicio))

        numero_sesion = cur.fetchone()["siguiente"]

        # Insertar progreso
        cur.execute("""
            INSERT INTO progreso_ejercicios (
                id_historial,
                id_ejercicio,
                id_cliente,
                fecha_sesion,
                numero_sesion,
                peso_kg,
                series_completadas,
                repeticiones_completadas,
                rpe,
                calidad_tecnica,
                notas
            ) VALUES (
                %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            id_historial,
            id_ejercicio,
            id_cliente,
            numero_sesion,
            peso_kg,
            series,
            repeticiones,
            rpe,
            calidad_tecnica,
            notas
        ))

        cn.commit()

        return {"success": True, "mensaje": "Sesión registrada correctamente"}

    except Exception as e:
        print("❌ Error al registrar sesión:", e)
        cn.rollback()
        raise HTTPException(500, f"Error al registrar sesión: {str(e)}")

    finally:
        if cn and cn.is_connected():
            cur.close()
            cn.close()

def generar_alertas_progresion_periodica(db: Session):
    """
    Genera alertas automáticas cuando un cliente lleva 14–28 días sin aumentar peso
    o sin registrar sesión en un ejercicio.
    """

    query = text("""
        SELECT 
            he.id_cliente,
            he.id_ejercicio,
            e.nombre AS nombre_ejercicio,
            MAX(he.fecha_sesion) AS ultima_sesion,
            MAX(he.peso_kg) AS ultimo_peso
        FROM historial_ejercicio he
        INNER JOIN ejercicios e ON e.id_ejercicio = he.id_ejercicio
        GROUP BY he.id_cliente, he.id_ejercicio;
    """)

    registros = db.execute(query).fetchall()

    hoy = datetime.now()

    for r in registros:
        id_cliente = r.id_cliente
        id_ejercicio = r.id_ejercicio
        nombre_ejercicio = r.nombre_ejercicio
        ultima_sesion = r.ultima_sesion
        ultimo_peso = r.ultimo_peso

        if not ultima_sesion:
            continue

        dias = (hoy - ultima_sesion).days

        # Solo generar alerta si han pasado entre 14 y 28 días
        if 14 <= dias <= 28:

            # Evitar duplicados
            existe = db.execute(text("""
                SELECT id_alerta 
                FROM alertas_progresion 
                WHERE id_cliente = :c AND id_ejercicio = :e
                AND tipo_alerta = 'progresion_retrasada'
                AND estado = 'pendiente'
            """), {
                "c": id_cliente,
                "e": id_ejercicio
            }).fetchone()

            if existe:
                continue

            # Crear alerta
            db.execute(text("""
                INSERT INTO alertas_progresion (
                    id_cliente, id_ejercicio,
                    tipo_alerta, prioridad, titulo, mensaje,
                    fecha_creacion, estado
                ) VALUES (
                    :c, :e,
                    'progresion_retrasada', 'media',
                    :titulo, :mensaje,
                    NOW(), 'pendiente'
                )
            """), {
                "c": id_cliente,
                "e": id_ejercicio,
                "titulo": f"Tiempo de subir peso en {nombre_ejercicio}",
                "mensaje": f"Han pasado {dias} días desde tu última progresión en {nombre_ejercicio}. "
                           f"Considera aumentar ligeramente el peso.",
            })

    db.commit()

@router.post("/alertas/generar-periodicas")
def alertas_periodicas(db: Session = Depends(get_db)):
    generar_alertas_progresion_periodica(db)
    return {"status": "ok", "mensaje": "Alertas generadas"}


@router.post("/alertas/generar-automatico/{id_cliente}")
def generar_alertas_auto(id_cliente: int, db: Session = Depends(get_db)):
    """
    Genera alertas cada 2-4 semanas basado en el progreso real del cliente.
    """

    # 💾 1. Obtener ejercicios con progreso
    query = text("""
        SELECT 
            he.id_ejercicio,
            e.nombre,
            MAX(he.fecha_sesion) AS ultima_sesion,
            MAX(he.peso_kg) AS peso_actual,
            MIN(he.peso_kg) AS peso_inicial
        FROM historial_ejercicios he
        INNER JOIN ejercicios e ON he.id_ejercicio = e.id_ejercicio
        WHERE he.id_cliente = :cliente
        GROUP BY he.id_ejercicio
    """)

    registros = db.execute(query, {"cliente": id_cliente}).fetchall()

    nuevas_alertas = 0

    for r in registros:
        id_ejercicio = r[0]
        nombre = r[1]
        ultima = r[2]
        peso_actual = r[3]
        peso_inicial = r[4]

        if not ultima:
            continue

        # 🧮 Calcular días desde última sesión
        ultima_dt = datetime.strptime(str(ultima), "%Y-%m-%d %H:%M:%S")
        dias = (datetime.now() - ultima_dt).days

        if dias < 14:
            continue  # No ha pasado el periodo mínimo

        # Si está entre 14-27 días → prioridad media
        if 14 <= dias <= 27:
            prioridad = "media"
            mensaje = (
                f"Han pasado {dias} días desde tu última sesión del ejercicio '{nombre}'. "
                "Considera aumentar ligeramente el peso si te sientes capaz."
            )
        else:
            prioridad = "alta"
            mensaje = (
                f"Hace más de {dias} días que no entrenas '{nombre}'. "
                "Es importante retomar o ajustar la carga."
            )

        # Si el peso lleva igual mucho tiempo → estancamiento
        if peso_actual == peso_inicial and dias >= 21:
            prioridad = "alta"
            mensaje = (
                f"No has aumentado peso en '{nombre}' desde hace más de {dias} días. "
                "Probable estancamiento detectado."
            )

        # 📌 Guardar alerta
        db.execute(text("""
            INSERT INTO alertas_progresion
            (id_cliente, tipo_alerta, prioridad, titulo, mensaje, id_ejercicio)
            VALUES (:c, 'progresion', :p, :t, :m, :e)
        """), {
            "c": id_cliente,
            "p": prioridad,
            "t": f"Progresión para {nombre}",
            "m": mensaje,
            "e": id_ejercicio
        })

        nuevas_alertas += 1

    db.commit()

    return {"alertas_generadas": nuevas_alertas}
