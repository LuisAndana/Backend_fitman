# config/database.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv, find_dotenv, dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 1) localizar .env
dotenv_path = find_dotenv(usecwd=True)
if not dotenv_path:
    repo_root_env = Path(__file__).resolve().parents[1] / ".env"
    if repo_root_env.exists():
        dotenv_path = str(repo_root_env)

# 2) cargar .env forzando override de variables existentes
load_dotenv(dotenv_path=dotenv_path if dotenv_path else None, override=True)

# 3) leer variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    parsed = dotenv_values(dotenv_path) if dotenv_path else {}
    hint_path = dotenv_path or (Path(__file__).resolve().parents[1] / ".env")
    raise RuntimeError(
        "DATABASE_URL no está definido (viene None o vacío).\n"
        f"Revisé .env en: {hint_path}\n"
        f"Claves detectadas en el .env: {', '.join(parsed.keys()) or '(ninguna)'}\n\n"
        "Ejemplo (SQLAlchemy síncrono con PyMySQL):\n"
        "DATABASE_URL=mysql+pymysql://root:0405@127.0.0.1:3306/gym_rutinas?charset=utf8mb4\n"
        "Si tu contraseña tiene símbolos, usa percent-encoding (p. ej. @ -> %40)."
    )

# --- Engine y Session (modo síncrono) ---
engine = create_engine(
    DATABASE_URL,
    echo=True,           # 🔎 verás SELECT/UPDATE/COMMIT en consola
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # no desasocia objetos tras commit
    future=True,
)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator:
    db = SessionLocal()
    try:
        # Debug útil: confirma a qué BD apunta la sesión
        try:
            print(">> get_db URL:", str(db.bind.url))
        except Exception:
            pass
        yield db
    finally:
        db.close()
