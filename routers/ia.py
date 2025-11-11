# routers/ia_router.py - Router IA V4 (Gemini + OpenAI + fallback local + filtros de salud)

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any, Literal
import google.generativeai as genai
import os
import json
import re
from datetime import datetime

from utils.dependencies import get_db

router = APIRouter(prefix="/api/ia", tags=["IA"])

# ============================================================
# CONFIG
# ============================================================

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
    dias: int  # 2-7
    nivel: str  # "principiante" | "intermedio" | "avanzado"
    grupo_muscular_foco: Optional[str] = "general"
    perfil_salud: Optional[PerfilSalud] = None
    proveedor: Literal["auto", "gemini", "openai", "grok", "local"] = "auto"  # <-- ACTUALIZADO CON GROK


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
# HELPER FUNCTIONS - DETECCIÓN DE ERRORES
# ============================================================

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
    # El SDK lista modelos como "models/gemini-1.5-pro-002". Aceptamos ambos.
    return name.split("/")[-1] if name and "/" in name else name


def _select_gemini_model() -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY no configurada")

    wanted = os.getenv("GEMINI_MODEL", "").strip()
    try:
        models = list(genai.list_models())
    except Exception as e:
        # Si no podemos listar, usa el que pidieron o el preferido por defecto
        return wanted or PREFERRED_MODELS[0]

    # Si pidieron uno concreto, valídalo contra la lista
    if wanted:
        for m in models:
            m_id = _normalize_model_name(getattr(m, "name", ""))
            if m_id == _normalize_model_name(wanted) and _supports_generate_content(m):
                return m_id

    # Si no hay/valido, usa el primero de los preferidos que esté disponible
    for pref in PREFERRED_MODELS:
        for m in models:
            m_id = _normalize_model_name(getattr(m, "name", ""))
            if m_id == pref and _supports_generate_content(m):
                return pref

    # Último recurso: el primer modelo que soporte generateContent
    for m in models:
        if _supports_generate_content(m):
            return _normalize_model_name(getattr(m, "name", ""))

    raise RuntimeError("No hay modelos Gemini compatibles con generateContent en esta cuenta.")


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
    # bonus si grupo = PIERNAS/GLÚTEO
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

    # Splits con 2–3 días de glúteos por semana
    presets = {
        3: [["GLÚTEOS/PIERNAS"], ["UPPER LIGERO"], ["GLÚTEOS/PIERNAS"]],
        4: [["GLÚTEOS/QUADS"], ["UPPER LIGERO"], ["GLÚTEOS/ISQUIOS"], ["CORE/CARDIO SUAVE"]],
        5: [["GLÚTEOS/QUADS"], ["UPPER LIGERO"], ["GLÚTEOS/ISQUIOS"], ["CORE/ESTABILIDAD"], ["GLÚTEOS (AISLAMIENTOS)"]],
        6: [["GLÚTEOS/QUADS"], ["UPPER LIGERO"], ["GLÚTEOS/ISQUIOS"], ["UPPER LIGERO"], ["GLÚTEOS (AISLAMIENTOS)"],
            ["CORE/CARDIO"]],
        7: [["GLÚTEOS/QUADS"], ["UPPER LIGERO"], ["GLÚTEOS/ISQUIOS"], ["CORE"], ["GLÚTEOS (AISLAMIENTOS)"],
            ["UPPER LIGERO"], ["DESCANSO"]],
    }

    # Fallback cercano si no hay preset exacto
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

    # Split por objetivo (glúteos) o genérico
    plan = _split_por_objetivo(dias_semana, objetivo, None)

    idxs = {g: 0 for g in ejercicios_por_grupo.keys()}
    advertencias: List[str] = []
    casa_sin_equipo = _es_casa_sin_equipo(perfil.preferencias if perfil else None)

    # Función local para "expandir" etiquetas artificiales a grupos reales
    def expandir_grupo(alias: str) -> List[str]:
        a = alias.upper()
        if "UPPER" in a:
            return ["PECHO", "ESPALDA", "HOMBROS", "BRAZOS"]
        if "GLÚTEOS" in a or "GLUTEOS" in a or "GLUTE" in a:
            return ["PIERNAS"]  # usamos pool de PIERNAS pero luego priorizamos por score de glúteo
        if "CORE" in a:
            return ["CORE"]
        if "CARDIO" in a:
            return ["CARDIO"]
        if "DESCANSO" in a:
            return ["DESCANSO"]
        return [a]

    for i, grupos in enumerate(plan):
        nombre_dia = nombres[i] if i < len(nombres) else f"Día {i + 1}"
        # Expande aliases (UPPER LIGERO, GLÚTEOS/QUADS, etc.)
        grupos_norm: List[str] = []
        for g in grupos:
            # Soporte de alias escritos como "GLÚTEOS/ISQUIOS"
            partes = [p.strip() for p in g.replace("/", ",").split(",")]
            for p in partes:
                grupos_norm.extend(expandir_grupo(p))

        activos = [g for g in grupos_norm if g != "DESCANSO"]
        n_por_grupo = max(2, 6 // max(1, len(activos)))  # ~5–6 ejercicios/día

        ej_del_dia: List[EjercicioRutina] = []
        usados: set = set()  # (id, nombre) para evitar duplicados

        for g in grupos_norm:
            if g == "DESCANSO":
                continue

            g_pri = MAPEO_GRUPOS_SECUNDARIOS.get(g, g)
            pool = list(ejercicios_por_grupo.get(g_pri, []))

            # 1) Filtra por salud
            pool, seg_local = validar_filtrar_ejercicios(perfil, pool)
            if seg_local.advertencias:
                advertencias.extend([f"{nombre_dia}/{g}: {a}" for a in seg_local.advertencias])

            # 2) Filtra por equipo si casa sin equipo
            if casa_sin_equipo:
                pool = [e for e in pool if not _descarta_por_equipo_si_casa_sin_equipo(e)]

            # 3) Prioriza glúteos por score si el objetivo es glúteos
            if _objetivo_es_gluteos(objetivo, "gluteo"):
                pool.sort(key=_score_prioridad_gluteo, reverse=True)

            # 4) Selección circular con deduplicación
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
    objetivo_primario = objetivos.lower()

    reglas_equipo = []
    if home and no_equipo:
        reglas_equipo.append(
            "- Si es en casa sin equipamiento, evita máquinas, barras o poleas; usa peso corporal o bandas elásticas.")
    elif home and pref.equipamiento:
        reglas_equipo.append(
            f"- Equipamiento disponible: {pref.equipamiento} (no uses máquinas de gimnasio no listadas).")

    foco_gluteos = ""
    if "glute" in objetivo_primario or "glúte" in objetivo_primario:
        foco_gluteos = f"""
- OBJETIVO PRINCIPAL: GLÚTEOS Y PIERNAS.
  • Al menos 2–3 días deben enfocarse en tren inferior o glúteos.
  • Incluye básicos (hip thrust, sentadillas, peso muerto rumano) y accesorios (abducciones, patadas, step-ups, puente de glúteo).
  • Series y repeticiones orientadas a hipertrofia (4×10-12 reps, 60–90s descanso).
"""

    # 🧩 Distribución automática por días
    dist_text = f"""
El plan debe distribuir los grupos musculares a lo largo de {dias} días de forma equilibrada:
- Usa el formato push/pull/legs o fullbody, según el nivel ({nivel}).
- Varía el enfoque cada día: por ejemplo, PECHO/BÍCEPS, ESPALDA/TRÍCEPS, PIERNAS/CORE.
- Cada día debe tener entre 5 y 7 ejercicios.
"""

    # 🧍 Perfil del usuario
    perfil_text = f"""
Edad: {p.datos.edad}, Sexo: {p.datos.sexo}, Peso: {p.datos.peso_kg}, Estatura: {p.datos.estatura_cm}
Condiciones: {[c.nombre for c in p.condiciones]}
Lesiones: {[l.zona + ':' + l.tipo for l in p.lesiones]}
Medicaciones: {[m.nombre for m in p.medicaciones]}
Preferencias: lugar={pref.lugar}, tiempo={pref.tiempo_minutos}min, días_disponibles={pref.dias_disponibles}, objetivos={pref.objetivos}, gustos={pref.gustos}, disgustos={pref.disgustos}
"""

    return f"""
Eres un entrenador profesional y debes crear una rutina de entrenamiento personalizada distribuida en {dias} días.

Requisitos:
- Nivel del usuario: {nivel}.
- Objetivos: {objetivos}.
{dist_text}
{foco_gluteos}
{os.linesep.join(reglas_equipo)}

Formato de salida:
Devuelve **solo JSON válido** con esta estructura:

{{
  "nombre": "string",
  "descripcion": "string",
  "dias_semana": {dias},
  "minutos_aproximados": {pref.tiempo_minutos or 45},
  "dias": [
    {{
      "numero_dia": 1,
      "nombre_dia": "Lunes",
      "descripcion": "Día de tren inferior",
      "grupos_enfoque": ["PIERNAS","GLÚTEOS"],
      "ejercicios": [
        {{
          "id_ejercicio": 0,
          "nombre": "Hip Thrust con peso corporal",
          "descripcion": "Ejercicio para activar glúteos con pausa de 2s arriba",
          "grupo_muscular": "PIERNAS",
          "dificultad": "{nivel}",
          "tipo": "fuerza",
          "series": 4,
          "repeticiones": 12,
          "descanso_segundos": 75,
          "notas": "énfasis glúteos"
        }}
      ]
    }}
  ]
}}

{perfil_text}

⚠️ No incluyas texto adicional fuera del JSON.
Si no puedes generar la rutina, devuelve un JSON con {{ "error": "no disponible" }}.
"""


# ============================================================
# AI GENERATORS (GEMINI + OPENAI)
# ============================================================

def _resp_to_text(resp) -> str:
    # Intenta .text
    t = getattr(resp, "text", None)
    if t:
        return t

    # Candidatos (SDKs recientes)
    try:
        cands = getattr(resp, "candidates", None) or []
        if cands:
            parts = getattr(cands[0], "content", None).parts  # type: ignore
            if parts:
                return "".join([getattr(p, "text", "") for p in parts])
    except Exception:
        pass

    # Último recurso: str(...)
    return str(resp)[:2000]


def _gemini_generate_plan(perfil: Optional[PerfilSalud], dias: int, nivel: str, objetivos: str) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY no configurada")

    prompt = _build_ai_prompt(perfil, dias, nivel, objetivos)
    generation_config = {"response_mime_type": "application/json", "temperature": 0.2, "max_output_tokens": 1024}

    last_err = None
    tried_models = []

    # 1) Intento con el modelo seleccionado dinámicamente
    try:
        selected_model = _normalize_model_name(GEMINI_MODEL)
        tried_models.append(selected_model)
        model = genai.GenerativeModel(selected_model)
        try:
            resp = model.generate_content(prompt, generation_config=generation_config)
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
        last_err = e
        # Si NO es un error de cuota, propaga tal cual
        if not _is_quota_error(e):
            raise RuntimeError(
                f"Fallo en _gemini_generate_plan: {type(e).__name__}: {str(e)} (modelos probados: {tried_models})")

    # 2) Si fue cuota, intenta con modelo ligero (flash) una vez
    try:
        light_model = FALLBACK_LIGHT_MODEL
        tried_models.append(light_model)
        model = genai.GenerativeModel(light_model)
        try:
            resp = model.generate_content(prompt, generation_config=generation_config)
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
        # Propaga el error original de cuota para que el endpoint decida (429/fallback)
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
            response_format={"type": "json_object"}  # Fuerza respuesta JSON
        )

        raw = response.choices[0].message.content
        if not raw:
            raise RuntimeError("OpenAI devolvió respuesta vacía")

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Intenta extraer JSON del texto
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
            # Intenta extraer JSON del texto
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                raise ValueError(f"Grok no devolvió JSON válido. raw (400): {raw[:400]}...")
            return json.loads(m.group(0))

    except Exception as e:
        raise RuntimeError(f"Fallo en _grok_generate_plan: {type(e).__name__}: {str(e)}")


