from typing import Union

from pydantic import BaseModel, Field

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta


class RutaConsultaEntrada(FiltroIdsConsulta):
    tipo_ruta: str = Field(min_length=1, max_length=100)
    excluir_tipos: list[str] = Field(default_factory=list)


class RutaConsultaExito(BaseModel):
    ids_ruta: list[int]
    estado_busqueda: EstadoBusqueda | None = None


class RutaConsultaSinRutas(BaseModel):
    sin_rutas: str
    estado_busqueda: EstadoBusqueda | None = None


class RutaConsultaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


RutaConsultaSalida = Union[
    RutaConsultaExito,
    RutaConsultaSinRutas,
    RutaConsultaFallo,
]
