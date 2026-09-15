from sqlalchemy import Column, BigInteger, String, Text, Boolean
from sqlalchemy.dialects.postgresql import GEOMETRY

from core.conexion import Base


class RutaTuristica(Base):
    __tablename__ = "rutas_turistica"
    __table_args__ = {"schema": "gis"}

    id_ruta = Column(BigInteger, primary_key=True)
    tipo_ruta = Column(String(50))
    titulo = Column(String(150))
    url_imagen = Column(Text)
    descripcion = Column(Text)
    geom_linea = Column(GEOMETRY("LINESTRING", 4326))
    activo = Column(Boolean)


class RutaPunto(Base):
    __tablename__ = "ruta_puntos"
    __table_args__ = {"schema": "gis"}

    id_ruta_punto = Column(BigInteger, primary_key=True)
    id_ruta = Column(BigInteger)
    id_sitio = Column(BigInteger)
    punto_inicio = Column(GEOMETRY("POINT", 4326))
    punto_fin = Column(GEOMETRY("POINT", 4326))
    orden = Column(BigInteger)
    activo = Column(Boolean)