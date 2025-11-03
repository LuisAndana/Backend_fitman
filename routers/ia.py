# routers/ia.py
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
import base64
import json

from utils.dependencies import get_db, get_current_user
from models.user import Usuario
from models.analisis_usuario import AnalisisUsuario, Progreso
from models.rutina_generada import RutinaGenerada
from models.analisis_perfil import AnalisisPerfil
from schemas.ia import (
    GenerarRutinaRequest, RutinaGeneradaOut,
    AnalisisPhotoRequest, AnalisisPhotoOut,
    CalificacionEntrenadorRequest, CalificacionEntrenadorOut,
    ProgresoOut
)
from services.ia_service import (
    generar_rutina_con_ia,
    analizar_foto_usuario_con_ia,
    calificar_perfil_entrenador_con_ia,
    analizar_perfil_usuario_con_ia
)

router = APIRouter(prefix="/ia", tags=["ia"])


@router.post("/generar-rutina", response_model=dict, status_code=status.HTTP_201_CREATED)
def generar_rutina_endpoint(
        payload: GenerarRutinaRequest,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Genera una rutina personalizada con IA basada en el perfil del usuario"""

    usuario = db.query(Usuario).filter(Usuario.id_usuario == current.id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    perfil_cliente = {
        "nombre": f"{usuario.nombre} {usuario.apellido}",
        "edad": usuario.edad,
        "peso_kg": usuario.peso_kg,
        "estatura_cm": usuario.estatura_cm,
        "problemas": usuario.problemas,
        "enfermedades": usuario.enfermedades if isinstance(usuario.enfermedades, list) else [],
        "objetivo": payload.objetivo,
    }

    resultado = generar_rutina_con_ia(perfil_cliente)

    if not resultado.get("success"):
        raise HTTPException(status_code=500, detail=resultado.get("error"))

    rutina_data = resultado.get("rutina")

    try:
        rutina = RutinaGenerada(
            id_usuario=current.id_usuario,
            nombre=rutina_data.get("nombre_rutina", "Rutina sin nombre"),
            descripcion=rutina_data.get("descripcion", ""),
            duracion_minutos=rutina_data.get("duracion_minutos", 60),
            dificultad=rutina_data.get("dificultad", "Intermedio"),
            ejercicios=json.dumps(rutina_data.get("ejercicios", [])),
            prompt_usado=str(perfil_cliente),
            modelo_ia="gemini-2.0-flash"
        )
        db.add(rutina)
        db.commit()
        db.refresh(rutina)

        return {
            "success": True,
            "id_rutina_generada": rutina.id_rutina_generada,
            "rutina": rutina_data,
            "mensaje": "Rutina generada y guardada exitosamente en BD",
            "modelo": "gemini-2.0-flash"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error guardando rutina: {str(e)}")


@router.post("/analizar-foto", response_model=dict, status_code=status.HTTP_201_CREATED)
def analizar_foto_endpoint(
        file: UploadFile = File(...),
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Analiza una foto del usuario con IA"""

    try:
        contenido = file.file.read()
        imagen_base64 = base64.b64encode(contenido).decode('utf-8')

        resultado = analizar_foto_usuario_con_ia(imagen_base64)

        if not resultado.get("success"):
            raise HTTPException(status_code=500, detail=resultado.get("error"))

        analisis_data = resultado.get("analisis")

        analisis = AnalisisUsuario(
            id_usuario=current.id_usuario,
            estado_fisico=analisis_data.get("estado_fisico", ""),
            composicion_corporal=analisis_data.get("composicion_corporal", ""),
            observaciones_postura=analisis_data.get("observaciones_postura", ""),
            recomendaciones=analisis_data.get("recomendaciones", ""),
            puntuacion_forma_fisica=float(analisis_data.get("puntuacion_forma_fisica", 5)),
            imagen_url=file.filename,
        )
        db.add(analisis)
        db.commit()
        db.refresh(analisis)

        return {
            "success": True,
            "id_analisis": analisis.id_analisis,
            "analisis": analisis_data,
            "mensaje": "Foto analizada y guardada exitosamente"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error procesando foto: {str(e)}")


@router.post("/calificar-entrenador")
def calificar_entrenador_endpoint(
        payload: CalificacionEntrenadorRequest,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Califica automáticamente a un entrenador con IA"""

    entrenador = db.query(Usuario).filter(Usuario.id_usuario == payload.id_entrenador).first()
    if not entrenador:
        raise HTTPException(status_code=404, detail="Entrenador no encontrado")

    perfil_entrenador = {
        "nombre": f"{entrenador.nombre} {entrenador.apellido}",
        "especialidad": getattr(entrenador, "especialidad", "General"),
        "experiencia": getattr(entrenador, "experiencia", 0),
        "certificaciones": "N/A",
        "educacion": "N/A",
    }

    resultado = calificar_perfil_entrenador_con_ia(perfil_entrenador)

    if not resultado.get("success"):
        raise HTTPException(status_code=500, detail=resultado.get("error"))

    return {
        "success": True,
        "calificacion": resultado.get("calificacion"),
        "id_entrenador": payload.id_entrenador
    }


@router.post("/registrar-progreso", response_model=dict, status_code=status.HTTP_201_CREATED)
def registrar_progreso_endpoint(
        peso_actual: float,
        notas: str | None = None,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Registra el progreso (peso) del usuario"""

    try:
        progreso = Progreso(
            id_usuario=current.id_usuario,
            peso_anterior=current.peso_kg,
            peso_actual=peso_actual,
            notas=notas,
        )
        db.add(progreso)

        current.peso_kg = peso_actual
        db.add(current)

        db.commit()
        db.refresh(progreso)

        return {
            "success": True,
            "id_progreso": progreso.id_progreso,
            "peso_anterior": progreso.peso_anterior,
            "peso_actual": progreso.peso_actual,
            "diferencia": peso_actual - (progreso.peso_anterior or peso_actual),
            "mensaje": "Progreso registrado exitosamente en BD"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error guardando progreso: {str(e)}")


@router.get("/progreso/historial", response_model=List[ProgresoOut])
def obtener_progreso_endpoint(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene el historial de progreso del usuario"""

    progresos = db.query(Progreso) \
        .filter(Progreso.id_usuario == current.id_usuario) \
        .order_by(Progreso.fecha.desc()) \
        .all()

    return progresos


@router.get("/analisis/ultimo", response_model=dict)
def obtener_ultimo_analisis_endpoint(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene el último análisis de foto del usuario"""

    analisis = db.query(AnalisisUsuario) \
        .filter(AnalisisUsuario.id_usuario == current.id_usuario) \
        .order_by(AnalisisUsuario.fecha_analisis.desc()) \
        .first()

    if not analisis:
        raise HTTPException(status_code=404, detail="No hay análisis registrado")

    return {
        "id_analisis": analisis.id_analisis,
        "estado_fisico": analisis.estado_fisico,
        "composicion_corporal": analisis.composicion_corporal,
        "observaciones_postura": analisis.observaciones_postura,
        "recomendaciones": analisis.recomendaciones,
        "puntuacion": analisis.puntuacion_forma_fisica,
        "fecha": analisis.fecha_analisis
    }


@router.get("/rutinas/mis-rutinas", response_model=List[dict])
def obtener_mis_rutinas_endpoint(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene todas las rutinas generadas del usuario"""

    rutinas = db.query(RutinaGenerada) \
        .filter(RutinaGenerada.id_usuario == current.id_usuario) \
        .order_by(RutinaGenerada.fecha_generacion.desc()) \
        .all()

    resultado = []
    for rutina in rutinas:
        resultado.append({
            "id_rutina_generada": rutina.id_rutina_generada,
            "nombre": rutina.nombre,
            "descripcion": rutina.descripcion,
            "duracion_minutos": rutina.duracion_minutos,
            "dificultad": rutina.dificultad,
            "ejercicios": json.loads(rutina.ejercicios),
            "fecha_generacion": rutina.fecha_generacion,
            "modelo_ia": rutina.modelo_ia
        })

    return resultado


@router.get("/rutinas/{id_rutina}", response_model=dict)
def obtener_rutina_endpoint(
        id_rutina: int,
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene una rutina específica generada"""

    rutina = db.query(RutinaGenerada) \
        .filter(
        RutinaGenerada.id_rutina_generada == id_rutina,
        RutinaGenerada.id_usuario == current.id_usuario
    ) \
        .first()

    if not rutina:
        raise HTTPException(status_code=404, detail="Rutina no encontrada")

    return {
        "id_rutina_generada": rutina.id_rutina_generada,
        "nombre": rutina.nombre,
        "descripcion": rutina.descripcion,
        "duracion_minutos": rutina.duracion_minutos,
        "dificultad": rutina.dificultad,
        "ejercicios": json.loads(rutina.ejercicios),
        "fecha_generacion": rutina.fecha_generacion,
        "modelo_ia": rutina.modelo_ia
    }


@router.post("/analizar-perfil", response_model=dict, status_code=status.HTTP_201_CREATED)
def analizar_perfil_usuario_endpoint(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Analiza el perfil completo del usuario con IA"""

    usuario = db.query(Usuario).filter(Usuario.id_usuario == current.id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    perfil_usuario = {
        "nombre": f"{usuario.nombre} {usuario.apellido}",
        "edad": usuario.edad,
        "peso_kg": usuario.peso_kg,
        "estatura_cm": usuario.estatura_cm,
        "problemas": usuario.problemas,
        "enfermedades": usuario.enfermedades if isinstance(usuario.enfermedades, list) else [],
        "objetivo": getattr(usuario, "objetivo", "Fitness general"),
    }

    resultado = analizar_perfil_usuario_con_ia(perfil_usuario)

    if not resultado.get("success"):
        raise HTTPException(status_code=500, detail=resultado.get("error"))

    analisis_data = resultado.get("analisis")

    try:
        # Convertir listas a strings JSON
        recomendaciones_entrenamiento = analisis_data.get("recomendaciones_entrenamiento", "")
        if isinstance(recomendaciones_entrenamiento, list):
            recomendaciones_entrenamiento = json.dumps(recomendaciones_entrenamiento, ensure_ascii=False)

        recomendaciones_nutricion = analisis_data.get("recomendaciones_nutricion", "")
        if isinstance(recomendaciones_nutricion, list):
            recomendaciones_nutricion = json.dumps(recomendaciones_nutricion, ensure_ascii=False)

        objetivos_sugeridos = analisis_data.get("objetivos_sugeridos", "")
        if isinstance(objetivos_sugeridos, list):
            objetivos_sugeridos = json.dumps(objetivos_sugeridos, ensure_ascii=False)
        else:
            objetivos_sugeridos = str(objetivos_sugeridos)

        riesgos_potenciales = analisis_data.get("riesgos_potenciales", "")
        if isinstance(riesgos_potenciales, list):
            riesgos_potenciales = json.dumps(riesgos_potenciales, ensure_ascii=False)
        else:
            riesgos_potenciales = str(riesgos_potenciales)

        analisis = AnalisisPerfil(
            id_usuario=current.id_usuario,
            categoria_fitness=analisis_data.get("categoria_fitness", ""),
            nivel_condicion=analisis_data.get("nivel_condicion", ""),
            recomendaciones_entrenamiento=str(recomendaciones_entrenamiento),
            recomendaciones_nutricion=str(recomendaciones_nutricion),
            objetivos_sugeridos=objetivos_sugeridos,
            riesgos_potenciales=riesgos_potenciales,
            puntuacion_general=float(analisis_data.get("puntuacion_general", 0))
        )
        db.add(analisis)
        db.commit()
        db.refresh(analisis)

        return {
            "success": True,
            "id_analisis_perfil": analisis.id_analisis_perfil,
            "analisis": analisis_data,
            "mensaje": "Perfil analizado y guardado"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/analisis-perfil", response_model=dict)
def obtener_analisis_perfil_endpoint(
        current: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Obtiene el análisis de perfil del usuario"""

    analisis = db.query(AnalisisPerfil) \
        .filter(AnalisisPerfil.id_usuario == current.id_usuario) \
        .order_by(AnalisisPerfil.fecha_analisis.desc()) \
        .first()

    if not analisis:
        raise HTTPException(status_code=404, detail="No hay análisis registrado")

    return {
        "id_analisis_perfil": analisis.id_analisis_perfil,
        "categoria_fitness": analisis.categoria_fitness,
        "nivel_condicion": analisis.nivel_condicion,
        "recomendaciones_entrenamiento": analisis.recomendaciones_entrenamiento,
        "recomendaciones_nutricion": analisis.recomendaciones_nutricion,
        "objetivos_sugeridos": analisis.objetivos_sugeridos,
        "riesgos_potenciales": analisis.riesgos_potenciales,
        "puntuacion_general": analisis.puntuacion_general,
        "fecha_analisis": analisis.fecha_analisis
    }