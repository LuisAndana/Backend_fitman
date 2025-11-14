# routers/progresion.py - Sistema de Progresión e Histórico

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum

from utils.dependencies import get_db

router = APIRouter(prefix="/api/progresion", tags=["Progresión"])


# ============================================================
# ENUMS
# ============================================================

class TipoAlerta(str, Enum):
    aumentar_peso = "aumentar_peso"
    aumentar_reps = "aumentar_reps"
    reducir_descanso = "reducir_descanso"
    cambiar_ejercicio = "cambiar_ejercicio"
    meseta_detectada = "meseta_detectada"
    regresion_detectada = "regresion_detectada"
    objetivo_alcanzado = "objetivo_alcanzado"
    record_personal = "record_personal"


class PrioridadAlerta(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"
    critica = "critica"


class EstadoAlerta(str, Enum):
    pendiente = "pendiente"
    vista = "vista"
    atendida = "atendida"
    descartada = "descartada"


class CalidadTecnica(str, Enum):
    excelente = "excelente"
    buena = "buena"
    regular = "regular"
    mala = "mala"


class EstadoAnimo(str, Enum):
    excelente = "excelente"
    bueno = "bueno"
    regular = "regular"
    malo = "malo"


# ============================================================
# SCHEMAS
# ============================================================

class RegistrarProgresoRequest(BaseModel):
    id_historial: int
    id_ejercicio: int
    fecha_sesion: datetime
    dia_rutina: Optional[str] = None
    peso_kg: Optional[float] = None
    series_completadas: int
    repeticiones_completadas: int
    tiempo_descanso_segundos: Optional[int] = None
    rpe: Optional[int] = Field(None, ge=1, le=10, description="Rate of Perceived Exertion (1-10)")
    calidad_tecnica: Optional[CalidadTecnica] = CalidadTecnica.buena
    estado_animo: Optional[EstadoAnimo] = None
    notas: Optional[str] = None
    dolor_molestias: Optional[str] = None


class ProgresoEjercicio(BaseModel):
    id_progreso: int
    fecha_sesion: datetime
    numero_sesion: int
    peso_kg: Optional[float]
    series_completadas: int
    repeticiones_completadas: int
    rpe: Optional[int]
    calidad_tecnica: str
    peso_anterior: Optional[float]
    diferencia_peso: Optional[float]
    porcentaje_mejora: Optional[float]
    es_record_personal: bool
    notas: Optional[str]


class AlertaProgresion(BaseModel):
    id_alerta: int
    tipo_alerta: str
    prioridad: str
    titulo: str
    mensaje: str
    recomendacion: Optional[str]
    nombre_ejercicio: Optional[str]
    peso_actual: Optional[float]
    peso_sugerido: Optional[float]
    sesiones_sin_progreso: Optional[int]
    fecha_generacion: datetime
    estado: str


class EstadisticasProgreso(BaseModel):
    total_sesiones: int
    peso_inicial: Optional[float]
    peso_actual: Optional[float]
    peso_maximo: Optional[float]
    progreso_total: Optional[float]
    porcentaje_mejora: Optional[float]
    rpe_promedio: Optional[float]
    records_personales: int
    primera_sesion: Optional[datetime]
    ultima_sesion: Optional[datetime]
    dias_entrenando: int


class HistorialRutina(BaseModel):
    id_historial: int
    nombre_rutina: str
    fecha_inicio: datetime
    fecha_fin: datetime
    estado: str
    duracion_dias: int
    dias_entrenados: int
    sesiones_completadas: int
    porcentaje_cumplimiento: float
    peso_inicial: Optional[float]
    peso_final: Optional[float]
    objetivo: Optional[str]


class CrearObjetivoRequest(BaseModel):
    id_cliente: int
    id_ejercicio: Optional[int] = None
    tipo_objetivo: str
    titulo: str
    descripcion: Optional[str] = None
    valor_inicial: Optional[float] = None
    valor_objetivo: float
    unidad: Optional[str] = "kg"
    fecha_limite: datetime


class ObjetivoCliente(BaseModel):
    id_objetivo: int
    titulo: str
    descripcion: Optional[str]
    tipo_objetivo: str
    valor_inicial: Optional[float]
    valor_objetivo: float
    valor_actual: Optional[float]
    unidad: str
    porcentaje_completado: float
    estado: str
    fecha_inicio: datetime
    fecha_limite: datetime
    fecha_alcanzado: Optional[datetime]


# ============================================================
# ENDPOINTS - REGISTRO DE PROGRESO
# ============================================================

@router.post("/registrar")
def registrar_progreso(
        progreso: RegistrarProgresoRequest,
        db: Session = Depends(get_db)
):
    """
    Registra el progreso de un ejercicio en una sesión de entrenamiento.
    Calcula automáticamente mejoras, records personales y genera alertas.
    """
    try:
        # Obtener ID del cliente desde el historial
        query_cliente = text("""
            SELECT id_cliente FROM historial_rutinas WHERE id_historial = :id_historial
        """)
        result = db.execute(query_cliente, {"id_historial": progreso.id_historial}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Historial de rutina no encontrado")

        id_cliente = result[0]

        # Llamar al procedimiento almacenado
        query = text("""
            CALL sp_registrar_progreso(
                :id_historial,
                :id_ejercicio,
                :id_cliente,
                :fecha_sesion,
                :peso_kg,
                :series,
                :repeticiones,
                :rpe,
                :notas
            )
        """)

        result = db.execute(query, {
            "id_historial": progreso.id_historial,
            "id_ejercicio": progreso.id_ejercicio,
            "id_cliente": id_cliente,
            "fecha_sesion": progreso.fecha_sesion,
            "peso_kg": progreso.peso_kg,
            "series": progreso.series_completadas,
            "repeticiones": progreso.repeticiones_completadas,
            "rpe": progreso.rpe,
            "notas": progreso.notas
        })

        db.commit()

        # Obtener el ID insertado
        id_progreso = result.fetchone()[0]

        return {
            "success": True,
            "id_progreso": id_progreso,
            "mensaje": "Progreso registrado exitosamente",
            "record_personal": False  # Se actualizará con lógica
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar progreso: {str(e)}")


@router.get("/ejercicio/{id_ejercicio}/cliente/{id_cliente}")
def obtener_progreso_ejercicio(
        id_ejercicio: int,
        id_cliente: int,
        limite: int = Query(50, le=200),
        db: Session = Depends(get_db)
) -> List[ProgresoEjercicio]:
    """
    Obtiene el historial de progreso de un ejercicio específico para un cliente.
    """
    try:
        query = text("""
            SELECT 
                id_progreso,
                fecha_sesion,
                numero_sesion,
                peso_kg,
                series_completadas,
                repeticiones_completadas,
                rpe,
                calidad_tecnica,
                peso_anterior,
                diferencia_peso,
                porcentaje_mejora,
                es_record_personal,
                notas
            FROM progreso_ejercicios
            WHERE id_ejercicio = :id_ejercicio 
              AND id_cliente = :id_cliente
            ORDER BY fecha_sesion DESC
            LIMIT :limite
        """)

        results = db.execute(query, {
            "id_ejercicio": id_ejercicio,
            "id_cliente": id_cliente,
            "limite": limite
        }).fetchall()

        progresos = []
        for row in results:
            progresos.append(ProgresoEjercicio(
                id_progreso=row[0],
                fecha_sesion=row[1],
                numero_sesion=row[2],
                peso_kg=row[3],
                series_completadas=row[4],
                repeticiones_completadas=row[5],
                rpe=row[6],
                calidad_tecnica=row[7] or "buena",
                peso_anterior=row[8],
                diferencia_peso=row[9],
                porcentaje_mejora=row[10],
                es_record_personal=bool(row[11]),
                notas=row[12]
            ))

        return progresos

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener progreso: {str(e)}")


@router.get("/ejercicio/{id_ejercicio}/cliente/{id_cliente}/estadisticas")
def obtener_estadisticas_ejercicio(
        id_ejercicio: int,
        id_cliente: int,
        db: Session = Depends(get_db)
) -> EstadisticasProgreso:
    """
    Obtiene estadísticas resumidas del progreso en un ejercicio.
    """
    try:
        query = text("""
            SELECT * FROM v_progreso_por_ejercicio
            WHERE id_cliente = :id_cliente 
              AND id_ejercicio = :id_ejercicio
        """)

        result = db.execute(query, {
            "id_cliente": id_cliente,
            "id_ejercicio": id_ejercicio
        }).fetchone()

        if not result:
            return EstadisticasProgreso(
                total_sesiones=0,
                peso_inicial=None,
                peso_actual=None,
                peso_maximo=None,
                progreso_total=None,
                porcentaje_mejora=None,
                rpe_promedio=None,
                records_personales=0,
                primera_sesion=None,
                ultima_sesion=None,
                dias_entrenando=0
            )

        return EstadisticasProgreso(
            total_sesiones=result[3],
            peso_inicial=result[4],
            peso_maximo=result[5],
            peso_actual=result[5],  # El máximo es el actual
            progreso_total=result[7],
            porcentaje_mejora=result[8],
            rpe_promedio=result[9],
            primera_sesion=result[10],
            ultima_sesion=result[11],
            dias_entrenando=result[12] or 0,
            records_personales=result[13]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")


# ============================================================
# ENDPOINTS - HISTORIAL DE RUTINAS
# ============================================================

@router.post("/historial/crear")
def crear_historial_rutina(
        id_rutina: int,
        fecha_inicio: Optional[datetime] = None,
        db: Session = Depends(get_db)
):
    """
    Crea un registro en el historial cuando se activa una rutina.
    """
    try:
        if fecha_inicio is None:
            fecha_inicio = datetime.now()

        # Llamar procedimiento almacenado
        query = text("CALL sp_crear_historial_rutina(:id_rutina, :fecha_inicio)")

        result = db.execute(query, {
            "id_rutina": id_rutina,
            "fecha_inicio": fecha_inicio
        })

        db.commit()

        id_historial = result.fetchone()[0]

        return {
            "success": True,
            "id_historial": id_historial,
            "mensaje": "Historial de rutina creado exitosamente"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear historial: {str(e)}")


@router.get("/historial/cliente/{id_cliente}")
def obtener_historial_cliente(
        id_cliente: int,
        db: Session = Depends(get_db)
) -> List[HistorialRutina]:
    """
    Obtiene el historial completo de rutinas de un cliente.
    """
    try:
        query = text("""
            SELECT 
                id_historial,
                nombre_rutina,
                fecha_inicio,
                fecha_fin,
                estado,
                duracion_dias,
                dias_entrenados,
                sesiones_completadas,
                porcentaje_cumplimiento,
                peso_inicial,
                peso_final,
                objetivo
            FROM historial_rutinas
            WHERE id_cliente = :id_cliente
            ORDER BY fecha_inicio DESC
        """)

        results = db.execute(query, {"id_cliente": id_cliente}).fetchall()

        historiales = []
        for row in results:
            historiales.append(HistorialRutina(
                id_historial=row[0],
                nombre_rutina=row[1],
                fecha_inicio=row[2],
                fecha_fin=row[3],
                estado=row[4],
                duracion_dias=row[5],
                dias_entrenados=row[6] or 0,
                sesiones_completadas=row[7] or 0,
                porcentaje_cumplimiento=float(row[8] or 0),
                peso_inicial=row[9],
                peso_final=row[10],
                objetivo=row[11]
            ))

        return historiales

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener historial: {str(e)}")


@router.put("/historial/{id_historial}/completar")
def completar_rutina(
        id_historial: int,
        peso_final: Optional[float] = None,
        grasa_corporal_final: Optional[float] = None,
        notas_entrenador: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Marca una rutina como completada y registra métricas finales.
    """
    try:
        query = text("""
            UPDATE historial_rutinas
            SET 
                estado = 'completada',
                fecha_completada = NOW(),
                peso_final = :peso_final,
                grasa_corporal_final = :grasa_corporal_final,
                notas_entrenador = :notas_entrenador
            WHERE id_historial = :id_historial
        """)

        db.execute(query, {
            "id_historial": id_historial,
            "peso_final": peso_final,
            "grasa_corporal_final": grasa_corporal_final,
            "notas_entrenador": notas_entrenador
        })

        db.commit()

        return {
            "success": True,
            "mensaje": "Rutina marcada como completada"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al completar rutina: {str(e)}")


# ============================================================
# ENDPOINTS - ALERTAS
# ============================================================

@router.get("/alertas/cliente/{id_cliente}")
def obtener_alertas_cliente(
        id_cliente: int,
        estado: Optional[EstadoAlerta] = None,
        db: Session = Depends(get_db)
) -> List[AlertaProgresion]:
    """
    Obtiene las alertas de progresión de un cliente.
    """
    try:
        if estado:
            query = text("""
                SELECT * FROM v_alertas_pendientes
                WHERE id_cliente = :id_cliente AND estado = :estado
                ORDER BY prioridad DESC, fecha_generacion ASC
            """)
            params = {"id_cliente": id_cliente, "estado": estado.value}
        else:
            query = text("""
                SELECT 
                    id_alerta, id_cliente, nombre_cliente, apellido_cliente,
                    tipo_alerta, prioridad, titulo, mensaje,
                    nombre_ejercicio, peso_actual, peso_sugerido,
                    fecha_generacion, dias_pendiente
                FROM v_alertas_pendientes
                WHERE id_cliente = :id_cliente
                ORDER BY prioridad DESC, fecha_generacion ASC
            """)
            params = {"id_cliente": id_cliente}

        results = db.execute(query, params).fetchall()

        alertas = []
        for row in results:
            alertas.append(AlertaProgresion(
                id_alerta=row[0],
                tipo_alerta=row[4],
                prioridad=row[5],
                titulo=row[6],
                mensaje=row[7],
                recomendacion=None,
                nombre_ejercicio=row[8],
                peso_actual=row[9],
                peso_sugerido=row[10],
                sesiones_sin_progreso=None,
                fecha_generacion=row[11],
                estado="pendiente"
            ))

        return alertas

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener alertas: {str(e)}")


@router.post("/alertas/analizar/{id_cliente}")
def analizar_progresion_cliente(
        id_cliente: int,
        db: Session = Depends(get_db)
):
    """
    Analiza la progresión del cliente y genera alertas automáticas.
    """
    try:
        query = text("CALL sp_analizar_progresion(:id_cliente)")

        result = db.execute(query, {"id_cliente": id_cliente})
        db.commit()

        alertas_generadas = result.fetchone()[0]

        return {
            "success": True,
            "alertas_generadas": alertas_generadas,
            "mensaje": f"Análisis completado. {alertas_generadas} alertas generadas."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al analizar progresión: {str(e)}")


@router.put("/alertas/{id_alerta}/atender")
def atender_alerta(
        id_alerta: int,
        id_entrenador: int,
        accion_tomada: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Marca una alerta como atendida.
    """
    try:
        query = text("""
            UPDATE alertas_progresion
            SET 
                estado = 'atendida',
                fecha_atendida = NOW(),
                atendida_por = :id_entrenador,
                accion_tomada = :accion_tomada
            WHERE id_alerta = :id_alerta
        """)

        db.execute(query, {
            "id_alerta": id_alerta,
            "id_entrenador": id_entrenador,
            "accion_tomada": accion_tomada
        })

        db.commit()

        return {
            "success": True,
            "mensaje": "Alerta atendida exitosamente"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al atender alerta: {str(e)}")


# ============================================================
# ENDPOINTS - OBJETIVOS
# ============================================================

@router.post("/objetivos/crear")
def crear_objetivo(
        objetivo: CrearObjetivoRequest,
        db: Session = Depends(get_db)
):
    """
    Crea un nuevo objetivo para un cliente.
    """
    try:
        query = text("""
            INSERT INTO objetivos_cliente (
                id_cliente, id_ejercicio, tipo_objetivo, titulo, descripcion,
                valor_inicial, valor_objetivo, unidad, fecha_inicio, fecha_limite
            ) VALUES (
                :id_cliente, :id_ejercicio, :tipo_objetivo, :titulo, :descripcion,
                :valor_inicial, :valor_objetivo, :unidad, NOW(), :fecha_limite
            )
        """)

        result = db.execute(query, {
            "id_cliente": objetivo.id_cliente,
            "id_ejercicio": objetivo.id_ejercicio,
            "tipo_objetivo": objetivo.tipo_objetivo,
            "titulo": objetivo.titulo,
            "descripcion": objetivo.descripcion,
            "valor_inicial": objetivo.valor_inicial,
            "valor_objetivo": objetivo.valor_objetivo,
            "unidad": objetivo.unidad,
            "fecha_limite": objetivo.fecha_limite
        })

        db.commit()

        return {
            "success": True,
            "id_objetivo": result.lastrowid,
            "mensaje": "Objetivo creado exitosamente"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear objetivo: {str(e)}")


@router.get("/objetivos/cliente/{id_cliente}")
def obtener_objetivos_cliente(
        id_cliente: int,
        db: Session = Depends(get_db)
) -> List[ObjetivoCliente]:
    """
    Obtiene los objetivos de un cliente.
    """
    try:
        query = text("""
            SELECT 
                id_objetivo, titulo, descripcion, tipo_objetivo,
                valor_inicial, valor_objetivo, valor_actual, unidad,
                porcentaje_completado, estado,
                fecha_inicio, fecha_limite, fecha_alcanzado
            FROM objetivos_cliente
            WHERE id_cliente = :id_cliente
            ORDER BY estado ASC, fecha_limite ASC
        """)

        results = db.execute(query, {"id_cliente": id_cliente}).fetchall()

        objetivos = []
        for row in results:
            objetivos.append(ObjetivoCliente(
                id_objetivo=row[0],
                titulo=row[1],
                descripcion=row[2],
                tipo_objetivo=row[3],
                valor_inicial=row[4],
                valor_objetivo=row[5],
                valor_actual=row[6],
                unidad=row[7],
                porcentaje_completado=float(row[8] or 0),
                estado=row[9],
                fecha_inicio=row[10],
                fecha_limite=row[11],
                fecha_alcanzado=row[12]
            ))

        return objetivos

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener objetivos: {str(e)}")


# ============================================================
# ENDPOINTS - DASHBOARD
# ============================================================

@router.get("/dashboard/cliente/{id_cliente}")
def obtener_dashboard_cliente(
        id_cliente: int,
        db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Obtiene un resumen completo del progreso del cliente para dashboard.
    """
    try:
        # Resumen general
        query_resumen = text("""
            SELECT * FROM v_resumen_progreso_cliente
            WHERE id_usuario = :id_cliente
        """)
        resumen = db.execute(query_resumen, {"id_cliente": id_cliente}).fetchone()

        # Alertas pendientes
        query_alertas = text("""
            SELECT COUNT(*) FROM alertas_progresion
            WHERE id_cliente = :id_cliente AND estado = 'pendiente'
        """)
        alertas_count = db.execute(query_alertas, {"id_cliente": id_cliente}).fetchone()[0]

        # Records personales recientes
        query_records = text("""
            SELECT COUNT(*) FROM progreso_ejercicios
            WHERE id_cliente = :id_cliente 
              AND es_record_personal = TRUE
              AND fecha_sesion >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """)
        records_mes = db.execute(query_records, {"id_cliente": id_cliente}).fetchone()[0]

        # Objetivos activos
        query_objetivos = text("""
            SELECT COUNT(*) FROM objetivos_cliente
            WHERE id_cliente = :id_cliente 
              AND estado IN ('pendiente', 'en_progreso')
        """)
        objetivos_activos = db.execute(query_objetivos, {"id_cliente": id_cliente}).fetchone()[0]

        return {
            "resumen": {
                "total_rutinas": resumen[3] if resumen else 0,
                "rutinas_completadas": resumen[4] if resumen else 0,
                "total_sesiones": resumen[5] if resumen else 0,
                "cumplimiento_promedio": float(resumen[6] or 0) if resumen else 0,
                "ultima_sesion": resumen[7] if resumen else None
            },
            "alertas_pendientes": alertas_count,
            "records_este_mes": records_mes,
            "objetivos_activos": objetivos_activos
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener dashboard: {str(e)}")