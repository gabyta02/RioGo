from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

EstadoNoticia = Literal["activo", "inactivo", "publicada", "vencida", "all"]
EstadoVisualNoticia = Literal["publicada", "vencida", "inactiva"]


class NoticiaCreate(BaseModel):
    titulo: str = Field(min_length=2, max_length=200)
    imagen_url: str | None = None
    fecha_inicio: date
    fecha_fin: date | None = None
    activa: bool = True

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fecha_fin is not None and self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin debe ser mayor o igual a fecha_inicio")
        return self


class NoticiaUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=2, max_length=200)
    imagen_url: str | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    activa: bool | None = None

    @model_validator(mode="after")
    def validar_fechas(self):
        if (
            self.fecha_inicio is not None
            and self.fecha_fin is not None
            and self.fecha_fin < self.fecha_inicio
        ):
            raise ValueError("fecha_fin debe ser mayor o igual a fecha_inicio")
        return self


class EstadoNoticiaUpdate(BaseModel):
    activa: bool


class NoticiaResponse(BaseModel):
    id_noticia: int
    titulo: str
    imagen_url: str | None = None
    fecha_inicio: date
    fecha_fin: date | None = None
    activa: bool
    estado_visual: EstadoVisualNoticia


class NoticiasListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[NoticiaResponse]


class ImagenNoticiaResponse(BaseModel):
    url: str
    nombre_archivo: str


class NoticiaUsuarioResponse(BaseModel):
    id_noticia: int
    titulo: str
    imagen_url: str | None = None
    fecha_inicio: date
    fecha_fin: date | None = None


class NoticiasUsuarioListResponse(BaseModel):
    total: int
    noticias: list[NoticiaUsuarioResponse]


class NoticiasUsuarioEstadoResponse(BaseModel):
    ultimo_id: int
    total: int
