from sqlalchemy import String, Integer, DateTime, Boolean
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from core.conexion import Base

class Usuario(Base):
    __tablename__ ="usuario"
    __table_args__ = {"schema": "chatbot"}

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False
    )

    activo: Mapped[str] = mapped_column(
        Boolean,
        nullable=True
    )

    password_hash: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    username: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False
    )

    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)