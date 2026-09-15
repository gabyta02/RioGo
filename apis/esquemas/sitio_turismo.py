from typing import List, Optional

from pydantic import BaseModel


class CategoriaSalida(BaseModel):
    id_categoria: int
    nombre: str
    activo: bool

    class Config:
        from_attributes = True


class SubcategoriaSalida(BaseModel):
    id_subcategoria: int
    nombre: str
    activo: bool
    categoria: CategoriaSalida

    class Config:
        from_attributes = True


class PuntoSalida(BaseModel):
    type: str
    coordinates: List[float]


class SitioSalida(BaseModel):
    id_sitio: int
    nombre: str
    categoria: str
    subcategoria: Optional[str] = None
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    img_Url: Optional[str] = None
    point: Optional[PuntoSalida] = None

    class Config:
        from_attributes = True


class SitioCacheActualizadoSalida(BaseModel):
    accion: str
    id_sitio: int
    sitio: SitioSalida


class SitioCacheEliminadoSalida(BaseModel):
    accion: str
    id_sitio: int
    eliminado: bool


class CargaCacheSitiosSalida(BaseModel):
    total: int
