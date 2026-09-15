from typing import Union

from pydantic import BaseModel, Field

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta


class AtributosBooleanosConsultaEntrada(FiltroIdsConsulta):
    tiene_wifi: bool | None = None
    permite_mascotas: bool | None = None
    accesibilidad: bool | None = None
    parqueadero: bool | None = None
    es_gratuito: bool | None = None
    excluir: list[str] = Field(default_factory=list)


class AtributosBooleanosConsultaExito(BaseModel):
    ids_sitio: list[int]
    estado_busqueda: EstadoBusqueda | None = None


class AtributosBooleanosConsultaSinSitios(BaseModel):
    sin_sitios: str
    estado_busqueda: EstadoBusqueda | None = None


class AtributosBooleanosConsultaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


AtributosBooleanosConsultaSalida = Union[
    AtributosBooleanosConsultaExito,
    AtributosBooleanosConsultaSinSitios,
    AtributosBooleanosConsultaFallo,
]
