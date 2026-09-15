from typing import List, Optional

from pydantic import BaseModel


class GeometrySalida(BaseModel):
    type: str
    coordinates: list


class RutaBusSalida(BaseModel):
    id_ruta: int
    nombre: Optional[str] = None
    estado: Optional[str] = None
    distancia_recorrido: Optional[str] = None
    linea_bus: Optional[str] = None
    color: str
    geometry: Optional[GeometrySalida] = None

    class Config:
        from_attributes = True


class LeyendaRutaBusSalida(BaseModel):
    linea_bus: str
    color: str
    cantidad_rutas: int
