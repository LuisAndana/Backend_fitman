# db.py
import os
import mysql.connector
from dotenv import load_dotenv

from config.database import dotenv_path

load_dotenv()

# --- después de load_dotenv(...) ---
from dotenv import dotenv_values

DATABASE_URL = os.getenv("DATABASE_URL")

# fallback por si la clave llega como \ufeffDATABASE_URL
if not DATABASE_URL:
    parsed = dotenv_values(dotenv_path) if 'dotenv_path' in globals() and dotenv_path else {}
    DATABASE_URL = parsed.get("DATABASE_URL") or parsed.get("\ufeffDATABASE_URL")


def get_connection():
    cn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "0405"),
        database=os.getenv("DB_NAME", "gym_rutinas"),
        auth_plugin='mysql_native_password'
    )
    return cn