# ============================================================
# CONVERSION FROM AI TO PYDANTIC
# ============================================================

def _from_ai_to_pydantic(plan: Dict[str, Any], nivel_norm: str, perfil: Optional[PerfilSalud]) -> (
        List[DiaRutinaDetallado], SeguridadOut):
    dias_py: List[DiaRutinaDetallado] = []
    advertencias: List[str] = []
    for d in plan.get("dias", []):
        ejercicios_in = d.get("ejercicios", [])
        ejercicios_filtrados, seg_local = validar_filtrar_ejercicios(perfil, ejercicios_in)
        if seg_local.advertencias:
            advertencias.extend([f"{d.get('nombre_dia', 'Día?')}: {a}" for a in seg_local.advertencias])
        ejercicios_out = [EjercicioRutina(
            id_ejercicio=int(e.get("id_ejercicio", 0)),
            nombre=str(e.get("nombre", "")).strip(),
            descripcion=str(e.get("descripcion", "") or ""),
            grupo_muscular=str(e.get("grupo_muscular", "GENERAL")).upper(),
            dificultad=str(e.get("dificultad", nivel_norm)),
            tipo=str(e.get("tipo", "general")),
            series=int(e.get("series", 3)),
            repeticiones=int(e.get("repeticiones", 10)),
            descanso_segundos=int(e.get("descanso_segundos", 60)),
            notas=e.get("notas")
        ) for e in ejercicios_filtrados]

        dias_py.append(DiaRutinaDetallado(
            numero_dia=int(d.get("numero_dia", len(dias_py) + 1)),
            nombre_dia=str(d.get("nombre_dia", f"Día {len(dias_py) + 1}")),
            descripcion=str(d.get("descripcion", "")),
            grupos_enfoque=[str(x).upper() for x in d.get("grupos_enfoque", [])],
            ejercicios=ejercicios_out
        ))

    seg_global = perf_to_riesgo(perfil)
    seguridad = SeguridadOut(
        nivel_riesgo=seg_global.nivel_riesgo,
        detonantes_evitar=seg_global.detonantes_evitar,
        advertencias=advertencias,
        validada_por_reglas=(len(advertencias) == 0)
    )
    return dias_py, seguridad


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/generar-rutina", response_model=Dict[str, Any])
def generar_rutina_distribuida(solicitud: SolicitudGenerarRutina, db: Session = Depends(get_db)):
    """
    Genera una rutina con IA (Gemini/OpenAI) ajustada por perfil de salud.
    - proveedor="auto"   -> intenta Gemini primero, si falla usa OpenAI, si falla usa local
    - proveedor="gemini" -> exige Gemini (si cuota 429, si otro error 502).
    - proveedor="openai" -> exige OpenAI (si error 502).
    - proveedor="local"  -> usa generador local directamente.
    """
    try:
        if not (2 <= solicitud.dias <= 7):
            raise HTTPException(status_code=422, detail="Días debe estar entre 2 y 7")

        nivel_map = {"principiante": "PRINCIPIANTE", "intermedio": "INTERMEDIO", "avanzado": "AVANZADO"}
        nivel_norm = nivel_map.get(solicitud.nivel.lower(), "INTERMEDIO")
        prov = getattr(solicitud, "proveedor", "auto")

        # Validaciones de proveedor
        if prov == "gemini" and not GEMINI_API_KEY:
            raise HTTPException(status_code=502, detail="Gemini requerido pero GEMINI_API_KEY no está configurada")

        if prov == "openai" and not OPENAI_API_KEY:
            raise HTTPException(status_code=502, detail="OpenAI requerido pero OPENAI_API_KEY no está configurada")

        if prov == "grok" and not GROK_API_KEY:
            raise HTTPException(status_code=502, detail="Grok requerido pero GROK_API_KEY no está configurada")

        generada_por = "local"
        descripcion = "Rutina generada localmente con validación de seguridad"

        # LOCAL DIRECTO
        if prov == "local":
            ejercicios_por_grupo = obtener_ejercicios_por_grupo(db, nivel_norm)
            if not any(ejercicios_por_grupo.values()):
                raise HTTPException(status_code=400, detail="No hay ejercicios disponibles en la base de datos")

            dias, seguridad = distribuir_ejercicios_inteligente(
                ejercicios_por_grupo=ejercicios_por_grupo,
                dias_semana=solicitud.dias,
                nivel=nivel_norm,
                objetivo=solicitud.objetivos,
                perfil=solicitud.perfil_salud
            )
            generada_por = "local"
            descripcion = "Rutina generada localmente (respaldo) con validación de seguridad"

        # GEMINI DIRECTO
        elif prov == "gemini":
            try:
                plan_json = _gemini_generate_plan(
                    perfil=solicitud.perfil_salud,
                    dias=solicitud.dias,
                    nivel=nivel_norm,
                    objetivos=solicitud.objetivos
                )
                dias, seguridad = _from_ai_to_pydantic(plan_json, nivel_norm, solicitud.perfil_salud)
                generada_por = "gemini"
                descripcion = "Rutina generada por IA (Gemini) con validación de seguridad"
            except Exception as ge:
                status_code = 429 if _is_quota_error(ge) else 502
                raise HTTPException(
                    status_code=status_code,
                    detail={
                        "error": "quota_exceeded" if status_code == 429 else "gemini_error",
                        "message": str(ge),
                        "hint": "Usa proveedor='auto' para fallback automático o revisa cuotas/billing."
                    }
                )

        # OPENAI DIRECTO
        elif prov == "openai":
            try:
                plan_json = _openai_generate_plan(
                    perfil=solicitud.perfil_salud,
                    dias=solicitud.dias,
                    nivel=nivel_norm,
                    objetivos=solicitud.objetivos
                )
                dias, seguridad = _from_ai_to_pydantic(plan_json, nivel_norm, solicitud.perfil_salud)
                generada_por = "openai"
                descripcion = "Rutina generada por IA (OpenAI ChatGPT) con validación de seguridad"
            except Exception as oe:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "openai_error",
                        "message": str(oe),
                        "hint": "Usa proveedor='auto' para fallback automático."
                    }
                )

        # GROK DIRECTO
        elif prov == "grok":
            try:
                plan_json = _grok_generate_plan(
                    perfil=solicitud.perfil_salud,
                    dias=solicitud.dias,
                    nivel=nivel_norm,
                    objetivos=solicitud.objetivos
                )
                dias, seguridad = _from_ai_to_pydantic(plan_json, nivel_norm, solicitud.perfil_salud)
                generada_por = "grok"
                descripcion = "Rutina generada por IA (Grok xAI) con validación de seguridad"
            except Exception as gke:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "grok_error",
                        "message": str(gke),
                        "hint": "Usa proveedor='auto' para fallback automático."
                    }
                )

        # AUTO (Cascada: Gemini -> OpenAI -> Grok -> Local)
        else:
            # Intento 1: Gemini
            try:
                if GEMINI_API_KEY:
                    plan_json = _gemini_generate_plan(
                        perfil=solicitud.perfil_salud,
                        dias=solicitud.dias,
                        nivel=nivel_norm,
                        objetivos=solicitud.objetivos
                    )
                    dias, seguridad = _from_ai_to_pydantic(plan_json, nivel_norm, solicitud.perfil_salud)
                    generada_por = "gemini"
                    descripcion = "Rutina generada por IA (Gemini) con validación de seguridad"
                else:
                    raise RuntimeError("Gemini no disponible")
            except Exception as ge:
                print(f"⚠️ Gemini falló: {ge}")

                # Intento 2: OpenAI
                try:
                    if OPENAI_API_KEY and openai_client:
                        plan_json = _openai_generate_plan(
                            perfil=solicitud.perfil_salud,
                            dias=solicitud.dias,
                            nivel=nivel_norm,
                            objetivos=solicitud.objetivos
                        )
                        dias, seguridad = _from_ai_to_pydantic(plan_json, nivel_norm, solicitud.perfil_salud)
                        generada_por = "openai"
                        descripcion = "Rutina generada por IA (OpenAI ChatGPT) con validación de seguridad"
                    else:
                        raise RuntimeError("OpenAI no disponible")
                except Exception as oe:
                    print(f"⚠️ OpenAI falló: {oe}")

                    # Intento 3: Grok
                    try:
                        if GROK_API_KEY and grok_client:
                            plan_json = _grok_generate_plan(
                                perfil=solicitud.perfil_salud,
                                dias=solicitud.dias,
                                nivel=nivel_norm,
                                objetivos=solicitud.objetivos
                            )
                            dias, seguridad = _from_ai_to_pydantic(plan_json, nivel_norm, solicitud.perfil_salud)
                            generada_por = "grok"
                            descripcion = "Rutina generada por IA (Grok xAI) con validación de seguridad"
                        else:
                            raise RuntimeError("Grok no disponible")
                    except Exception as gke:
                        print(f"⚠️ Grok falló: {gke}")

                        # Intento 4: Local Fallback
                        ejercicios_por_grupo = obtener_ejercicios_por_grupo(db, nivel_norm)
                        if not any(ejercicios_por_grupo.values()):
                            raise HTTPException(status_code=400,
                                                detail="No hay ejercicios disponibles en la base de datos")

                        dias, seguridad = distribuir_ejercicios_inteligente(
                            ejercicios_por_grupo=ejercicios_por_grupo,
                            dias_semana=solicitud.dias,
                            nivel=nivel_norm,
                            objetivo=solicitud.objetivos,
                            perfil=solicitud.perfil_salud
                        )
                        generada_por = "local"
                        descripcion = "Rutina generada localmente (respaldo) por límite de cuota o error de IA"

        total_ejercicios = sum(len(d.ejercicios) for d in dias)
        minutos = calcular_minutos_rutina(dias)

        base = RutinaCompleta(
            nombre=f"Rutina de {nivel_norm} - {solicitud.objetivos.title()}",
            descripcion=descripcion,
            id_cliente=solicitud.id_cliente,
            objetivo=solicitud.objetivos,
            grupo_muscular=solicitud.grupo_muscular_foco or "General",
            nivel=nivel_norm,
            dias_semana=solicitud.dias,
            total_ejercicios=total_ejercicios,
            minutos_aproximados=minutos,
            dias=dias,
            fecha_creacion=datetime.now().isoformat(),
            generada_por=generada_por
        )

        return {**base.model_dump(), "seguridad": seguridad.model_dump(), "proveedor": prov}

    except HTTPException:
        raise
    except Exception as e:
        import traceback;
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al generar rutina: {str(e)}")


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
            "models": models_info
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
            "model": GEMINI_MODEL if GEMINI_API_KEY else None
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