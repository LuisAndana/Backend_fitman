# models/routine.py - Modelos corregidos sin dependencias circulares

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, DECIMAL, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum


# IMPORTANTE: Importar Base desde donde la tengas configurada
# from database import Base
# O donde sea que definas tu Base en tu proyecto

class EstadoRutina(str, enum.Enum):
    ACTIVA = "activa"
    INACTIVA = "inactiva"
    COMPLETADA = "completada"
    EN_EDICION = "en_edicion"


class Rutina:
    """
    NOTA: Este es un ejemplo de cómo debería ser.

    NO USES SQLALCHEMY si tienes problemas con las relaciones.
    En su lugar, usa directamente SQL raw queries en tu router.

    Si necesitas ORM, aquí está la estructura correcta:
    """
    __tablename__ = "rutinas"

    # Campos
    id_rutina = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario'), nullable=False)
    id_entrenador = Column(Integer, ForeignKey('usuarios.id_usuario'), nullable=False)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(Text)
    dias_por_semana = Column(Integer, default=3)
    nivel_dificultad = Column(String(50))
    grupo_muscular_enfoque = Column(String(100))
    problemas_alumno = Column(JSON)
    enfermedades_alumno = Column(JSON)
    objetivo_alumno = Column(Text)
    estado = Column(Enum(EstadoRutina), default=EstadoRutina.EN_EDICION)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_inicio = Column(DateTime)
    fecha_modificacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # NO uses relationship() si tienes problemas
    # Usa SQL raw queries en su lugar


class DiaRutina:
    """Modelo para días de rutina"""
    __tablename__ = "dias_rutina"

    id_dia_rutina = Column(Integer, primary_key=True, index=True)
    id_rutina = Column(Integer, ForeignKey('rutinas.id_rutina'), nullable=False)
    numero_dia = Column(Integer, nullable=False)
    nombre_dia = Column(String(50), nullable=False)
    descripcion = Column(Text)
    activo = Column(Boolean, default=True)


class EjercicioDiaRutina:
    """Modelo para ejercicios en un día"""
    __tablename__ = "ejercicios_dia_rutina"

    id_ejercicio_dia = Column(Integer, primary_key=True, index=True)
    id_dia_rutina = Column(Integer, ForeignKey('dias_rutina.id_dia_rutina'), nullable=False)
    id_ejercicio = Column(Integer, ForeignKey('ejercicios.id_ejercicio'), nullable=False)
    orden = Column(Integer, nullable=False)
    series = Column(Integer, default=3)
    repeticiones = Column(Integer)
    rango_repeticiones = Column(String(20))
    peso = Column(DECIMAL(5, 2))
    descanso_segundos = Column(Integer, default=60)
    notas = Column(Text)

    # NO uses relationship() a Ejercicio si causa problemas
    # Usa SQL raw queries en su lugar


# ============================================================
# ALTERNATIVA: USO CON RAW SQL (RECOMENDADO)
# ============================================================

