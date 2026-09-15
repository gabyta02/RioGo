from typing import Literal

from pydantic import BaseModel, Field

TipoRuta = Literal["Senderismo", "Ciclismo", "Caminata Urbana", "Montañismo", "Otras"]
EstadoRuta = Literal["activo", "inactivo", "all"]
TipoPuntoRuta = Literal["inicio", "fin", "libre", "sitio"]


class Coordenada(BaseModel):
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)


class RutaPuntoCreate(BaseModel):
    orden: int = Field(ge=1)
    id_sitio: int | None = Field(default=None, ge=1)
    punto_inicio: Coordenada | None = None
    punto_fin: Coordenada | None = None


class RutaPuntoGeometriaCreate(BaseModel):
    orden: int = Field(ge=1)
    tipo: TipoPuntoRuta
    id_sitio: int | None = Field(default=None, ge=1)
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)


class RutaGeometriaUpdate(BaseModel):
    linea: list[Coordenada] = Field(default_factory=list)
    puntos: list[RutaPuntoGeometriaCreate] = Field(default_factory=list)


class RutaCreate(BaseModel):
    tipo_ruta: TipoRuta
    titulo: str = Field(min_length=2, max_length=150)
    url_imagen: str | None = None
    descripcion: str | None = None
    activo: bool = True
    linea: list[Coordenada] | None = None
    puntos: list[RutaPuntoCreate] = Field(default_factory=list)
    documentos: list[str] = Field(default_factory=list)


class RutaUpdate(BaseModel):
    tipo_ruta: TipoRuta | None = None
    titulo: str | None = Field(default=None, min_length=2, max_length=150)
    url_imagen: str | None = None
    descripcion: str | None = None
    activo: bool | None = None
    linea: list[Coordenada] | None = None
    puntos: list[RutaPuntoCreate] | None = None
    documentos: list[str] | None = None


class EstadoRutaUpdate(BaseModel):
    activo: bool


class RutaResponse(BaseModel):
    id_ruta: int
    tipo_ruta: TipoRuta
    titulo: str
    url_imagen: str | None = None
    descripcion: str | None = None
    activo: bool
    total_puntos: int
    tiene_linea: bool


class RutaPuntoGeometriaResponse(BaseModel):
    orden: int
    tipo: TipoPuntoRuta
    id_sitio: int | None = None
    nombre_sitio: str | None = None
    latitud: float
    longitud: float


class RutaGeometriaResponse(BaseModel):
    id_ruta: int
    titulo: str
    linea: list[Coordenada]
    puntos: list[RutaPuntoGeometriaResponse]


class SitioRutaResponse(BaseModel):
    id_sitio: int
    nombre: str
    categoria: str | None = None
    subcategoria: str | None = None
    latitud: float
    longitud: float


class ImagenRutaResponse(BaseModel):
    url: str
    nombre_archivo: str


class RutasListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[RutaResponse]
