from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, ForeignKey, DateTime
from config.database import Base

class Rutina(Base):
    __tablename__ = "rutinas"

    id_rutina: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(150))
    # 👇 ESTA ES LA CLAVE: ForeignKey apunta a tabla.columna (no a Clase.atributo)
    creado_por_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id_usuario"),
        nullable=False,
        index=True,
    )
    creado_en: Mapped[DateTime] = mapped_column(DateTime)

    creado_por = relationship(
        "Usuario",
        back_populates="rutinas_creadas",
        foreign_keys=[creado_por_id],
    )
