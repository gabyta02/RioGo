from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FavoritoItem(BaseModel):
    id_favorito: int
    id_sitio: int
    nombre: str
    categoria: str
    subcategoria: str
    descripcion_corta: Optional[str] = None
    imagen_principal: Optional[str] = None
    ubicacion: Optional[dict] = None
    fecha_agregado: datetime

    class Config:
        from_attributes = True


class FavoritosListaRespuesta(BaseModel):
    total: int
    favoritos: list[FavoritoItem]


class FavoritoEstadoRespuesta(BaseModel):
    id_sitio: int
    es_favorito: bool


class FavoritoAccionRespuesta(BaseModel):
    message: str
    id_sitio: int
    es_favorito: bool
