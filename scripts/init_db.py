# scripts/init_db.py
"""
Script para inicializar la base de datos con todos los modelos.

Uso:
    python scripts/init_db.py create
    python scripts/init_db.py drop
"""

from sqlalchemy import create_engine
import os
from pathlib import Path

# Agregar el directorio padre al path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import Base, DATABASE_URL

# Importar todos los modelos para que se registren en Base.metadata
from models.user import Usuario, RolEnum
from models.routine import Rutina
from models.routine_exercise import RutinaEjercicio
from models.exercise import Ejercicio
from models.assignment import Asignacion, EstadoAsignacion
from models.review import Resena
from models.message import Mensaje
from models.payment import Pago, Suscripcion, EstadoPago


def init_db():
    """Crea todas las tablas en la base de datos"""
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)

    print("Creando tablas en la base de datos...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas creadas exitosamente")

    # Mostrar tablas creadas
    print("\nTablas disponibles:")
    for table_name in sorted(Base.metadata.tables.keys()):
        print(f"  - {table_name}")

    engine.dispose()


def drop_db():
    """Elimina todas las tablas (SOLO PARA DESARROLLO)"""
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)

    respuesta = input("⚠️  ¿Seguro que deseas eliminar todas las tablas? (s/n): ")
    if respuesta.lower() != 's':
        print("Operación cancelada")
        return

    print("Eliminando tablas...")
    Base.metadata.drop_all(bind=engine)
    print("✅ Tablas eliminadas")

    engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gestión de base de datos")
    parser.add_argument("action", choices=["create", "drop"], help="Acción a ejecutar")

    args = parser.parse_args()

    if args.action == "create":
        init_db()
    elif args.action == "drop":
        drop_db()