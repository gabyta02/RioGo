from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

EstadoAtractivo = Literal["activo", "inactivo", "all"]
ServicioFiltro = Literal["wifi", "parqueadero", "mascotas", "accesibilidad", "all"]
PrecioFiltro = Literal["gratis", "pagado", "all"]
TipoSitio = Literal[
    "servicio_turistico",
    "atractivo_turistico",
    "operadora_turistica",
    "desconocido",
]
EtiquetaPrecio = Literal["economico", "medio", "alto", "desconocido"]


class CategoriaCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    activo: bool = True


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    activo: bool | None = None


class EstadoActivoUpdate(BaseModel):
    activo: bool


class CategoriaResponse(BaseModel):
    id_categoria: int
    nombre: str
    activo: bool


class SubcategoriaCreate(BaseModel):
    id_categoria: int = Field(ge=1)
    nombre: str = Field(min_length=2, max_length=100)
    activo: bool = True


class SubcategoriaUpdate(BaseModel):
    id_categoria: int | None = Field(default=None, ge=1)
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    activo: bool | None = None


class SubcategoriaResponse(BaseModel):
    id_subcategoria: int
    id_categoria: int
    nombre: str
    activo: bool


class SubcategoriaDetalleResponse(SubcategoriaResponse):
    total_atractivos: int


class CategoriaDetalleResponse(CategoriaResponse):
    total_atractivos: int
    total_subcategorias: int
    subcategorias: list[SubcategoriaDetalleResponse]


class HorarioDetalleCreate(BaseModel):
    dia_semana: int = Field(ge=1, le=7)
    cerrado: bool = False
    hora_inicio: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    hora_fin: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class HorarioCreate(BaseModel):
    abierto_24h: bool
    dias_semana: list[int] = Field(default_factory=list)
    hora_inicio: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    hora_fin: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    comentario: str | None = Field(default=None, max_length=200)
    detalles: list[HorarioDetalleCreate] = Field(default_factory=list)


class ContactoCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    contenido: str = Field(min_length=1, max_length=200)


class MultimediaCreate(BaseModel):
    url: str = Field(min_length=1)
    es_principal: bool = False


class PrecioCreate(BaseModel):
    es_gratuito: bool
    precio_min: Decimal | None = Field(default=None, ge=0)
    precio_max: Decimal | None = Field(default=None, ge=0)
    etiqueta_precio: EtiquetaPrecio = "desconocido"
    tarifa_acceso: Decimal | None = Field(default=None, ge=0)
    condicion_tarifa: str | None = Field(default=None, max_length=150)


class SitioCreate(BaseModel):
    id_parroquia: int | None = Field(default=None, ge=1)
    id_plataforma: int | None = Field(default=None, ge=1)
    id_categoria: int = Field(ge=1)
    id_subcategoria: int = Field(ge=1)
    tipo: TipoSitio = "atractivo_turistico"
    nombre: str = Field(min_length=2, max_length=180)
    descripcion_corta: str = Field(min_length=5, max_length=350)
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)
    es_gratuito: bool | None = None
    permite_mascotas: bool | None = None
    parqueadero: bool | None = None
    tiene_wifi: bool | None = None
    accesibilidad: bool | None = None
    activo: bool = True
    direccion_texto: str = Field(min_length=5, max_length=200)
    referencia_adicional: str = Field(min_length=3, max_length=200)
    horario: HorarioCreate
    contactos: list[ContactoCreate] = Field(min_length=1)
    multimedia: list[MultimediaCreate] = Field(min_length=1)
    precio: PrecioCreate


class SitioResponse(BaseModel):
    id_sitio: int
    nombre: str
    descripcion_corta: str | None = None
    id_categoria: int
    categoria: str
    id_subcategoria: int | None = None
    subcategoria: str | None = None
    activo: bool
    imagen_url: str | None = None


class DireccionResponse(BaseModel):
    direccion_texto: str
    referencia_adicional: str | None = None
    latitud: float | None = None
    longitud: float | None = None


class HorarioDetalleResponse(BaseModel):
    dia_semana: int
    cerrado: bool
    hora_inicio: str | None = None
    hora_fin: str | None = None


class HorarioResponse(BaseModel):
    abierto_24h: bool
    dias_semana: list[int]
    hora_inicio: str | None = None
    hora_fin: str | None = None
    comentario: str | None = None
    detalles: list[HorarioDetalleResponse] = Field(default_factory=list)


class ContactoResponse(BaseModel):
    nombre: str
    contenido: str


class MultimediaResponse(BaseModel):
    url: str
    es_principal: bool


class PrecioResponse(BaseModel):
    es_gratuito: bool
    precio_min: Decimal | None = None
    precio_max: Decimal | None = None
    etiqueta_precio: EtiquetaPrecio = "desconocido"
    tarifa_acceso: Decimal | None = None
    condicion_tarifa: str | None = None


class SitioDetalleResponse(SitioResponse):
    id_parroquia: int | None = None
    id_plataforma: int | None = None
    tipo: TipoSitio
    permite_mascotas: bool | None = None
    parqueadero: bool | None = None
    tiene_wifi: bool | None = None
    accesibilidad: bool | None = None
    direccion: DireccionResponse
    horario: HorarioResponse
    contactos: list[ContactoResponse]
    multimedia: list[MultimediaResponse]
    precio: PrecioResponse


class SitiosListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[SitioResponse]


class CatalogoSimpleResponse(BaseModel):
    id: int
    nombre: str
    activo: bool
    id_parroquia: int | None = None


class ImagenSubidaResponse(BaseModel):
    nombre_archivo: str
    url: str
