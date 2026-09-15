from typing import Union

from pydantic import BaseModel, Field

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta


class ContactoBusquedaEntrada(FiltroIdsConsulta):
    contacto_sugerido: str = Field(min_length=1, max_length=100)
    excluir_contactos: list[str] = Field(default_factory=list)


class ContactoBusquedaExito(BaseModel):
    ids_sitio: list[int]
    estado_busqueda: EstadoBusqueda | None = None


class ContactoBusquedaSinSitios(BaseModel):
    sin_sitios: str
    estado_busqueda: EstadoBusqueda | None = None


class ContactoBusquedaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


ContactoBusquedaSalida = Union[
    ContactoBusquedaExito,
    ContactoBusquedaSinSitios,
    ContactoBusquedaFallo,
]
