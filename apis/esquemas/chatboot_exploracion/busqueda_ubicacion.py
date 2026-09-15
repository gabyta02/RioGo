from typing import Literal, Union

from pydantic import BaseModel, Field

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta
from esquemas.chatboot_exploracion.gis_consulta import (
    CandidatoGisRutaItem,
    CandidatoGisSitioItem,
    RetroalimentacionGis,
    UbicacionUsuario,
)

TipoBusquedaUbicacion = Literal["", "zona_textual", "cercania"]
UnidadBusquedaUbicacion = Literal["", "m", "km"]
EntidadBusquedaUbicacion = Literal["sitio", "ruta"]


class BusquedaUbicacionEntrada(FiltroIdsConsulta):
    entidad: EntidadBusquedaUbicacion = "sitio"
    tipo_busqueda: TipoBusquedaUbicacion = ""
    referencia_ubicacion: str = Field(default="", max_length=300)
    usar_ubicacion_usuario: bool | None = None
    distancia: float | None = Field(default=None, gt=0)
    unidad: UnidadBusquedaUbicacion = ""
    excluir_zonas: list[str] = Field(default_factory=list)
    ubicacion_usuario: UbicacionUsuario | None = None


class BusquedaUbicacionExitoSitios(BaseModel):
    ids_sitio: list[int]
    candidatos: list[CandidatoGisSitioItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionGis | dict = Field(default_factory=dict)
    estado_busqueda: EstadoBusqueda | None = None


class BusquedaUbicacionExitoRutas(BaseModel):
    ids_ruta: list[int]
    candidatos: list[CandidatoGisRutaItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionGis | dict = Field(default_factory=dict)
    estado_busqueda: EstadoBusqueda | None = None


class BusquedaUbicacionSinSitios(BaseModel):
    sin_sitios: str
    candidatos: list[CandidatoGisSitioItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionGis | dict = Field(default_factory=dict)
    estado_busqueda: EstadoBusqueda | None = None


class BusquedaUbicacionSinRutas(BaseModel):
    sin_rutas: str
    candidatos: list[CandidatoGisRutaItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionGis | dict = Field(default_factory=dict)
    estado_busqueda: EstadoBusqueda | None = None


class BusquedaUbicacionFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


BusquedaUbicacionSalida = Union[
    BusquedaUbicacionExitoSitios,
    BusquedaUbicacionExitoRutas,
    BusquedaUbicacionSinSitios,
    BusquedaUbicacionSinRutas,
    BusquedaUbicacionFallo,
]
