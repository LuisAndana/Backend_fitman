# scripts/migrate_to_bcrypt.py
from sqlalchemy import select
from config.database import SessionLocal
from models.user import Usuario
from utils.passwords import verify_password, hash_password

def looks_hashed_bcrypt(s: str) -> bool:
    return s.startswith(("$2a$", "$2b$", "$2y$"))

def looks_pbkdf2(s: str) -> bool:
    return s.startswith("$pbkdf2-sha256$") or s.startswith("pbkdf2_sha256$") or s.startswith("pbkdf2:")

def main():
    s = SessionLocal()
    try:
        users = s.execute(select(Usuario)).scalars().all()
        changed = 0
        for u in users:
            pwd = (u.password or "").strip()
            if not pwd or pwd in {"GOOGLE", "GOOGLE_OAUTH_ONLY"}:
                continue
            if looks_hashed_bcrypt(pwd):
                continue  # ya está bien
            # pide contraseña al usuario? no. Re-hasheamos usando su propio hash sólo si podemos verificar contra sí mismo:
            # aquí no conocemos la contraseña en texto, así que solo podemos migrar en "login" real.
            # Mejor: migra "al vuelo" en el login cuando verify_password(...) True y el hash no sea bcrypt:
            #   u.password = hash_password(plain)
            #   s.add(u); s.commit()
        print("Listo. (Migración real ocurre al hacer login con éxito si no era bcrypt).")
    finally:
        s.close()

if __name__ == "__main__":
    main()
