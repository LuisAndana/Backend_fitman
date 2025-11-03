# models/analisis_perfil.py
from sqlalchemy import Integer, String, ForeignKey, DateTime, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from config.database import Base


class AnalisisPerfil(Base):
    __tablename__ = "analisis_perfil_usuario"

    id_analisis_perfil: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    categoria_fitness: Mapped[str] = mapped_column(String(100), nullable=False)
    nivel_condicion: Mapped[str] = mapped_column(String(100), nullable=False)
    recomendaciones_entrenamiento: Mapped[str] = mapped_column(Text, nullable=False)
    recomendaciones_nutricion: Mapped[str | None] = mapped_column(Text, nullable=True)
    objetivos_sugeridos: Mapped[str | None] = mapped_column(Text, nullable=True)
    riesgos_potenciales: Mapped[str | None] = mapped_column(Text, nullable=True)
    puntuacion_general: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_analisis: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)