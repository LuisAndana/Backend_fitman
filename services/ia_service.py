# services/ia_service.py - Servicio de IA mejorado con fallback

from typing import List, Optional
import random
from pydantic import BaseModel

class EjercicioIA(BaseModel):
    id_ejercicio: int
    nombre: str
    descripcion: str
    grupo_muscular: str
    dificultad: str
    tipo: str
    series: int = 3
    repeticiones: int = 10
    descanso_segundos: int = 60
    notas: Optional[str] = None


class RutinaLocal(BaseModel):
    nombre: str
    descripcion: str
    ejercicios: List[EjercicioIA]
    total_ejercicios: int
    minutos_aproximados: int
    dias_semana: int
    nivel: str
    objetivo: str


class IAService:
    """Servicio para manejar la lógica de IA y generación local"""

    @staticmethod
    def generar_rutina_local(
        ejercicios: List[dict],
        dias: int,
        nivel: str,
        objetivos: str
    ) -> RutinaLocal:
        """
        Genera una rutina usando lógica local cuando Gemini no funciona.
        Fallback robusto que garantiza una rutina válida.
        """
        print("\n⚠️  Usando generación local (Gemini no disponible)")
        print("─" * 60)

        if not ejercicios:
            raise ValueError("No hay ejercicios disponibles para generar rutina")

        # Agrupar ejercicios por tipo
        ejercicios_por_tipo = {}
        for ej in ejercicios:
            tipo = ej.get('tipo', 'general')
            if tipo not in ejercicios_por_tipo:
                ejercicios_por_tipo[tipo] = []
            ejercicios_por_tipo[tipo].append(ej)

        # Construir rutina seleccionando ejercicios variados
        rutina_ejercicios = []
        ejercicios_por_dia = max(4, len(ejercicios) // dias)

        seleccionados = set()
        for _ in range(min(dias * ejercicios_por_dia, len(ejercicios))):
            # Seleccionar ejercicio aleatorio que no esté repetido
            ej = random.choice(ejercicios)
            if ej.get('id_ejercicio') not in seleccionados:
                seleccionados.add(ej.get('id_ejercicio'))

                # Ajustar series/repeticiones según nivel
                if nivel == "PRINCIPIANTE":
                    series = 2
                    repeticiones = 10
                    descanso = 90
                elif nivel == "AVANZADO":
                    series = 4
                    repeticiones = 8
                    descanso = 45
                else:  # INTERMEDIO
                    series = 3
                    repeticiones = 10
                    descanso = 60

                rutina_ejercicios.append(
                    EjercicioIA(
                        id_ejercicio=ej.get('id_ejercicio', 0),
                        nombre=ej.get('nombre', 'Ejercicio'),
                        descripcion=ej.get('descripcion', ''),
                        grupo_muscular=ej.get('grupo_muscular', 'general'),
                        dificultad=ej.get('dificultad', nivel),
                        tipo=ej.get('tipo', 'general'),
                        series=series,
                        repeticiones=repeticiones,
                        descanso_segundos=descanso,
                        notas=f"Recomendado para {objetivos.lower()}"
                    )
                )

        # Calcular tiempo aproximado
        minutos = sum(
            (ej.series * ej.repeticiones * 3 + ej.descanso_segundos) // 60
            for ej in rutina_ejercicios
        ) // dias

        rutina = RutinaLocal(
            nombre=f"Rutina de {nivel.capitalize()} - {objetivos.title()}",
            descripcion=f"Rutina personalizada para: {objetivos}",
            ejercicios=rutina_ejercicios,
            total_ejercicios=len(rutina_ejercicios),
            minutos_aproximados=max(30, minutos),
            dias_semana=dias,
            nivel=nivel,
            objetivo=objetivos
        )

        print(f"✅ Rutina generada localmente")
        print(f"   - {len(rutina_ejercicios)} ejercicios")
        print(f"   - {rutina.minutos_aproximados} minutos aprox")
        print()

        return rutina

    @staticmethod
    def normalizar_valor_enum(valor: str, tipo: str = "nivel") -> Optional[str]:
        """Normaliza valores de enums a los valores válidos en MySQL."""
        if not valor:
            return None

        valor_limpio = valor.strip().upper()

        if tipo == "nivel":
            mapeo = {
                "PRINCIPIANTE": "PRINCIPIANTE",
                "BEGINNER": "PRINCIPIANTE",
                "FACIL": "PRINCIPIANTE",
                "INTERMEDIO": "INTERMEDIO",
                "INTERMEDIATE": "INTERMEDIO",
                "AVANZADO": "AVANZADO",
                "ADVANCED": "AVANZADO",
                "GENERAL": None,
            }
            return mapeo.get(valor_limpio, None)

        elif tipo == "grupo":
            mapeo = {
                "PECHO": "PECHO",
                "ESPALDA": "ESPALDA",
                "BRAZOS": "BRAZOS",
                "PIERNAS": "PIERNAS",
                "HOMBROS": "HOMBROS",
                "CORE": "CORE",
                "CARDIO": "CARDIO",
                "GENERAL": None,
            }
            return mapeo.get(valor_limpio, None)

        return None

    @staticmethod
    def construir_prompt_rutina(
        nombre_alumno: str,
        ejercicios: List[dict],
        dias: int,
        nivel: str,
        objetivos: str
    ) -> str:
        """Construye el prompt para Gemini."""
        import json

        ejercicios_json = json.dumps([{
            "id": e.get('id_ejercicio'),
            "nombre": e.get('nombre'),
            "grupo_muscular": e.get('grupo_muscular'),
            "dificultad": e.get('dificultad'),
        } for e in ejercicios[:30]], ensure_ascii=False)

        prompt = f"""
Eres un entrenador personal experto en diseño de rutinas personalizadas.

ALUMNO: {nombre_alumno}
NIVEL: {nivel}
DÍAS POR SEMANA: {dias}
OBJETIVOS: {objetivos}

EJERCICIOS DISPONIBLES (selecciona solo de aquí):
{ejercicios_json}

Genera una rutina de {dias} días usando SOLO ejercicios de la lista.
Responde en JSON válido con esta estructura:

{{
  "nombre": "nombre de la rutina",
  "descripcion": "descripción breve",
  "ejercicios": [
    {{
      "id_ejercicio": 1,
      "nombre": "nombre del ejercicio",
      "series": 3,
      "repeticiones": 10,
      "descanso_segundos": 60
    }}
  ],
  "total_ejercicios": 6,
  "minutos_aproximados": 45
}}
"""
        return prompt