from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String

from core.conexion import Base


class RutaBus(Base):
    __tablename__ = "ruta_bus"
    __table_args__ = {"schema": "gis"}

    id_ruta = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=True)
    estado = Column(String(50), nullable=True)
    distancia_recorrido = Column(String(50), nullable=True)
    linea_bus = Column(String(50), nullable=True)
    geom = Column(Geometry("MULTILINESTRING", srid=4326), nullable=True)