# services/user_service.py
from sqlalchemy.orm import Session
from models.user import Usuario, RolEnum
from schemas.user import UsuarioCreate
from utils.security import hash_password

def create_user(db: Session, data: UsuarioCreate) -> Usuario:
    u = Usuario(
        nombre=data.nombre, apellido=data.apellido,
        email=data.email, rol=RolEnum(data.rol),
        password=hash_password(data.password)
    )
    db.add(u); db.commit(); db.refresh(u)
    return u

def get_by_email(db: Session, email: str) -> Usuario | None:
    return db.query(Usuario).filter(Usuario.email==email).first()
