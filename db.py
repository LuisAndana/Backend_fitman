# db.py — solo conexión, sin JWT ni lógica al importar
from __future__ import annotations

import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.pooling import PooledMySQLConnection
from mysql.connector.abstracts import MySQLConnectionAbstract

# Carga variables del .env (si existe)
load_dotenv()

def get_connection() -> PooledMySQLConnection | MySQLConnection | MySQLConnectionAbstract:
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "0405"),
        database=os.getenv("DB_NAME", "gym_rutinas"),
        auth_plugin="mysql_native_password",
    )
