# services/ia_service.py
import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


def generar_rutina_con_ia(perfil_cliente: dict) -> dict:
    """
    Genera una rutina personalizada basada en el perfil del cliente usando Gemini
    """

    prompt = f"""
    Eres un entrenador personal experto. Genera una rutina de entrenamiento personalizada.

    Datos del cliente:
    - Nombre: {perfil_cliente.get('nombre', 'Cliente')}
    - Edad: {perfil_cliente.get('edad', 'N/A')} años
    - Peso: {perfil_cliente.get('peso_kg', 'N/A')} kg
    - Estatura: {perfil_cliente.get('estatura_cm', 'N/A')} cm
    - Problemas: {perfil_cliente.get('problemas', 'Ninguno')}
    - Enfermedades: {', '.join(perfil_cliente.get('enfermedades', [])) or 'Ninguna'}
    - Objetivo: {perfil_cliente.get('objetivo', 'Fitness general')}

    Por favor genera:
    1. Nombre de la rutina
    2. Descripción (2-3 líneas)
    3. Duración en minutos
    4. Dificultad (Principiante, Intermedio, Avanzado)
    5. Una lista de 5-7 ejercicios con:
       - Nombre del ejercicio
       - Series
       - Repeticiones
       - Descanso en segundos
       - Notas/recomendaciones

    Responde en formato JSON válido.
    """

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')  # ← Modelo actualizado
        response = model.generate_content(prompt)

        # Parsear respuesta
        import json
        import re

        # Extraer JSON de la respuesta
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            rutina_json = json.loads(json_match.group())
            return {
                "success": True,
                "rutina": rutina_json,
                "generada_en": datetime.utcnow().isoformat()
            }
        else:
            return {
                "success": False,
                "error": "No se pudo extraer JSON de la respuesta",
                "respuesta_raw": response.text
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def analizar_foto_usuario_con_ia(imagen_base64: str) -> dict:
    """
    Analiza una foto del usuario para hacer una evaluación visual
    """

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')  # ← Modelo actualizado

        image_data = {
            "mime_type": "image/jpeg",
            "data": imagen_base64
        }

        prompt = """
        Analiza esta foto de una persona y proporciona:
        1. Evaluación visual del estado físico (Sedentario, Moderado, Fit, Muy fit)
        2. Posible composición corporal (Sobrepeso, Normal, Musculoso, Muy musculoso)
        3. Observaciones sobre postura
        4. Recomendaciones generales de ejercicio (2-3 líneas)
        5. Puntuación de forma física (1-10)

        Sé respetuoso y constructivo. Responde en JSON.
        """

        response = model.generate_content([prompt, image_data])

        import json
        import re

        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            analisis = json.loads(json_match.group())
            return {
                "success": True,
                "analisis": analisis,
                "fecha_analisis": datetime.utcnow().isoformat()
            }
        else:
            return {
                "success": False,
                "error": "No se pudo extraer JSON",
                "respuesta_raw": response.text
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def calificar_perfil_entrenador_con_ia(perfil_entrenador: dict) -> dict:
    """
    Califica automáticamente a un entrenador basado en su perfil
    """

    prompt = f"""
    Califica este perfil de entrenador en una escala del 1-5:

    Nombre: {perfil_entrenador.get('nombre', 'N/A')}
    Especialidad: {perfil_entrenador.get('especialidad', 'N/A')}
    Experiencia (años): {perfil_entrenador.get('experiencia', 'N/A')}
    Certificaciones: {perfil_entrenador.get('certificaciones', 'N/A')}
    Educación: {perfil_entrenador.get('educacion', 'N/A')}

    Proporciona:
    1. Puntuación general (1-5)
    2. Fortalezas (3 máximo)
    3. Áreas de mejora (2-3)
    4. Recomendación si contratar (Sí/No/Tal vez)

    Responde en JSON.
    """

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')  # ← Modelo actualizado
        response = model.generate_content(prompt)

        import json
        import re

        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            calificacion = json.loads(json_match.group())
            return {
                "success": True,
                "calificacion": calificacion
            }
        else:
            return {
                "success": False,
                "error": "No se pudo extraer JSON"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def analizar_perfil_usuario_con_ia(perfil_usuario: dict) -> dict:
    """
    Analiza el perfil completo del usuario
    """

    # Convertir a float para evitar errores con Decimal
    peso = float(perfil_usuario.get("peso_kg") or 70)
    estatura_cm = float(perfil_usuario.get("estatura_cm") or 170)
    estatura_m = estatura_cm / 100
    imc = peso / (estatura_m ** 2) if estatura_m > 0 else 0

    prompt = f"""
    Analiza el perfil de este usuario:

    - Nombre: {perfil_usuario.get('nombre', 'Usuario')}
    - Edad: {perfil_usuario.get('edad', 'N/A')} años
    - Peso: {peso} kg, Estatura: {estatura_cm} cm
    - IMC: {imc:.2f}
    - Problemas: {perfil_usuario.get('problemas', 'Ninguno')}
    - Enfermedades: {', '.join(perfil_usuario.get('enfermedades', [])) or 'Ninguna'}
    - Objetivo: {perfil_usuario.get('objetivo', 'Fitness general')}

    Proporciona en JSON:
    1. categoria_fitness (Sedentario/Moderado/Activo/Muy activo)
    2. nivel_condicion (Principiante/Intermedio/Avanzado)
    3. recomendaciones_entrenamiento (4-5 líneas)
    4. recomendaciones_nutricion (3-4 líneas)
    5. objetivos_sugeridos (2-3 objetivos)
    6. riesgos_potenciales (2-3 riesgos)
    7. puntuacion_general (1-10)
    """

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)

        import json
        import re

        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            analisis = json.loads(json_match.group())
            return {"success": True, "analisis": analisis}
        else:
            return {"success": False, "error": "No se pudo extraer JSON"}

    except Exception as e:
        return {"success": False, "error": str(e)}