class RutinaService:
    """
    Servicio para rutinas usando SQL raw queries.
    ESTO FUNCIONA SIEMPRE, sin problemas de mappers.
    """

    @staticmethod
    def crear_rutina_sql(db, id_usuario, id_entrenador, nombre, datos):
        """Crea rutina usando SQL raw"""
        query = """
        INSERT INTO rutinas (
            id_usuario, id_entrenador, nombre, descripcion,
            dias_por_semana, nivel_dificultad, grupo_muscular_enfoque,
            problemas_alumno, enfermedades_alumno, objetivo_alumno,
            estado, fecha_creacion
        ) VALUES (
            :id_usuario, :id_entrenador, :nombre, :descripcion,
            :dias_por_semana, :nivel_dificultad, :grupo_muscular_enfoque,
            :problemas_alumno, :enfermedades_alumno, :objetivo_alumno,
            :estado, NOW()
        )
        """

        from sqlalchemy import text
        import json

        params = {
            'id_usuario': id_usuario,
            'id_entrenador': id_entrenador,
            'nombre': nombre,
            'descripcion': datos.get('descripcion'),
            'dias_por_semana': datos.get('dias_por_semana', 3),
            'nivel_dificultad': datos.get('nivel_dificultad'),
            'grupo_muscular_enfoque': datos.get('grupo_muscular_enfoque'),
            'problemas_alumno': json.dumps(datos.get('problemas_alumno', [])),
            'enfermedades_alumno': json.dumps(datos.get('enfermedades_alumno', [])),
            'objetivo_alumno': datos.get('objetivo_alumno'),
            'estado': 'en_edicion'
        }

        result = db.execute(text(query), params)
        db.commit()
        return result.lastrowid

    @staticmethod
    def obtener_rutina_completa_sql(db, id_rutina):
        """Obtiene rutina completa con todos sus días y ejercicios"""
        from sqlalchemy import text

        query = """
        SELECT 
            r.id_rutina, r.nombre, r.descripcion, r.dias_por_semana,
            r.nivel_dificultad, r.estado, r.fecha_creacion,
            d.id_dia_rutina, d.numero_dia, d.nombre_dia, d.descripcion as dia_descripcion,
            e.id_ejercicio_dia, e.id_ejercicio, e.orden, e.series,
            e.repeticiones, e.rango_repeticiones, e.peso, e.descanso_segundos, e.notas,
            ej.nombre as ejercicio_nombre, ej.descripcion as ejercicio_descripcion
        FROM rutinas r
        LEFT JOIN dias_rutina d ON r.id_rutina = d.id_rutina
        LEFT JOIN ejercicios_dia_rutina e ON d.id_dia_rutina = e.id_dia_rutina
        LEFT JOIN ejercicios ej ON e.id_ejercicio = ej.id_ejercicio
        WHERE r.id_rutina = :id_rutina
        ORDER BY d.numero_dia, e.orden
        """

        results = db.execute(text(query), {'id_rutina': id_rutina}).fetchall()
        return results

    @staticmethod
    def agregar_ejercicio_a_dia_sql(db, id_dia_rutina, id_ejercicio, orden, series, reps, descanso):
        """Agrega ejercicio a un día de rutina"""
        from sqlalchemy import text

        query = """
        INSERT INTO ejercicios_dia_rutina (
            id_dia_rutina, id_ejercicio, orden, series,
            repeticiones, descanso_segundos
        ) VALUES (
            :id_dia_rutina, :id_ejercicio, :orden, :series,
            :repeticiones, :descanso_segundos
        )
        """

        params = {
            'id_dia_rutina': id_dia_rutina,
            'id_ejercicio': id_ejercicio,
            'orden': orden,
            'series': series,
            'repeticiones': reps,
            'descanso_segundos': descanso
        }

        result = db.execute(text(query), params)
        db.commit()
        return result.lastrowid


# ============================================================
# USO EN ROUTER
# ============================================================

"""
En tu router (routers/ia.py), en lugar de usar ORM:

    # ❌ EVITA ESTO (causa problemas):
    from models.routine import Rutina, DiaRutina
    rutina = db.query(Rutina).filter(Rutina.id_usuario == id).first()

    # ✅ USA ESTO (siempre funciona):
    from services.ia_service import IAService
    from models.routine import RutinaService
    from sqlalchemy import text

    # Crear rutina
    id_rutina = RutinaService.crear_rutina_sql(
        db, id_usuario, id_entrenador, "Mi Rutina",
        {'dias_por_semana': 3, 'nivel_dificultad': 'intermedio'}
    )

    # Obtener rutina
    resultado = RutinaService.obtener_rutina_completa_sql(db, id_rutina)

    # Agregar ejercicio
    id_ej = RutinaService.agregar_ejercicio_a_dia_sql(
        db, id_dia, id_ejercicio, orden=1, series=3, reps=10, descanso=60
    )
"""