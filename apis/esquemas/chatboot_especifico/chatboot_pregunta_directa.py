from decimal import Decimal
from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator


class IdSitioEntrada(BaseModel):
    id_sitio: int = Field(gt=0)


class ContactoCompacto(BaseModel):
    nombre: str
    contenido: str


class HorarioCompacto(BaseModel):
    abierto_24h: bool
    texto: str
    comentario: str | None = None


class TarifaCompacta(BaseModel):
    condicion: str | None = None
    precio: float


class PrecioCompacto(BaseModel):
    texto: str
    precio_min: Decimal | None = None
    precio_max: Decimal | None = None
    etiqueta_precio: str | None = None
    tarifas: list[TarifaCompacta] = Field(default_factory=list)


class AtributosSitioCompacto(BaseModel):
    es_gratuito: bool | None = None
    parqueadero: bool | None = None
    tiene_wifi: bool | None = None
    accesibilidad: bool | None = None
    permite_mascotas: bool | None = None


class FichaSitioCompactaExito(BaseModel):
    id_sitio: int
    nombre: str
    categoria: str
    subcategoria: str
    parroquia: str | None = None
    plataforma: str | None = None
    horario: HorarioCompacto
    contactos: list[ContactoCompacto] = Field(default_factory=list)
    precio: PrecioCompacto
    atributos: AtributosSitioCompacto


class FichaSitioFallo(BaseModel):
    fallo: str


FichaSitioSalida = Union[FichaSitioCompactaExito, FichaSitioFallo]


class ImagenSitioItem(BaseModel):
    url: str
    es_principal: bool


class MultimediaSitioExito(BaseModel):
    id_sitio: int
    imagenes: list[ImagenSitioItem] = Field(default_factory=list)


MultimediaSitioSalida = Union[MultimediaSitioExito, FichaSitioFallo]


class ChunksDocumentoEntrada(IdSitioEntrada):
    mensaje_chunk: str | list[str]
    keywords: list[str] = Field(default_factory=list)

    @field_validator("mensaje_chunk", mode="before")
    @classmethod
    def normalizar_mensaje_chunk(cls, valor):
        if isinstance(valor, str):
            return valor
        if isinstance(valor, list):
            return valor
        raise ValueError("mensaje_chunk debe ser un string o una lista de strings.")


class ChunkDocumentoItem(BaseModel):
    id_chunk: str
    contenido: str
    score_semantico: float
    score_final: float
    keywords_match: list[str] = Field(default_factory=list)


EstadoChunksDocumento = Literal["ok", "chunk_baja_precision"]


class ChunksDocumentoExito(BaseModel):
    estado: EstadoChunksDocumento
    id_sitio: int
    score_maximo: float
    chunks: list[ChunkDocumentoItem] = Field(default_factory=list)


ChunksDocumentoSalida = Union[ChunksDocumentoExito, FichaSitioFallo]


class UbicacionSitio(BaseModel):
    lat: float
    lon: float


class ComoLlegarExito(BaseModel):
    id_sitio: int
    nombre: str
    ubicacion: UbicacionSitio


ComoLlegarSalida = Union[ComoLlegarExito, FichaSitioFallo]


CriterioSeleccionDocumento = Literal[
    "unico",
    "archivo_mayor",
    "mas_secciones",
    "mas_reciente",
]


class RutaDocumentoExito(BaseModel):
    id_sitio: int
    id_documento: int
    titulo: str
    ruta_archivo: str
    total_documentos: int
    criterio_seleccion: CriterioSeleccionDocumento


RutaDocumentoSalida = Union[RutaDocumentoExito, FichaSitioFallo]
