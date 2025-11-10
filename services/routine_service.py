# services/rutina_service.py - Servicio completo para rutinas

from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import datetime
import json
from models.rutina import Rutina, DiaRutina, EjercicioDiaRutina, EstadoRutina
from schemas.rutina_schemas import (
    ParametrosRutinaCreate, RutinaDetailResponse, RutinaListResponse
)


class RutinaService:
    """Servicio para gestionar rutinas"""

    @staticmethod
    def crear_rutina(
            db: Session,
            parametros: ParametrosRutinaCreate,
            dias_config: List[Dict]
    ) -> Rutina:
        """
        Crea una rutina completa con todos sus días y ejercicios.

        Args:
            db: Sesión de BD
            parametros: Parámetros iniciales
            dias_config: Lista con configuración de cada día

        Returns:
            Rutina creada
        """
        # Crear rutina principal
        rutina = Rutina(
            id_usuario=parametros.id_usuario,
            id_entrenador=parametros.id_entrenador,
            nombre=parametros.nombre_rutina,
            dias_por_semana=parametros.dias_por_semana,
            nivel_dificultad=parametros.nivel_dificultad,
            grupo_muscular_enfoque=parametros.grupo_muscular_enfoque,
            problemas_alumno=parametros.problemas,
            enfermedades_alumno=parametros.enfermedades,
            objetivo_alumno=parametros.objetivo_alumno,
            estado=EstadoRutina.EN_EDICION
        )
        db.add(rutina)
        db.flush()  # Para obtener el ID sin commit

        # Crear días y ejercicios
        for dia_data in dias_config:
            dia_rutina = DiaRutina(
                id_rutina=rutina.id_rutina,
                numero_dia=dia_data.get("numero_dia"),
                nombre_dia=dia_data.get("nombre_dia"),
                descripcion=dia_data.get("descripcion"),
                activo=True
            )
            db.add(dia_rutina)
            db.flush()

            # Agregar ejercicios al día
            for orden, ejercicio_data in enumerate(dia_data.get("ejercicios", []), 1):
                ejercicio_dia = EjercicioDiaRutina(
                    id_dia_rutina=dia_rutina.id_dia_rutina,
                    id_ejercicio=ejercicio_data.get("id_ejercicio"),
                    orden=orden,
                    series=ejercicio_data.get("series", 3),
                    repeticiones=ejercicio_data.get("repeticiones"),
                    rango_repeticiones=ejercicio_data.get("rango_repeticiones"),
                    peso=ejercicio_data.get("peso"),
                    descanso_segundos=ejercicio_data.get("descanso_segundos", 60),
                    notas=ejercicio_data.get("notas")
                )
                db.add(ejercicio_dia)

        db.commit()
        db.refresh(rutina)
        return rutina

    @staticmethod
    def actualizar_rutina(
            db: Session,
            id_rutina: int,
            **kwargs
    ) -> Optional[Rutina]:
        """
        Actualiza campos de una rutina.
        """
        rutina = db.query(Rutina).filter(Rutina.id_rutina == id_rutina).first()
        if not rutina:
            return None

        for key, value in kwargs.items():
            if hasattr(rutina, key) and value is not None:
                setattr(rutina, key, value)

        rutina.fecha_modificacion = datetime.utcnow()
        db.commit()
        db.refresh(rutina)
        return rutina

    @staticmethod
    def obtener_rutina(db: Session, id_rutina: int) -> Optional[Rutina]:
        """Obtiene una rutina por ID"""
        return db.query(Rutina).filter(Rutina.id_rutina == id_rutina).first()

    @staticmethod
    def obtener_rutinas_usuario(db: Session, id_usuario: int) -> List[Rutina]:
        """Obtiene todas las rutinas de un usuario"""
        return db.query(Rutina).filter(Rutina.id_usuario == id_usuario).all()

    @staticmethod
    def obtener_rutinas_entrenador(db: Session, id_entrenador: int) -> List[Rutina]:
        """Obtiene todas las rutinas que un entrenador ha creado"""
        return db.query(Rutina).filter(Rutina.id_entrenador == id_entrenador).all()

    @staticmethod
    def eliminar_rutina(db: Session, id_rutina: int) -> bool:
        """
        Elimina una rutina y todos sus días/ejercicios (cascada).
        """
        rutina = db.query(Rutina).filter(Rutina.id_rutina == id_rutina).first()
        if not rutina:
            return False

        db.delete(rutina)
        db.commit()
        return True

    @staticmethod
    def agregar_ejercicio_a_dia(
            db: Session,
            id_dia_rutina: int,
            id_ejercicio: int,
            orden: int,
            **kwargs
    ) -> EjercicioDiaRutina:
        """Agrega un ejercicio a un día de rutina"""
        ejercicio_dia = EjercicioDiaRutina(
            id_dia_rutina=id_dia_rutina,
            id_ejercicio=id_ejercicio,
            orden=orden,
            **kwargs
        )
        db.add(ejercicio_dia)
        db.commit()
        db.refresh(ejercicio_dia)
        return ejercicio_dia

    @staticmethod
    def eliminar_ejercicio_de_dia(
            db: Session,
            id_ejercicio_dia: int
    ) -> bool:
        """Elimina un ejercicio de un día"""
        ejercicio = db.query(EjercicioDiaRutina).filter(
            EjercicioDiaRutina.id_ejercicio_dia == id_ejercicio_dia
        ).first()

        if not ejercicio:
            return False

        db.delete(ejercicio)
        db.commit()
        return True

    @staticmethod
    def actualizar_ejercicio_dia(
            db: Session,
            id_ejercicio_dia: int,
            **kwargs
    ) -> Optional[EjercicioDiaRutina]:
        """Actualiza un ejercicio dentro de un día"""
        ejercicio = db.query(EjercicioDiaRutina).filter(
            EjercicioDiaRutina.id_ejercicio_dia == id_ejercicio_dia
        ).first()

        if not ejercicio:
            return None

        for key, value in kwargs.items():
            if hasattr(ejercicio, key) and value is not None:
                setattr(ejercicio, key, value)

        db.commit()
        db.refresh(ejercicio)
        return ejercicio

    @staticmethod
    def cambiar_estado_rutina(
            db: Session,
            id_rutina: int,
            nuevo_estado: EstadoRutina
    ) -> Optional[Rutina]:
        """Cambia el estado de una rutina"""
        rutina = db.query(Rutina).filter(Rutina.id_rutina == id_rutina).first()
        if not rutina:
            return None

        rutina.estado = nuevo_estado
        if nuevo_estado == EstadoRutina.ACTIVA and not rutina.fecha_inicio:
            rutina.fecha_inicio = datetime.utcnow()

        db.commit()
        db.refresh(rutina)
        return rutina

    @staticmethod
    def duplicar_rutina(
            db: Session,
            id_rutina: int,
            id_nuevo_usuario: int,
            nombre_nueva: str = None
    ) -> Optional[Rutina]:
        """Duplica una rutina para otro usuario"""
        rutina_original = db.query(Rutina).filter(Rutina.id_rutina == id_rutina).first()
        if not rutina_original:
            return None

        # Crear nueva rutina
        nueva_rutina = Rutina(
            id_usuario=id_nuevo_usuario,
            id_entrenador=rutina_original.id_entrenador,
            nombre=nombre_nueva or f"{rutina_original.nombre} (Copia)",
            descripcion=rutina_original.descripcion,
            dias_por_semana=rutina_original.dias_por_semana,
            nivel_dificultad=rutina_original.nivel_dificultad,
            grupo_muscular_enfoque=rutina_original.grupo_muscular_enfoque,
            problemas_alumno=rutina_original.problemas_alumno,
            enfermedades_alumno=rutina_original.enfermedades_alumno,
            objetivo_alumno=rutina_original.objetivo_alumno,
            estado=EstadoRutina.EN_EDICION
        )
        db.add(nueva_rutina)
        db.flush()

        # Copiar días y ejercicios
        for dia_original in rutina_original.dias_rutina:
            nuevo_dia = DiaRutina(
                id_rutina=nueva_rutina.id_rutina,
                numero_dia=dia_original.numero_dia,
                nombre_dia=dia_original.nombre_dia,
                descripcion=dia_original.descripcion,
                activo=dia_original.activo
            )
            db.add(nuevo_dia)
            db.flush()

            for ejercicio_original in dia_original.ejercicios_dia:
                nuevo_ejercicio = EjercicioDiaRutina(
                    id_dia_rutina=nuevo_dia.id_dia_rutina,
                    id_ejercicio=ejercicio_original.id_ejercicio,
                    orden=ejercicio_original.orden,
                    series=ejercicio_original.series,
                    repeticiones=ejercicio_original.repeticiones,
                    rango_repeticiones=ejercicio_original.rango_repeticiones,
                    peso=ejercicio_original.peso,
                    descanso_segundos=ejercicio_original.descanso_segundos,
                    notas=ejercicio_original.notas
                )
                db.add(nuevo_ejercicio)

        db.commit()
        db.refresh(nueva_rutina)
        return nueva_rutina

    @staticmethod
    def exportar_rutina_json(db: Session, id_rutina: int) -> Dict:
        """Exporta una rutina a formato JSON"""
        rutina = db.query(Rutina).filter(Rutina.id_rutina == id_rutina).first()
        if not rutina:
            return None

        datos = {
            "nombre": rutina.nombre,
            "descripcion": rutina.descripcion,
            "dias_por_semana": rutina.dias_por_semana,
            "nivel_dificultad": rutina.nivel_dificultad,
            "grupo_muscular": rutina.grupo_muscular_enfoque,
            "objetivo": rutina.objetivo_alumno,
            "dias": []
        }

        for dia in rutina.dias_rutina:
            dia_data = {
                "nombre": dia.nombre_dia,
                "descripcion": dia.descripcion,
                "ejercicios": [
                    {
                        "nombre": e.ejercicio.nombre,
                        "series": e.series,
                        "repeticiones": e.repeticiones,
                        "rango": e.rango_repeticiones,
                        "peso": float(e.peso) if e.peso else None,
                        "descanso": e.descanso_segundos,
                        "notas": e.notas
                    }
                    for e in dia.ejercicios_dia
                ]
            }
            datos["dias"].append(dia_data)

        return datos