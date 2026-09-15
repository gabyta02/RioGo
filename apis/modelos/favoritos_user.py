from datetime import datetime, timezone

from sqlalchemy import Column, BigInteger, Integer, DateTime

from core.conexion import Base


def _utc_now():
    return datetime.now(timezone.utc)


class Favorito(Base):
    __tablename__ = "favorito"
    __table_args__ = {"schema": "conversacion"}

    id_favorito = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, nullable=False, index=True)
    id_sitio = Column(BigInteger, nullable=False, index=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=_utc_now)