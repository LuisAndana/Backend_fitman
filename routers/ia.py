# routers/ia.py - Router IA V5 (Gemini + OpenAI + Grok + Vigencia de Rutinas)

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any, Literal
import google.generativeai as genai
import os
import json
import re
from datetime import datetime, timedelta

from utils.dependencies import get_db

# ============================================================
# ROUTER CON PREFIJO INTERNO - NO AÑADIR PREFIJO EN main.py
# ============================================================
router = APIRouter(prefix="/api/ia", tags=["IA"])

# ============================================================
# CONFIG - VERSIÓN ACTUALIZADA
# ============================================================

# Gemini Configuratio
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "models/gemini-2.5-flash")
GEMINI_VISION_MODEL_ID = os.getenv("GEMINI_VISION_MODEL_ID", "models/gemini-2.5-pro")
GEMINI_TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "120000"))  # 120 segundos por defecto
GEMINI_TIMEOUT_SECONDS = GEMINI_TIMEOUT_MS / 1000  # Convertir a segundos

if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        print(f"✅ Gemini configurado con modelo: {GEMINI_MODEL}")
        print(f"📊 Timeout configurado: {GEMINI_TIMEOUT_SECONDS} segundos")
else:
    print("⚠️ GEMINI_API_KEY no configurada - usando solo generador local")

    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Import OpenAI only if API key is configured
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI

            openai_client = OpenAI(api_key=OPENAI_API_KEY)
        except ImportError:
            print("⚠️ Advertencia: openai library no instalada. Instala con: pip install openai")
            openai_client = None
    else:
        openai_client = None

    # Grok (xAI) Configuration
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    GROK_MODEL = os.getenv("GROK_MODEL", "grok-beta")

    # Import Grok client (uses OpenAI-compatible API)
    if GROK_API_KEY:
        try:
            from openai import OpenAI

            grok_client = OpenAI(
                api_key=GROK_API_KEY,
                base_url="https://api.x.ai/v1"
            )
        except ImportError:
            print("⚠️ Advertencia: openai library no instalada para Grok. Instala con: pip install openai")
            grok_client = None
    else:
        grok_client = None

    # ============================================================
    # SCHEMAS
    # ============================================================

    from enum import Enum

    class ExtenderVigenciaRequest(BaseModel):
        meses_adicionales: int


    class SexoEnum(str, Enum):
        masculino = "masculino"
        femenino = "femenino"
        otro = "otro"


    class CondicionSalud(BaseModel):
        nombre: str
        severidad: Optional[str] = None  # leve|moderada|severa
        controlada: Optional[bool] = True
        notas: Optional[str] = None


    class Lesion(BaseModel):
        zona: str
        tipo: str
        fase: Optional[str] = None
        rango_mov_limitado: Optional[List[str]] = []
        notas: Optional[str] = None


    class Medicacion(BaseModel):
        nombre: str
        dosis: Optional[str] = None
        efectos_secundarios: Optional[List[str]] = []


    class PreferenciasUsuario(BaseModel):
        equipamiento: List[str] = []
        lugar: Optional[str] = "casa"
        tiempo_minutos: Optional[int] = 45
        dias_disponibles: Optional[int] = 4
        experiencia: Optional[str] = "intermedio"
        objetivos: List[str] = []
        gustos: List[str] = []
        disgustos: List[str] = []


    class DatosFisicos(BaseModel):
        edad: Optional[int] = None
        sexo: Optional[SexoEnum] = None
        peso_kg: Optional[float] = None
        estatura_cm: Optional[float] = None
        grasa_corporal: Optional[float] = None
        fc_reposo: Optional[int] = None


    class PerfilSalud(BaseModel):
        usuario_id: Optional[int] = None
        datos: DatosFisicos = DatosFisicos()
        condiciones: List[CondicionSalud] = []
        lesiones: List[Lesion] = []
        medicaciones: List[Medicacion] = []
        riesgos: List[str] = []
        preferencias: PreferenciasUsuario = PreferenciasUsuario()


    class EjercicioRutina(BaseModel):
        id_ejercicio: int
        nombre: str
        descripcion: str
        grupo_muscular: str
        dificultad: str
        tipo: str
        series: int
        repeticiones: int
        descanso_segundos: int
        notas: Optional[str] = None


    class DiaRutinaDetallado(BaseModel):
        numero_dia: int
        nombre_dia: str
        descripcion: str
        grupos_enfoque: List[str]
        ejercicios: List[EjercicioRutina]


    class RutinaCompleta(BaseModel):
        nombre: str
        descripcion: str
        id_cliente: int
        objetivo: str
        grupo_muscular: str
        nivel: str
        dias_semana: int
        total_ejercicios: int
        minutos_aproximados: int
        duracion_meses: int  # NUEVO: Duración en meses
        fecha_inicio_vigencia: Optional[str] = None  # NUEVO: Fecha inicio
        fecha_fin_vigencia: Optional[str] = None  # NUEVO: Fecha fin
        estado_vigencia: str = "pendiente"  # NUEVO: Estado
        dias: List[DiaRutinaDetallado]
        fecha_creacion: str
        generada_por: str


    class SeguridadOut(BaseModel):
        nivel_riesgo: str  # "bajo" | "moderado" | "alto"
        detonantes_evitar: List[str] = []
        advertencias: List[str] = []
        validada_por_reglas: bool = False


    class SolicitudGenerarRutina(BaseModel):
        id_cliente: int
        objetivos: str
        dias: int = Field(..., ge=2, le=7, description="Días de entrenamiento por semana (2-7)")
        nivel: str  # "principiante" | "intermedio" | "avanzado"
        grupo_muscular_foco: Optional[str] = "general"
        perfil_salud: Optional[PerfilSalud] = None
        proveedor: Literal["auto", "gemini", "openai", "grok", "local"] = "auto"
        duracion_meses: int = Field(
            default=1,
            ge=1,
            le=12,
            description="Duración de la rutina en meses (1-12)"
        )  # NUEVO

        @field_validator('duracion_meses')
        def validar_duracion(cls, v):
            if v < 1 or v > 12:
                raise ValueError('La duración debe estar entre 1 y 12 meses')
            return v


    # ============================================================
    # PLANES (fallback local)
    # ============================================================

    PLANES_DISTRIBUCION = {
        2: [["PECHO", "BRAZOS"], ["ESPALDA", "PIERNAS"]],
        3: [["PECHO", "HOMBROS"], ["ESPALDA", "BRAZOS"], ["PIERNAS", "CORE"]],
        4: [["PECHO", "TRÍCEPS"], ["ESPALDA", "BÍCEPS"], ["PIERNAS", "CORE"], ["HOMBROS", "CARDIO"]],
        5: [["PECHO", "TRÍCEPS"], ["ESPALDA", "BÍCEPS"], ["PIERNAS"], ["HOMBROS"], ["CARDIO", "CORE"]],
        6: [["PECHO"], ["ESPALDA"], ["BRAZOS"], ["PIERNAS"], ["HOMBROS"], ["CARDIO", "CORE"]],
        7: [["PECHO"], ["ESPALDA"], ["BRAZOS"], ["PIERNAS"], ["HOMBROS"], ["CARDIO"], ["CORE", "DESCANSO"]],
    }

    MAPEO_GRUPOS_SECUNDARIOS = {
        "TRÍCEPS": "BRAZOS",
        "BÍCEPS": "BRAZOS",
        "ANTEBRAZO": "BRAZOS",
        "GEMELOS": "PIERNAS",
        "CUÁDRICEPS": "PIERNAS",
        "ISQUIOTIBIALES": "PIERNAS",
        "ADUCTORES": "PIERNAS",
        "GLÚTEOS": "PIERNAS",
    }

    # ============================================================
    # REGLAS DE SEGURIDAD
    # ============================================================

    CONTRAINDICACIONES = {
        "hipertensión": {
            "evitar_tags": ["valsalva", "isometria_larga", "hiit_alto_impacto", "cargas_maximas"],
            "advertencias": ["Evitar maniobra de Valsalva y picos de intensidad altos."]
        },
        "lumbalgia crónica": {
            "evitar_tags": ["carga_compresiva_lumbar_alta", "hiperextension_lumbar", "rotacion_lumbar"],
            "advertencias": ["Preferir neutro lumbar y anti-rotación."]
        },
        "lesion_hombro": {
            "evitar_tags": ["press_por_encima", "abduccion_90_mas", "rotacion_externa_cargada"],
            "advertencias": ["Limitar ROM doloroso y cargas overhead."]
        },
        "diabetes tipo 2": {
            "evitar_tags": [],
            "advertencias": ["Control glucemia y snack si sesión >60 min."]
        },
    }

    # Prioridad para glúteos (coincidencias por nombre/desc)
    PRIORIDAD_GLUTEOS = [
        "hip thrust", "empuje de cadera", "puente de glúteo", "glute bridge",
        "peso muerto rumano", "pmr", "romano", "rdl",
        "sentadilla sumo", "sumo", "sentadilla", "squat",
        "zancadas", "estocadas", "lunge", "bulgara", "búlgaras",
        "step up", "subida al banco",
        "abduccion", "abducción", "patada", "kickback", "monster walk", "frog pump"
    ]

    # Equipamiento que NO debes usar "en casa" si no hay equipo declarado
    PALABRAS_MAQUINAS_GYM = ["máquina", "prensa", "polea", "cable", "smith", "hack", "leg press", "prensa 45"]
    PALABRAS_BARRA = ["barra", "barbell"]

    # === Selector de modelo robusto para Google Generative AI ===
    PREFERRED_MODELS = [
        "models/gemini-2.5-flash",
        "models/gemini-2.5-pro",
        "models/gemini-1.5-flash-002",
        "models/gemini-1.5-pro-002"
    ]
    FALLBACK_LIGHT_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "models/gemini-2.5-flash")


    # ============================================================
    # FUNCIONES DE VIGENCIA - NUEVO
    # ============================================================

    def calcular_fechas_vigencia(meses: int) -> dict:
        """
        Calcula fechas de inicio y fin de vigencia usando tu estructura real.
        """
        inicio = datetime.now()
        fin = inicio + timedelta(days=meses * 30)  # Aproximación estándar

        return {
            "inicio": inicio,
            "fin": fin,
            "dias_totales": (fin - inicio).days
        }


    def obtener_estado_vigencia(fecha_fin: datetime, fecha_inicio: Optional[datetime] = None) -> dict:
        """
        Devuelve estado: activa | por_vencer | vencida.
        """
        ahora = datetime.now()
        dias_restantes = (fecha_fin - ahora).days

        if dias_restantes < 0:
            estado = "vencida"
        elif dias_restantes <= 7:
            estado = "por_vencer"
        else:
            estado = "activa"

        porcentaje = 0.0
        if fecha_inicio:
            total = (fecha_fin - fecha_inicio).days
            avance = (ahora - fecha_inicio).days
            if total > 0:
                porcentaje = min(100, max(0, (avance / total) * 100))

        return {
            "estado": estado,
            "dias_restantes": max(0, dias_restantes),
            "porcentaje_completado": round(porcentaje, 2)
        }
    # ============================================================
    # VERIFICACIÓN RÁPIDA DE RUTINAS EXISTENTES
    # ============================================================

    def rutina_existe(db: Session, id_rutina: int) -> bool:
        res = db.execute(text("SELECT id_rutina FROM rutinas WHERE id_rutina = :id"),
                         {"id": id_rutina}).fetchone()
        return res is not None


    def actualizar_estado_rutina(db: Session, id_rutina: int):
        """
        Sincroniza estado_vigencia automáticamente según fechas.
        Útil si se llama al consultar el dashboard.
        """

        q = text("""
            SELECT fecha_inicio_vigencia, fecha_fin_vigencia
            FROM rutinas WHERE id_rutina = :id
        """)
        row = db.execute(q, {"id": id_rutina}).fetchone()

        if not row:
            return

        inicio, fin = row
        if not inicio or not fin:
            return

        estado_new = obtener_estado_vigencia(fin, inicio)["estado"]

        upd = text("""
            UPDATE rutinas
            SET estado_vigencia = :e
            WHERE id_rutina = :id
        """)

        db.execute(upd, {"e": estado_new, "id": id_rutina})
        db.commit()

    def guardar_dias_rutina(db: Session, id_rutina: int, dias_json: dict):
        """
        Guarda contenido_dias: JSON completo de la IA.
        """
        q = text("""
            UPDATE rutinas
            SET contenido_dias = :dias
            WHERE id_rutina = :id
        """)

        db.execute(q, {
            "dias": json.dumps(dias_json),
            "id": id_rutina
        })
        db.commit()

    # ============================================================
    # HELPER PARA GUARDAR REGISTROS EN HISTORIAL
    # ============================================================

    def registrar_historial_rutina(db: Session, id_rutina: int, id_cliente: int, id_entrenador: int):
        """
        Guarda en la tabla historial_rutinas un snapshot básico
        cuando la rutina es generada.
        """

        q = text("""
            INSERT INTO historial_rutinas (
                id_rutina, id_cliente, id_entrenador,
                fecha_inicio, estado, created_at
            )
            VALUES (:r, :c, :e, NOW(), 'activa', NOW())
        """)

        db.execute(q, {
            "r": id_rutina,
            "c": id_cliente,
            "e": id_entrenador
        })
        db.commit()

    # ============================================================
    # HELPER PARA FORMATEAR RESPUESTA DE RUTINA GENERADA
    # ============================================================

    def respuesta_rutina_generada(rutina, seguridad, vigencia_info):
        """
        Arma un JSON unificado estándar para enviar al frontend Angular.
        """

        return {
            "id_rutina": rutina["id_rutina"],
            "nombre": rutina["nombre"],
            "descripcion": rutina["descripcion"],
            "dias_semana": rutina["dias_semana"],
            "total_ejercicios": rutina["total_ejercicios"],
            "minutos_aproximados": rutina["minutos_aproximados"],
            "nivel": rutina["nivel"],
            "grupo_muscular": rutina["grupo_muscular"],
            "generada_por": rutina["generada_por"],
            "fecha_creacion": rutina["fecha_creacion"],

            "seguridad": seguridad,
            "vigencia": {
                "duracion_meses": rutina["duracion_meses"],
                "fecha_inicio": vigencia_info.get("inicio"),
                "fecha_fin": vigencia_info.get("fin"),
                "dias_restantes": vigencia_info.get("dias_restantes"),
                "estado": vigencia_info.get("estado"),
                "porcentaje_completado": vigencia_info.get("porcentaje_completado")
            }
        }

    # ============================================================
    # HELPER FUNCTIONS - DETECCIÓN DE ERRORES
    # ============================================================
    def guardar_rutina_bd(db, base_rutina):
        """
        Guarda la rutina generada por IA dentro de la tabla 'rutinas'.
        Retorna el id_rutina generado.
        """

        query = text("""
            INSERT INTO rutinas (
                nombre, descripcion, creado_por,
                objetivo, grupo_muscular, nivel,
                dias_semana, total_ejercicios, minutos_aproximados,
                generada_por, duracion_meses,
                fecha_inicio_vigencia, fecha_fin_vigencia,
                estado_vigencia, contenido_dias
            )
            VALUES (
                :nombre, :descripcion, :creado_por,
                :objetivo, :grupo_muscular, :nivel,
                :dias_semana, :total_ejercicios, :minutos_aprox,
                :generada_por, :duracion_meses,
                :fecha_inicio_vigencia, :fecha_fin_vigencia,
                :estado_vigencia, :contenido_dias
            )
        """)

        db.execute(query, {
            "nombre": base_rutina.nombre,
            "descripcion": base_rutina.descripcion,
            "creado_por": base_rutina.id_cliente,
            "objetivo": base_rutina.objetivo,
            "grupo_muscular": base_rutina.grupo_muscular,
            "nivel": base_rutina.nivel,
            "dias_semana": base_rutina.dias_semana,
            "total_ejercicios": base_rutina.total_ejercicios,
            "minutos_aprox": base_rutina.minutos_aproximados,
            "generada_por": base_rutina.generada_por,
            "duracion_meses": base_rutina.duracion_meses,
            "fecha_inicio_vigencia": base_rutina.fecha_inicio_vigencia,
            "fecha_fin_vigencia": base_rutina.fecha_fin_vigencia,
            "estado_vigencia": base_rutina.estado_vigencia,
            "contenido_dias": json.dumps([d.model_dump() for d in base_rutina.dias])
        })

        db.commit()
        return db.execute(text("SELECT LAST_INSERT_ID()")).scalar()


    def guardar_ejercicios_rutina(db, id_rutina, dias):
        """
        Guarda los ejercicios de todos los días de la rutina
        en la tabla 'rutina_ejercicios'
        """
        for dia in dias:
            for ej in dia.ejercicios:
                db.execute(text("""
                    INSERT INTO rutina_ejercicios (
                        id_rutina, id_ejercicio, series,
                        repeticiones, descanso_segundos
                    )
                    VALUES (:rutina, :ejercicio, :series, :reps, :descanso)
                """), {
                    "rutina": id_rutina,
                    "ejercicio": ej.id_ejercicio,
                    "series": ej.series,
                    "reps": ej.repeticiones,
                    "descanso": ej.descanso_segundos
                })
        db.commit()


    def crear_historial_rutina(db, id_rutina, base):
        """
        Crea registro en historial_rutinas
        """
        query = text("""
            INSERT INTO historial_rutinas (
                id_rutina, id_cliente, nombre_rutina,
                fecha_inicio, fecha_fin, estado,
                total_ejercicios, nivel, objetivo, dias_semana
            )
            VALUES (
                :rutina, :cliente, :nombre,
                NOW(), DATE_ADD(NOW(), INTERVAL :meses MONTH), 'activa',
                :total_ejercicios, :nivel, :objetivo, :dias_semana
            )
        """)

        db.execute(query, {
            "rutina": id_rutina,
            "cliente": base.id_cliente,
            "nombre": base.nombre,
            "meses": base.duracion_meses,
            "total_ejercicios": base.total_ejercicios,
            "nivel": base.nivel,
            "objetivo": base.objetivo,
            "dias_semana": base.dias_semana
        })

        db.commit()
        return db.execute(text("SELECT LAST_INSERT_ID()")).scalar()


    def copiar_ejercicios_historial(db, id_historial, id_rutina):
        """
        Copia ejercicios desde rutina_ejercicios a historial_rutina_ejercicios
        """
        query = text("""
            INSERT INTO historial_rutina_ejercicios (
                id_historial, id_ejercicio, series, repeticiones, descanso_segundos
            )
            SELECT :historial, id_ejercicio, series, repeticiones, descanso_segundos
            FROM rutina_ejercicios
            WHERE id_rutina = :rutina
        """)
        db.execute(query, {"historial": id_historial, "rutina": id_rutina})
        db.commit()


    def crear_objetivos_iniciales(db, id_cliente, id_rutina):
        """
        Crea objetivos automáticos basados en una rutina nueva
        """
        query = text("""
            INSERT INTO objetivos_cliente (
                id_cliente, tipo_objetivo, titulo,
                valor_objetivo, valor_actual, unidad,
                estado, porcentaje_completado, fecha_inicio, fecha_limite
            )
            VALUES (
                :cliente, 'progreso', 'Completar rutina',
                100, 0, '%',
                'pendiente', 0,
                NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)
            )
        """)
        db.execute(query, {"cliente": id_cliente})
        db.commit()


    def crear_alertas_iniciales(db, id_cliente):
        """
        Crea alerta inicial cuando se asigna rutina
        """
        db.execute(text("""
            INSERT INTO alertas_progresion (
                id_cliente, tipo_alerta, prioridad,
                titulo, mensaje
            )
            VALUES (
                :cliente, 'nueva_rutina', 'media',
                'Nueva rutina asignada',
                'Se ha asignado una nueva rutina al cliente'
            )
        """), {"cliente": id_cliente})
        db.commit()

    def _is_quota_error(err: Exception) -> bool:
        msg = f"{type(err).__name__}: {err}"
        m = msg.lower()
        return (
                "resourceexhausted" in m or
                "quota" in m or
                ("rate" in m and "limit" in m) or
                "429" in m or
                "generativelanguage.googleapis.com" in m
        )


    def _supports_generate_content(m) -> bool:
        try:
            methods = getattr(m, "supported_generation_methods", []) or getattr(m, "generation_methods", [])
            return "generateContent" in methods or "generate_content" in methods
        except Exception:
            return False


    def _normalize_model_name(name: str) -> str:
        return name.split("/")[-1] if name and "/" in name else name


    def _select_gemini_model() -> str:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY no configurada")

        # Prioridad exacta de modelos válidos del SDK
        valid_models = [
            "models/gemini-2.5-pro",
            "models/gemini-2.5-flash",
            "models/gemini-1.5-pro-002",
            "models/gemini-1.5-flash-002",
        ]

        wanted = os.getenv("GEMINI_MODEL")

        # Si usuario pide uno específico y es válido
        if wanted in valid_models:
            return wanted

        # Si no, usar el primero disponible
        return valid_models[0]



    # ============================================================
    # HELPER FUNCTIONS - SEGURIDAD Y FILTROS
    # ============================================================

    def perf_to_riesgo(perfil: Optional[PerfilSalud]) -> SeguridadOut:
        if not perfil:
            return SeguridadOut(nivel_riesgo="bajo", validada_por_reglas=True)
        detonantes, advertencias, riesgo = set(), [], "bajo"
        for c in perfil.condiciones:
            key = c.nombre.lower()
            if key in CONTRAINDICACIONES:
                detonantes.update(CONTRAINDICACIONES[key]["evitar_tags"])
                advertencias.extend(CONTRAINDICACIONES[key]["advertencias"])
                if (c.severidad and c.severidad.lower() in ["moderada", "severa"]) or (c.controlada is False):
                    riesgo = "moderado" if riesgo == "bajo" else "alto"
        for l in perfil.lesiones:
            if l.zona.lower() == "hombro":
                detonantes.update(CONTRAINDICACIONES["lesion_hombro"]["evitar_tags"])
                advertencias.extend(CONTRAINDICACIONES["lesion_hombro"]["advertencias"])
                riesgo = "moderado" if riesgo == "bajo" else "alto"
            if l.zona.lower() in ["lumbar", "espalda baja"]:
                detonantes.update(CONTRAINDICACIONES["lumbalgia crónica"]["evitar_tags"])
                advertencias.extend(CONTRAINDICACIONES["lumbalgia crónica"]["advertencias"])
                riesgo = "moderado" if riesgo == "bajo" else "alto"
        if "embarazo" in [r.lower() for r in perfil.riesgos]:
            detonantes.update(["impacto_alto", "supino_prolongado", "valsalva"])
            advertencias.append("Evitar supino prolongado y alto impacto durante el embarazo.")

        return SeguridadOut(
            nivel_riesgo=riesgo,
            detonantes_evitar=list(detonantes),
            advertencias=advertencias,
            validada_por_reglas=True
        )


    def validar_filtrar_ejercicios(perfil: Optional[PerfilSalud], ejercicios: List[Dict[str, Any]]) -> (
            List[Dict[str, Any]], SeguridadOut):
        seg = perf_to_riesgo(perfil)
        if not seg.detonantes_evitar:
            return ejercicios, seg

        filtrados = []
        for ej in ejercicios:
            tags_ej = (ej.get("tags") or []) if isinstance(ej.get("tags"), list) else []
            if not any(t in tags_ej for t in seg.detonantes_evitar):
                filtrados.append(ej)

        return filtrados, seg


    def _es_casa_sin_equipo(pref: Optional[PreferenciasUsuario]) -> bool:
        if not pref:
            return False
        return (pref.lugar or "").lower() == "casa" and not pref.equipamiento


    def _descarta_por_equipo_si_casa_sin_equipo(ej: Dict[str, Any]) -> bool:
        t = (ej.get("nombre", "") + " " + ej.get("descripcion", "") + " " + ej.get("tipo", "")).lower()
        if any(p in t for p in PALABRAS_MAQUINAS_GYM): return True
        if any(p in t for p in PALABRAS_BARRA): return True
        return False


    def _score_prioridad_gluteo(ej: Dict[str, Any]) -> int:
        """Mayor score = más glúteo."""
        t = (ej.get("nombre", "") + " " + ej.get("descripcion", "")).lower()
        s = 0
        for kw in PRIORIDAD_GLUTEOS:
            if kw in t: s += 2
        if "glúteo" in t or (ej.get("grupo_muscular", "").upper() in ["PIERNAS", "GLÚTEOS"]):
            s += 1
        return s


    def _objetivo_es_gluteos(objetivo: str, foco: Optional[str]) -> bool:
        txt = (objetivo or "").lower() + " " + (foco or "").lower()
        return ("glute" in txt) or ("glúte" in txt)


    def _split_por_objetivo(dias: int, objetivos: str, foco: Optional[str]) -> List[List[str]]:
        """
        Devuelve un split preferente si el objetivo es glúteos.
        Si no detecta glúteos, usa los planes genéricos.
        """
        txt = (objetivos or "").lower() + " " + (foco or "")
        es_gluteo = ("glute" in txt) or ("glúte" in txt)

        if not es_gluteo:
            return PLANES_DISTRIBUCION.get(dias, PLANES_DISTRIBUCION[4])

        presets = {
            3: [["GLÚTEOS/PIERNAS"], ["UPPER LIGERO"], ["GLÚTEOS/PIERNAS"]],
            4: [["GLÚTEOS/QUADS"], ["UPPER LIGERO"], ["GLÚTEOS/ISQUIOS"], ["CORE/CARDIO SUAVE"]],
            5: [["GLÚTEOS/QUADS"], ["UPPER LIGERO"], ["GLÚTEOS/ISQUIOS"], ["CORE/ESTABILIDAD"], ["GLÚTEOS (AISLAMIENTOS)"]],
            6: [["GLÚTEOS/QUADS"], ["UPPER LIGERO"], ["GLÚTEOS/ISQUIOS"], ["UPPER LIGERO"], ["GLÚTEOS (AISLAMIENTOS)"],
                ["CORE/CARDIO"]],
            7: [["GLÚTEOS/QUADS"], ["UPPER LIGERO"], ["GLÚTEOS/ISQUIOS"], ["CORE"], ["GLÚTEOS (AISLAMIENTOS)"],
                ["UPPER LIGERO"], ["DESCANSO"]],
        }

        if dias in presets:
            return presets[dias]
        if dias < 3:
            return presets[3]
        if dias > 7:
            return presets[7]
        return PLANES_DISTRIBUCION.get(dias, PLANES_DISTRIBUCION[4])


    # ============================================================
    # FALLBACK LOCAL (consulta BD + distribución)
    # ============================================================

    def obtener_ejercicios_por_grupo(db: Session, nivel: str) -> Dict[str, List[Dict[str, Any]]]:
        print(f"\n🔍 Buscando ejercicios para nivel: {nivel}")
        grupos = ["PECHO", "ESPALDA", "BRAZOS", "PIERNAS", "HOMBROS", "CORE", "CARDIO"]
        out: Dict[str, List[Dict[str, Any]]] = {}
        for g in grupos:
            q = text("""
                SELECT id_ejercicio, nombre, descripcion, grupo_muscular, dificultad, tipo
                FROM ejercicios
                WHERE grupo_muscular = :grupo AND dificultad = :nivel
                LIMIT 100
            """)
            res = db.execute(q, {"grupo": g, "nivel": nivel}).fetchall()
            if not res:
                q2 = text("""
                    SELECT id_ejercicio, nombre, descripcion, grupo_muscular, dificultad, tipo
                    FROM ejercicios
                    WHERE grupo_muscular = :grupo
                    ORDER BY dificultad ASC
                    LIMIT 100
                """)
                res = db.execute(q2, {"grupo": g}).fetchall()
            out[g] = [{
                "id_ejercicio": r[0], "nombre": r[1], "descripcion": r[2] or "", "grupo_muscular": r[3],
                "dificultad": r[4], "tipo": r[5] or "general"
            } for r in res]
        return out


    def distribuir_ejercicios_inteligente(
            ejercicios_por_grupo: Dict[str, List[Dict[str, Any]]],
            dias_semana: int,
            nivel: str,
            objetivo: str,
            perfil: Optional[PerfilSalud] = None
    ) -> (List[DiaRutinaDetallado], SeguridadOut):
        """
        Fallback local mejorado:
        - Split adaptado al objetivo (glúteos) con _split_por_objetivo
        - Filtro por salud (contraindicaciones)
        - Filtro por "casa sin equipo"
        - Priorización de ejercicios de glúteo por score
        - Evita duplicados dentro del día
        """
        dias: List[DiaRutinaDetallado] = []
        nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        plan = _split_por_objetivo(dias_semana, objetivo, None)

        idxs = {g: 0 for g in ejercicios_por_grupo.keys()}
        advertencias: List[str] = []
        casa_sin_equipo = _es_casa_sin_equipo(perfil.preferencias if perfil else None)

        def expandir_grupo(alias: str) -> List[str]:
            a = alias.upper()
            if "UPPER" in a:
                return ["PECHO", "ESPALDA", "HOMBROS", "BRAZOS"]
            if "GLÚTEOS" in a or "GLUTEOS" in a or "GLUTE" in a:
                return ["PIERNAS"]
            if "CORE" in a:
                return ["CORE"]
            if "CARDIO" in a:
                return ["CARDIO"]
            if "DESCANSO" in a:
                return ["DESCANSO"]
            return [a]

        for i, grupos in enumerate(plan):
            nombre_dia = nombres[i] if i < len(nombres) else f"Día {i + 1}"
            grupos_norm: List[str] = []
            for g in grupos:
                partes = [p.strip() for p in g.replace("/", ",").split(",")]
                for p in partes:
                    grupos_norm.extend(expandir_grupo(p))

            activos = [g for g in grupos_norm if g != "DESCANSO"]
            n_por_grupo = max(2, 6 // max(1, len(activos)))

            ej_del_dia: List[EjercicioRutina] = []
            usados: set = set()

            for g in grupos_norm:
                if g == "DESCANSO":
                    continue

                g_pri = MAPEO_GRUPOS_SECUNDARIOS.get(g, g)
                pool = list(ejercicios_por_grupo.get(g_pri, []))

                pool, seg_local = validar_filtrar_ejercicios(perfil, pool)
                if seg_local.advertencias:
                    advertencias.extend([f"{nombre_dia}/{g}: {a}" for a in seg_local.advertencias])

                if casa_sin_equipo:
                    pool = [e for e in pool if not _descarta_por_equipo_si_casa_sin_equipo(e)]

                if _objetivo_es_gluteos(objetivo, "gluteo"):
                    pool.sort(key=_score_prioridad_gluteo, reverse=True)

                obtenidos = 0
                intentos = 0
                while obtenidos < n_por_grupo and pool and intentos < len(pool) * 2:
                    idx = idxs.get(g_pri, 0) % len(pool)
                    c = pool[idx]
                    idxs[g_pri] = idx + 1
                    intentos += 1

                    clave = (c["id_ejercicio"], c["nombre"])
                    if clave in usados:
                        continue
                    usados.add(clave)

                    ej_del_dia.append(EjercicioRutina(
                        id_ejercicio=c["id_ejercicio"],
                        nombre=c["nombre"],
                        descripcion=c["descripcion"],
                        grupo_muscular=c["grupo_muscular"],
                        dificultad=c["dificultad"],
                        tipo=c["tipo"],
                        series=3 if nivel == "PRINCIPIANTE" else 4,
                        repeticiones=12 if nivel == "PRINCIPIANTE" else 10,
                        descanso_segundos=90 if nivel == "PRINCIPIANTE" else 75,
                        notas=(f"Prioridad glúteos" if _objetivo_es_gluteos(objetivo, "gluteo") and _score_prioridad_gluteo(
                            c) > 2 else None)
                    ))
                    obtenidos += 1

            dias.append(DiaRutinaDetallado(
                numero_dia=i + 1,
                nombre_dia=nombre_dia,
                descripcion=f"Enfoque: {', '.join(grupos)}",
                grupos_enfoque=grupos,
                ejercicios=ej_del_dia
            ))

        seg_global = perf_to_riesgo(perfil)
        seguridad = SeguridadOut(
            nivel_riesgo=seg_global.nivel_riesgo,
            detonantes_evitar=seg_global.detonantes_evitar,
            advertencias=advertencias,
            validada_por_reglas=(len(advertencias) == 0)
        )
        return dias, seguridad


    def calcular_minutos_rutina(dias: List[DiaRutinaDetallado]) -> int:
        minutos_total = 0
        for d in dias:
            m = 0
            for ej in d.ejercicios:
                m += (ej.series * ej.repeticiones * 3) + (ej.descanso_segundos * (ej.series - 1))
            minutos_total += m // 60
        return max(30, minutos_total // len(dias)) if dias else 45


    # ============================================================
    # PROMPT BUILDER
    # ============================================================

    def _build_ai_prompt(perfil: Optional[PerfilSalud], dias: int, nivel: str, objetivos: str) -> str:
        p = perfil or PerfilSalud()
        pref = p.preferencias
        home = (pref.lugar or "").lower() == "casa"
        no_equipo = not pref.equipamiento

        requisitos = [f"Nivel: {nivel}", f"Objetivo: {objetivos}", f"{dias} días/semana"]

        if home and no_equipo:
            requisitos.append("Casa sin equipo (peso corporal/bandas)")
        elif home and pref.equipamiento:
            requisitos.append(f"Equipo: {', '.join(pref.equipamiento[:3])}")

        perfil_items = []
        if p.datos.edad:
            perfil_items.append(f"Edad: {p.datos.edad}")
        if p.condiciones:
            perfil_items.append(f"Condiciones: {', '.join([c.nombre for c in p.condiciones[:2]])}")
        if p.lesiones:
            perfil_items.append(f"Lesiones: {', '.join([l.zona for l in p.lesiones[:2]])}")

        perfil_text = ". ".join(perfil_items) if perfil_items else "Sin restricciones"

        return f"""Crea rutina de {dias} días en JSON.
    
    Requisitos: {' | '.join(requisitos)}
    Usuario: {perfil_text}
    
    JSON (5-6 ejercicios/día):
    {{
      "nombre": "Rutina {nivel} {dias}d",
      "descripcion": "Enfoque {objetivos}",
      "dias_semana": {dias},
      "minutos_aproximados": {pref.tiempo_minutos or 45},
      "dias": [
        {{
          "numero_dia": 1,
          "nombre_dia": "Lunes",
          "descripcion": "Push",
          "grupos_enfoque": ["PECHO","HOMBROS"],
          "ejercicios": [
            {{
              "id_ejercicio": 0,
              "nombre": "Press banca",
              "descripcion": "Pecho completo",
              "grupo_muscular": "PECHO",
              "dificultad": "{nivel}",
              "tipo": "fuerza",
              "series": 4,
              "repeticiones": 10,
              "descanso_segundos": 75,
              "notas": null
            }}
          ]
        }}
      ]
    }}
    
    IMPORTANTE: series, repeticiones y descanso_segundos deben ser NÚMEROS ENTEROS (ej: 10, NO "10-15").
    SOLO JSON válido. Sin texto extra."""


    # ============================================================
    # AI GENERATORS (GEMINI + OPENAI + GROK) - CON TIMEOUT
    # ============================================================

    def _resp_to_text(resp) -> str:
        """
        Extrae el texto de una respuesta de Gemini.
        Incluye DEBUG del finish_reason, safety y candidates.
        """

        # ===== DEBUG DE CANDIDATES =====
        try:
            finish_reason = None
            prompt_feedback = None

            if hasattr(resp, "candidates") and resp.candidates:
                finish_reason = getattr(resp.candidates[0], "finish_reason", None)
                prompt_feedback = getattr(resp, "prompt_feedback", None)

                if finish_reason is not None and finish_reason != 1:
                    print("⚠️ DEBUG GEMINI — FINISH_REASON INVALIDO ⚠️")
                    print("finish_reason:", finish_reason)
                    print("prompt_feedback:", prompt_feedback)
                    print("candidates:", resp.candidates)

        except Exception as dbg:
            print("Error debug finish_reason:", dbg)

        # ===== 1) Intento directo =====
        try:
            if hasattr(resp, "text") and resp.text:
                return resp.text
        except:
            pass

        # ===== 2) Intento en candidates[].content.parts[].text =====
        try:
            cands = getattr(resp, "candidates", [])
            if cands:
                content = getattr(cands[0], "content", None)
                if content:
                    parts = getattr(content, "parts", [])
                    textos = []
                    for p in parts:
                        t = getattr(p, "text", None)
                        if t:
                            textos.append(t)
                    if textos:
                        return "\n".join(textos)
        except:
            pass

        # ===== 3) Intento con resp.to_dict() =====
        try:
            d = resp.to_dict()
            raw = json.dumps(d)
            match = re.search(r'"text"\s*:\s*"(.+?)"', raw)
            if match:
                return match.group(1)
            return raw
        except:
            pass

        # ===== 4) Último recurso =====
        return str(resp)


    def _gemini_generate_plan(perfil: Optional[PerfilSalud], dias: int, nivel: str, objetivos: str) -> Dict[str, Any]:
        """
        Genera un plan de entrenamiento usando Gemini AI con timeout configurado.
        """
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY no configurada")

        prompt = _build_ai_prompt(perfil, dias, nivel, objetivos)

        max_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "4096"))

        generation_config = {
            "response_mime_type": "application/json",
            "temperature": 0.2,
            "max_output_tokens": max_tokens
        }

        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_ONLY_HIGH"
            }
        ]

        request_options = {
            "timeout": GEMINI_TIMEOUT_SECONDS
        }

        last_err = None
        tried_models = []

        try:
            selected_model = _normalize_model_name(GEMINI_MODEL)
            tried_models.append(selected_model)
            model = genai.GenerativeModel(selected_model)

            try:
                resp = model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                    request_options=request_options
                )
            except TypeError:
                try:
                    resp = model.generate_content(
                        [prompt],
                        generation_config=generation_config,
                        safety_settings=safety_settings,
                        request_options=request_options
                    )
                except TypeError:
                    try:
                        resp = model.generate_content(
                            [prompt],
                            generation_config=generation_config,
                            safety_settings=safety_settings
                        )
                    except TypeError:
                        resp = model.generate_content([prompt], generation_config=generation_config)

            raw = _resp_to_text(resp)
            if not raw:
                pf = getattr(resp, "prompt_feedback", None)
                raise RuntimeError(f"Gemini devolvió vacío. prompt_feedback={pf}")

            try:
                return json.loads(raw)
            except Exception:
                m = re.search(r"\{[\s\S]*\}", raw)
                if not m:
                    raise ValueError(f"Gemini no devolvió JSON válido. raw (400): {raw[:400]}...")
                return json.loads(m.group(0))


        except Exception as e:

            print("🔴 GEMINI ERROR DETECTADO 🔴")

            print("Tipo:", type(e).__name__)

            print("Mensaje:", str(e))

            # Log de respuesta cruda

            try:

                print("Raw Response:", resp)

            except Exception:

                print("❌ No hay RAW response")

            last_err = e

            if not _is_quota_error(e):
                raise RuntimeError(

                    f"Fallo en _gemini_generate_plan: {type(e).__name__}: {str(e)} "
    
                    f"(modelos probados: {tried_models})"

                )

        try:
            light_model = FALLBACK_LIGHT_MODEL
            tried_models.append(light_model)
            model = genai.GenerativeModel(light_model)

            try:
                resp = model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                    request_options=request_options
                )
            except TypeError:
                try:
                    resp = model.generate_content(
                        [prompt],
                        generation_config=generation_config,
                        safety_settings=safety_settings,
                        request_options=request_options
                    )
                except TypeError:
                    try:
                        resp = model.generate_content(
                            [prompt],
                            generation_config=generation_config,
                            safety_settings=safety_settings
                        )
                    except TypeError:
                        resp = model.generate_content([prompt], generation_config=generation_config)

            raw = _resp_to_text(resp)
            if not raw:
                raise RuntimeError("Gemini (flash) devolvió vacío.")

            try:
                return json.loads(raw)
            except Exception:
                m = re.search(r"\{[\s\S]*\}", raw)
                if not m:
                    raise ValueError("Gemini (flash) no devolvió JSON válido.")
                return json.loads(m.group(0))

        except Exception:
            raise RuntimeError(
                f"Fallo en _gemini_generate_plan: {type(last_err).__name__}: {str(last_err)} "
                f"(modelos probados: {tried_models})"
            )


    def _openai_generate_plan(perfil: Optional[PerfilSalud], dias: int, nivel: str, objetivos: str) -> Dict[str, Any]:
        """
        Genera plan usando OpenAI ChatGPT API
        """
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY no configurada")

        if not openai_client:
            raise RuntimeError("Cliente OpenAI no disponible. Instala con: pip install openai")

        prompt = _build_ai_prompt(perfil, dias, nivel, objetivos)

        try:
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un entrenador profesional experto en crear rutinas de ejercicio personalizadas. Debes responder ÚNICAMENTE con JSON válido, sin texto adicional."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=2048,
                response_format={"type": "json_object"}
            )

            raw = response.choices[0].message.content
            if not raw:
                raise RuntimeError("OpenAI devolvió respuesta vacía")

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                m = re.search(r"\{[\s\S]*\}", raw)
                if not m:
                    raise ValueError(f"OpenAI no devolvió JSON válido. raw (400): {raw[:400]}...")
                return json.loads(m.group(0))

        except Exception as e:
            raise RuntimeError(f"Fallo en _openai_generate_plan: {type(e).__name__}: {str(e)}")


    def _grok_generate_plan(perfil: Optional[PerfilSalud], dias: int, nivel: str, objetivos: str) -> Dict[str, Any]:
        """
        Genera plan usando Grok (xAI) API
        """
        if not GROK_API_KEY:
            raise RuntimeError("GROK_API_KEY no configurada")

        if not grok_client:
            raise RuntimeError("Cliente Grok no disponible. Instala con: pip install openai")

        prompt = _build_ai_prompt(perfil, dias, nivel, objetivos)

        try:
            response = grok_client.chat.completions.create(
                model=GROK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un entrenador profesional experto en crear rutinas de ejercicio personalizadas. Debes responder ÚNICAMENTE con JSON válido, sin texto adicional."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=2048
            )

            raw = response.choices[0].message.content
            if not raw:
                raise RuntimeError("Grok devolvió respuesta vacía")

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                m = re.search(r"\{[\s\S]*\}", raw)
                if not m:
                    raise ValueError(f"Grok no devolvió JSON válido. raw (400): {raw[:400]}...")
                return json.loads(m.group(0))

        except Exception as e:
            raise RuntimeError(f"Fallo en _grok_generate_plan: {type(e).__name__}: {str(e)}")


    # ============================================================
    # CONVERSION FROM AI TO PYDANTIC
    # ============================================================

    def _parse_int_value(value: Any, default: int = 0) -> int:
        """
        Parsea un valor a entero, manejando casos especiales como rangos.
        """
        if value is None or value == "":
            return default

        if isinstance(value, int):
            return value

        value_str = str(value).strip()

        if '-' in value_str:
            parts = value_str.split('-')
            try:
                return int(parts[0].strip())
            except (ValueError, IndexError):
                return default

        for separator in [' a ', ' to ', ' - ']:
            if separator in value_str.lower():
                parts = value_str.lower().split(separator)
                try:
                    return int(parts[0].strip())
                except (ValueError, IndexError):
                    return default

        try:
            import re
            numbers = re.findall(r'\d+', value_str)
            if numbers:
                return int(numbers[0])
            return default
        except (ValueError, TypeError):
            return default


    def _parse_series_reps(value: Any, default: int = 10) -> int:
        """
        Parsea series o repeticiones, con valores por defecto según tipo.
        """
        return _parse_int_value(value, default)


    def _from_ai_to_pydantic(plan: Dict[str, Any], nivel_norm: str, perfil: Optional[PerfilSalud]):
        dias_brutos = plan.get("dias") or plan.get("rutina") or plan.get("dias_rutina") or []

        # Si viene como dict, convertir a lista
        if isinstance(dias_brutos, dict):
            dias_brutos = [dias_brutos]

        # Si sigue vacío, abortar: regresamos []
        if not isinstance(dias_brutos, list):
            print("⚠️ Gemini devolvió formato inesperado para 'dias'")
            return [], SeguridadOut(
                nivel_riesgo="bajo",
                detonantes_evitar=[],
                advertencias=["Formato inválido desde IA"],
                validada_por_reglas=False
            )

        dias_py: List[DiaRutinaDetallado] = []
        advertencias: List[str] = []

        for idx, d in enumerate(dias_brutos, start=1):
            ejercicios_in = d.get("ejercicios") or []

            # Ejercicios puede venir como dict o null
            if isinstance(ejercicios_in, dict):
                ejercicios_in = [ejercicios_in]
            if ejercicios_in is None:
                ejercicios_in = []

            # Filtrar por seguridad
            ejercicios_filtrados, seg_local = validar_filtrar_ejercicios(perfil, ejercicios_in)
            if seg_local.advertencias:
                advertencias.extend(seg_local.advertencias)

            ejercicios_out = []
            for e in ejercicios_filtrados:
                # Intentar obtener ID, contemplando variantes
                id_ej = (
                    _parse_int_value(e.get("id_ejercicio")) or
                    _parse_int_value(e.get("idEjercicio")) or
                    _parse_int_value(e.get("idd_ejercicio")) or
                    0
                )

                ejercicios_out.append(
                    EjercicioRutina(
                        id_ejercicio=id_ej,
                        nombre=str(e.get("nombre") or "Ejercicio sin nombre"),
                        descripcion=str(e.get("descripcion") or ""),
                        grupo_muscular=str(e.get("grupo_muscular") or "GENERAL").upper(),
                        dificultad=str(e.get("dificultad") or nivel_norm),
                        tipo=str(e.get("tipo") or "general"),
                        series=_parse_int_value(e.get("series"), 3),
                        repeticiones=_parse_int_value(e.get("repeticiones"), 10),
                        descanso_segundos=_parse_int_value(e.get("descanso_segundos"), 60),
                        notas=e.get("notas")
                    )
                )

            # Construir día válido
            dias_py.append(
                DiaRutinaDetallado(
                    numero_dia=d.get("numero_dia", idx),
                    nombre_dia=d.get("nombre_dia", f"Día {idx}"),
                    descripcion=d.get("descripcion", ""),
                    grupos_enfoque=[str(g).upper() for g in d.get("grupos_enfoque", [])],
                    ejercicios=ejercicios_out
                )
            )

        seguridad = SeguridadOut(
            nivel_riesgo="bajo",
            detonantes_evitar=[],
            advertencias=advertencias,
            validada_por_reglas=(len(advertencias) == 0)
        )

        return dias_py, seguridad



    # ============================================================
    # ENDPOINTS
    # ============================================================

    @router.post("/generar-rutina", response_model=Dict[str, Any])
    def generar_rutina_distribuida(

        solicitud: SolicitudGenerarRutina,
        db: Session = Depends(get_db),
        activar_vigencia: bool = Query(False, description="Activar vigencia inmediatamente")
    ):
        """
        Genera rutina con IA, la guarda en BD, crea historial,
        copia ejercicios y crea objetivos + alertas.
        """
        dias = []
        seguridad = None
        generada_por = "local"  # fallback seguro
        descripcion = "Rutina generada localmente"
        try:
            # VALIDACIONES BÁSICAS
            if not (2 <= solicitud.dias <= 7):
                raise HTTPException(status_code=422, detail="Días debe estar entre 2 y 7")

            if not (1 <= solicitud.duracion_meses <= 12):
                raise HTTPException(status_code=422, detail="Duración debe estar entre 1 y 12 meses")

            # MAPEAR NIVEL
            nivel_map = {
                "principiante": "principiante",
                "intermedio": "intermedio",
                "avanzado": "avanzado"
            }
            nivel_norm = nivel_map.get(solicitud.nivel.lower(), "intermedio")
            prov = solicitud.proveedor

            # ======================================================
            # 1) GENERAR LA RUTINA (LOCAL, GEMINI, OPENAI, GROK)
            # ======================================================

            generada_por = "local"
            descripcion = "Rutina generada localmente"

            # LOCAL
            if prov == "local":
                ejercicios_por_grupo = obtener_ejercicios_por_grupo(db, nivel_norm)
                if not any(ejercicios_por_grupo.values()):
                    raise HTTPException(status_code=400, detail="No hay ejercicios disponibles en BD")

                dias, seguridad = distribuir_ejercicios_inteligente(
                    ejercicios_por_grupo,
                    solicitud.dias,
                    nivel_norm,
                    solicitud.objetivos,
                    solicitud.perfil_salud
                )

            # GEMINI
            elif prov == "gemini":
                plan_json = _gemini_generate_plan(
                    perfil=solicitud.perfil_salud,
                    dias=solicitud.dias,
                    nivel=nivel_norm,
                    objetivos=solicitud.objetivos
                )
                # === DEBUG CRÍTICO ===
                print("\n================ RAW GEMINI RESPONSE ================")
                try:
                    print(json.dumps(plan_json, indent=4, ensure_ascii=False))
                except:
                    print(plan_json)
                print("=====================================================\n")

                dias, seguridad = _from_ai_to_pydantic(plan_json, nivel_norm, solicitud.perfil_salud)
                generada_por = "gemini"
                descripcion = "Rutina generada por Gemini IA"

            # OPENAI
            elif prov == "openai":
                plan_json = _openai_generate_plan(
                    perfil=solicitud.perfil_salud,
                    dias=solicitud.dias,
                    nivel=nivel_norm,
                    objetivos=solicitud.objetivos
                )
                dias, seguridad = _from_ai_to_pydantic(plan_json, nivel_norm, solicitud.perfil_salud)
                generada_por = "openai"
                descripcion = "Rutina generada por OpenAI"

            # GROK
            elif prov == "grok":
                plan_json = _grok_generate_plan(
                    perfil=solicitud.perfil_salud,
                    dias=solicitud.dias,
                    nivel=nivel_norm,
                    objetivos=solicitud.objetivos
                )
                dias, seguridad = _from_ai_to_pydantic(plan_json, nivel_norm, solicitud.perfil_salud)
                generada_por = "grok"
                descripcion = "Rutina generada por Grok"

            # ======================================================
            # 2) CALCULAR MINUTOS Y DATOS
            # ======================================================
            # ======================================================
            # Validación crítica: asegurar que 'dias' no esté vacío
            # ======================================================
            if len(dias) == 0:
                print("❌ Gemini no generó días válidos — abortando IA y usando fallback REAL")

                # Usamos el generador local real
                ejercicios_por_grupo = obtener_ejercicios_por_grupo(db, nivel_norm)

                dias, seguridad = distribuir_ejercicios_inteligente(
                    ejercicios_por_grupo,
                    solicitud.dias,
                    nivel_norm,
                    solicitud.objetivos,
                    solicitud.perfil_salud
                )

                generada_por = "local"
                descripcion = "Rutina generada localmente (fallback por fallo de IA)"

            # Asegura que dias exista y sea lista
            if not isinstance(dias, list):
                dias = []

            # Si sigue vacío, crear fallback
            if len(dias) == 0:
                dias = [
                    DiaRutinaDetallado(
                        numero_dia=1,
                        nombre_dia="Día 1",
                        descripcion="Fallback: sin ejercicios",
                        grupos_enfoque=["GENERAL"],
                        ejercicios=[]
                    )
                ]

            total_ejercicios = sum(len(d.ejercicios) for d in dias)

            minutos = calcular_minutos_rutina(dias)

            vigencia_info = calcular_fechas_vigencia(solicitud.duracion_meses)

            estado_vigencia = "pendiente"
            fecha_inicio_v = None

            if activar_vigencia:
                estado_vigencia = "activa"
                fecha_inicio_v = vigencia_info["inicio"]

            base = RutinaCompleta(
                nombre=f"Rutina {nivel_norm.title()} - {solicitud.objetivos}",
                descripcion=descripcion,
                id_cliente=solicitud.id_cliente,
                objetivo=solicitud.objetivos,
                grupo_muscular=solicitud.grupo_muscular_foco,
                nivel=nivel_norm,
                dias_semana=solicitud.dias,
                total_ejercicios=total_ejercicios,
                minutos_aproximados=minutos,
                duracion_meses=solicitud.duracion_meses,
                fecha_inicio_vigencia=fecha_inicio_v.isoformat() if fecha_inicio_v else None,
                fecha_fin_vigencia=vigencia_info["fin"].isoformat(),
                estado_vigencia=estado_vigencia,
                dias=dias,
                fecha_creacion=datetime.now().isoformat(),
                generada_por=generada_por
            )

            # ======================================================
            # 4) GUARDAR EN BD (rutina + ejercicios)
            # ======================================================

            id_rutina = guardar_rutina_bd(db, base)
            guardar_ejercicios_rutina(db, id_rutina, dias)

            # ======================================================
            # 5) CREAR HISTORIAL Y COPIAR EJERCICIOS
            # ======================================================

            id_historial = crear_historial_rutina(db, id_rutina, base)
            copiar_ejercicios_historial(db, id_historial, id_rutina)

            # ======================================================
            # 6) CREAR OBJETIVOS Y ALERTAS INICIALES
            # ======================================================

            crear_objetivos_iniciales(db, solicitud.id_cliente, id_rutina)
            crear_alertas_iniciales(db, solicitud.id_cliente)

            # ======================================================
            # 7) RESPUESTA COMPLETA
            # ======================================================

            return {
                "status": "ok",
                "mensaje": "Rutina generada y guardada exitosamente",
                "id_rutina": id_rutina,
                "id_historial": id_historial,
                "rutina": base.model_dump(),
                "seguridad": seguridad.model_dump() if seguridad else None,
                "proveedor": generada_por
            }


        except HTTPException:

            raise


        except Exception as e:

            import traceback

            print("\n🔴 ⚠️ ERROR CRÍTICO AL GENERAR RUTINA ⚠️ 🔴")

            print("==============================================")

            traceback.print_exc()  # imprime error completo

            print("----------------------------------------------")

            print("DETALLE DEL ERROR:", str(e))

            print("==============================================\n")

            db.rollback()

            raise HTTPException(

                status_code=500,

                detail=f"Error interno al generar rutina (revisa consola del servidor para más detalles)"

            )


    # ============================================================
    # NUEVOS ENDPOINTS - GESTIÓN DE VIGENCIA
    # ============================================================

    # ============================================================
    # ENDPOINTS DE VIGENCIA - COMPATIBLE CON TU BD REAL
    # ============================================================

    @router.post("/rutinas/{id_rutina}/activar-vigencia")
    def activar_vigencia_rutina(
            id_rutina: int,
            duracion_meses: Optional[int] = Query(None, ge=1, le=12),
            db: Session = Depends(get_db)
    ):
        """
        Activa la vigencia de una rutina REAL en tabla 'rutinas'.
        """

        q = text("""
            SELECT duracion_meses FROM rutinas WHERE id_rutina = :id
        """)
        row = db.execute(q, {"id": id_rutina}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Rutina no encontrada")

        meses = duracion_meses if duracion_meses else row[0]

        if not (1 <= meses <= 12):
            raise HTTPException(status_code=422, detail="Duración inválida (1 a 12 meses)")

        desde = datetime.now()
        hasta = desde + timedelta(days=meses * 30)  # aproximación natural

        # Actualizar rutina
        upd = text("""
            UPDATE rutinas
            SET fecha_inicio_vigencia = :inicio,
                fecha_fin_vigencia = :fin,
                duracion_meses = :meses,
                estado_vigencia = 'activa'
            WHERE id_rutina = :id
        """)

        db.execute(upd, {
            "id": id_rutina,
            "inicio": desde,
            "fin": hasta,
            "meses": meses
        })
        db.commit()

        return {
            "status": "ok",
            "mensaje": "Vigencia activada correctamente",
            "id_rutina": id_rutina,
            "fecha_inicio": desde.isoformat(),
            "fecha_fin": hasta.isoformat(),
            "meses": meses
        }


    @router.post("/rutinas/{id_rutina}/extender-vigencia")
    def extender_vigencia(
        id_rutina: int,
        data: ExtenderVigenciaRequest,
        db: Session = Depends(get_db),
    ):
        """
        Extiende la fecha_fin_vigencia con meses adicionales.
        """

        meses_extra = data.meses_adicionales

        q = text("""
            SELECT fecha_fin_vigencia
            FROM rutinas
            WHERE id_rutina = :id
        """)
        row = db.execute(q, {"id": id_rutina}).fetchone()

        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="No existe vigencia activa a extender")

        fecha_fin_actual: datetime = row[0]
        nueva_fecha_fin = fecha_fin_actual + timedelta(days=meses_extra * 30)

        upd = text("""
            UPDATE rutinas
            SET fecha_fin_vigencia = :fin, estado_vigencia = 'extendida'
            WHERE id_rutina = :id
        """)

        db.execute(upd, {"fin": nueva_fecha_fin, "id": id_rutina})
        db.commit()

        return {
            "status": "ok",
            "mensaje": f"Vigencia extendida {meses_extra} meses",
            "fecha_fin_nueva": nueva_fecha_fin.isoformat()
        }


    @router.get("/rutinas/{id_rutina}/vigencia")
    def consultar_vigencia(id_rutina: int, db: Session = Depends(get_db)):
        """
        Devuelve el estado de vigencia de la rutina real.
        """

        q = text("""
            SELECT 
                nombre, fecha_inicio_vigencia, fecha_fin_vigencia, estado_vigencia, duracion_meses
            FROM rutinas
            WHERE id_rutina = :id
        """)

        row = db.execute(q, {"id": id_rutina}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Rutina no encontrada")

        nombre, inicio, fin, estado, meses = row

        if not inicio or not fin:
            return {
                "id_rutina": id_rutina,
                "nombre": nombre,
                "estado": "pendiente",
                "mensaje": "La rutina no ha sido activada aún"
            }

        estado_real = obtener_estado_vigencia(fin, inicio)

        return {
            "id_rutina": id_rutina,
            "nombre": nombre,
            "vigencia": {
                "inicio": inicio.isoformat(),
                "fin": fin.isoformat(),
                "duracion_meses": meses,
                "dias_totales": (fin - inicio).days,
                "dias_restantes": estado_real["dias_restantes"],
                "porcentaje_completado": estado_real["porcentaje_completado"],
                "estado": estado_real["estado"],
                "estado_db": estado
            }
        }


    @router.get("/rutinas/por-vencer")
    def listar_rutinas_por_vencer(
            dias_aviso: int = Query(7, ge=1, le=30),
            id_entrenador: Optional[int] = None,
            db: Session = Depends(get_db)
    ):
        """
        Lista rutinas cuya fecha_fin_vigencia está cerca.
        """

        limite = datetime.now() + timedelta(days=dias_aviso)

        q = text("""
            SELECT 
                r.id_rutina, r.nombre, r.fecha_fin_vigencia, r.fecha_inicio_vigencia,
                r.estado_vigencia, r.creado_por,
                u.nombre AS nom, u.apellido AS ape
            FROM rutinas r
            LEFT JOIN usuarios u ON r.creado_por = u.id_usuario
            WHERE r.fecha_fin_vigencia IS NOT NULL
              AND r.fecha_fin_vigencia BETWEEN NOW() AND :limite
              AND ( :entrenador IS NULL OR r.creado_por = :entrenador)
            ORDER BY r.fecha_fin_vigencia ASC
        """)

        rows = db.execute(q, {"limite": limite, "entrenador": id_entrenador}).fetchall()

        out = []
        for r in rows:
            estado_info = obtener_estado_vigencia(r[2], r[3])
            out.append({
                "id_rutina": r[0],
                "nombre": r[1],
                "fecha_fin": r[2].isoformat(),
                "dias_restantes": estado_info["dias_restantes"],
                "porcentaje_completado": estado_info["porcentaje_completado"],
                "estado": estado_info["estado"],
                "entrenador": f"{r[5]} - {r[6]} {r[7]}" if r[6] else None
            })

        return {
            "total": len(out),
            "rutinas": out,
            "fecha_consulta": datetime.now().isoformat()
        }


    @router.get("/rutinas/vencidas")
    def listar_rutinas_vencidas(
        id_entrenador: Optional[int] = None,
        db: Session = Depends(get_db)
    ):
        """
        Lista rutinas vencidas ordenadas por fecha_fin_vigencia
        """

        q = text("""
            SELECT 
                r.id_rutina, r.nombre, r.fecha_inicio_vigencia, r.fecha_fin_vigencia,
                u.nombre, u.apellido
            FROM rutinas r
            LEFT JOIN usuarios u ON r.creado_por = u.id_usuario
            WHERE r.fecha_fin_vigencia < NOW()
              AND ( :entrenador IS NULL OR r.creado_por = :entrenador)
            ORDER BY r.fecha_fin_vigencia DESC
        """)

        rows = db.execute(q, {"entrenador": id_entrenador}).fetchall()

        out = []
        now = datetime.now()

        for r in rows:
            dias_vencida = (now - r[3]).days
            out.append({
                "id_rutina": r[0],
                "nombre": r[1],
                "fecha_inicio": r[2].isoformat(),
                "fecha_fin": r[3].isoformat(),
                "dias_vencida": dias_vencida,
                "entrenador": f"{r[4]} {r[5]}" if r[4] else None
            })

        return {
            "total": len(out),
            "rutinas": out,
            "fecha_consulta": now.isoformat()
        }


    # ============================================================
    # ENDPOINTS ORIGINALES - DEBUG Y STATUS
    # ============================================================

    @router.get("/gemini/debug")
    def gemini_debug():
        try:
            if not GEMINI_API_KEY:
                return {"status": "error", "message": "GEMINI_API_KEY no configurada"}

            model = genai.GenerativeModel(GEMINI_MODEL)
            prompt = 'Devuelve SOLO este JSON: {"ok": true, "modelo": "' + GEMINI_MODEL + '"}'
            try:
                resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json",
                                                                         "temperature": 0.0})
            except TypeError:
                resp = model.generate_content([prompt], generation_config={"response_mime_type": "application/json",
                                                                           "temperature": 0.0})

            raw = _resp_to_text(resp)
            return {"status": "ok", "raw": raw}
        except Exception as e:
            return {"status": "error", "message": f"{type(e).__name__}: {str(e)}"}


    @router.get("/openai/debug")
    def openai_debug():
        """Endpoint para verificar que OpenAI está funcionando correctamente"""
        try:
            if not OPENAI_API_KEY:
                return {"status": "error", "message": "OPENAI_API_KEY no configurada"}

            if not openai_client:
                return {"status": "error", "message": "Cliente OpenAI no disponible"}

            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Responde solo con JSON válido"},
                    {"role": "user", "content": 'Devuelve SOLO este JSON: {"ok": true, "modelo": "' + OPENAI_MODEL + '"}'}
                ],
                temperature=0.0,
                max_tokens=100,
                response_format={"type": "json_object"}
            )

            raw = response.choices[0].message.content
            return {"status": "ok", "raw": raw, "model": OPENAI_MODEL}
        except Exception as e:
            return {"status": "error", "message": f"{type(e).__name__}: {str(e)}"}


    @router.get("/grok/debug")
    def grok_debug():
        """Endpoint para verificar que Grok está funcionando correctamente"""
        try:
            if not GROK_API_KEY:
                return {"status": "error", "message": "GROK_API_KEY no configurada"}

            if not grok_client:
                return {"status": "error", "message": "Cliente Grok no disponible"}

            response = grok_client.chat.completions.create(
                model=GROK_MODEL,
                messages=[
                    {"role": "system", "content": "Responde solo con JSON válido"},
                    {"role": "user", "content": 'Devuelve SOLO este JSON: {"ok": true, "modelo": "' + GROK_MODEL + '"}'}
                ],
                temperature=0.0,
                max_tokens=100
            )

            raw = response.choices[0].message.content
            return {"status": "ok", "raw": raw, "model": GROK_MODEL}
        except Exception as e:
            return {"status": "error", "message": f"{type(e).__name__}: {str(e)}"}


    @router.get("/ejercicios/sugerencias")
    def obtener_ejercicios_sugeridos(
            grupo: str = "general",
            nivel: str = "intermedio",
            limite: int = 20,
            db: Session = Depends(get_db)
    ):
        try:
            nivel_map = {"principiante": "PRINCIPIANTE", "intermedio": "INTERMEDIO", "avanzado": "AVANZADO"}
            nivel_norm = nivel_map.get(nivel.lower(), "INTERMEDIO")

            q = text("""
                SELECT id_ejercicio, nombre, descripcion, grupo_muscular, dificultad, tipo
                FROM ejercicios WHERE grupo_muscular = :grupo LIMIT :limite
            """)
            res = db.execute(q, {"grupo": grupo.upper(), "limite": limite}).fetchall()

            ejercicios = [{
                "id_ejercicio": e[0], "nombre": e[1], "descripcion": e[2] or "",
                "grupo_muscular": e[3], "dificultad": e[4], "tipo": e[5] or "general"
            } for e in res]

            return {"total": len(ejercicios), "grupo": grupo, "nivel": nivel_norm, "ejercicios": ejercicios}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


    @router.get("/planes/distribucion")
    def obtener_planes_distribucion():
        return {
            "planes_disponibles": {
                "2_dias": PLANES_DISTRIBUCION[2],
                "3_dias": PLANES_DISTRIBUCION[3],
                "4_dias": PLANES_DISTRIBUCION[4],
                "5_dias": PLANES_DISTRIBUCION[5],
                "6_dias": PLANES_DISTRIBUCION[6],
                "7_dias": PLANES_DISTRIBUCION[7],
            },
            "descripcion": "Planes de distribución de grupos musculares por día"
        }


    @router.get("/gemini/status")
    def gemini_status():
        try:
            if not GEMINI_API_KEY:
                return {"status": "warning", "message": "GEMINI_API_KEY no configurada", "fallback": "enabled (local)"}

            models_info = []
            try:
                for m in genai.list_models():
                    models_info.append({
                        "name": getattr(m, "name", ""),
                        "id": _normalize_model_name(getattr(m, "name", "")),
                        "supports_generateContent": _supports_generate_content(m)
                    })
            except Exception as e:
                models_info = [{"error_list_models": str(e)}]

            selected = None
            try:
                selected = _select_gemini_model()
            except Exception as e:
                selected = f"(selección fallida) {type(e).__name__}: {str(e)}"

            return {
                "status": "ok",
                "wanted_env": os.getenv("GEMINI_MODEL"),
                "selected_model": selected,
                "models": models_info,
                "timeout_seconds": GEMINI_TIMEOUT_SECONDS
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


    @router.get("/openai/status")
    def openai_status():
        """Endpoint para verificar el estado de OpenAI"""
        try:
            if not OPENAI_API_KEY:
                return {"status": "warning", "message": "OPENAI_API_KEY no configurada"}

            if not openai_client:
                return {"status": "error", "message": "Cliente OpenAI no disponible. Instala con: pip install openai"}

            return {
                "status": "ok",
                "model": OPENAI_MODEL,
                "client_available": True
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


    @router.get("/grok/status")
    def grok_status():
        """Endpoint para verificar el estado de Grok (xAI)"""
        try:
            if not GROK_API_KEY:
                return {"status": "warning", "message": "GROK_API_KEY no configurada"}

            if not grok_client:
                return {"status": "error", "message": "Cliente Grok no disponible. Instala con: pip install openai"}

            return {
                "status": "ok",
                "model": GROK_MODEL,
                "client_available": True
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


    @router.get("/ai/status")
    def ai_providers_status():
        """Endpoint para ver el estado de todos los proveedores de IA"""
        return {
            "gemini": {
                "configured": bool(GEMINI_API_KEY),
                "model": GEMINI_MODEL if GEMINI_API_KEY else None,
                "timeout_seconds": GEMINI_TIMEOUT_SECONDS
            },
            "openai": {
                "configured": bool(OPENAI_API_KEY),
                "model": OPENAI_MODEL if OPENAI_API_KEY else None,
                "client_available": openai_client is not None
            },
            "grok": {
                "configured": bool(GROK_API_KEY),
                "model": GROK_MODEL if GROK_API_KEY else None,
                "client_available": grok_client is not None
            },
            "local": {
                "available": True,
                "description": "Fallback local siempre disponible"
            }
        }