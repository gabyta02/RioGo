from typing import Union

from pydantic import BaseModel, Field

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta


class PreguntaDirectaEntrada(FiltroIdsConsulta):
    nombre_entidad: str = ""


class PreguntaDirectaExito(BaseModel):
    ids_sitio: list[int]
    id_sitio: int
    nombre: str
    score: float
    mensaje: str
    estado_busqueda: EstadoBusqueda | None = None


class PreguntaDirectaSinSitios(BaseModel):
    sin_sitios: str
    sugerencias: list[PreguntaDirectaExito] = Field(default_factory=list)
    estado_busqueda: EstadoBusqueda | None = None


class PreguntaDirectaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


PreguntaDirectaSalida = Union[
    PreguntaDirectaExito,
    PreguntaDirectaSinSitios,
    PreguntaDirectaFallo,
]
