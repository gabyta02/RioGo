from typing import Union

from pydantic import BaseModel, Field

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta


class BusquedaReferenciaEntrada(FiltroIdsConsulta):
    direccion_referencia: str = Field(min_length=1, max_length=300)


class BusquedaReferenciaExito(BaseModel):
    ids_sitio: list[int]
    estado_busqueda: EstadoBusqueda | None = None


class BusquedaReferenciaSinSitios(BaseModel):
    sin_sitios: str
    estado_busqueda: EstadoBusqueda | None = None


class BusquedaReferenciaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


BusquedaReferenciaSalida = Union[
    BusquedaReferenciaExito,
    BusquedaReferenciaSinSitios,
    BusquedaReferenciaFallo,
]
