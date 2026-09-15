from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class ImagenSalida(BaseModel):
    url: str
    es_principal: bool

    class Config:
        from_attributes = True


class EntradaMovilOut(BaseModel):
    es_gratuito: Optional[bool] = None
    texto: Optional[str] = None
    precio_min: Optional[Decimal] = None
    precio_max: Optional[Decimal] = None
    etiqueta_precio: Optional[str] = None
    tarifas: List[dict] = []


class ServiciosMovilOut(BaseModel):
    wifi: Optional[bool] = None
    parqueadero: Optional[bool] = None
    permite_mascotas: Optional[bool] = None


class SitioDetalleAppSalida(BaseModel):
    id_sitio: int
    nombre: str
    categoria: str
    subcategoria: str
    direccion: str
    horario_resumen: str
    entrada_resumen: str
    accesibilidad_resumen: str
    descripcion_corta: Optional[str] = None
    imagenes: List[ImagenSalida] = []
    entrada: Optional[EntradaMovilOut] = None
    servicios: Optional[ServiciosMovilOut] = None

    class Config:
        from_attributes = True
