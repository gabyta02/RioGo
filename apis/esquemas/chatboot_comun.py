from typing import Any, Literal

from pydantic import BaseModel, Field

EstadoFiltroBusqueda = Literal["cumplido", "no_cumplido", "aproximado", "error"]


class FiltroIdsConsulta(BaseModel):
    ids_consulta: list[int] = Field(default_factory=list)


class FiltroBusqueda(BaseModel):
    nombre: str
    valor: dict[str, Any] = Field(default_factory=dict)
    estado: EstadoFiltroBusqueda
    detalle: str = ""


class EstadoBusqueda(BaseModel):
    estado: EstadoFiltroBusqueda
    ids_entrada: list[int] = Field(default_factory=list)
    ids_salida: list[int] = Field(default_factory=list)
    filtros: list[FiltroBusqueda] = Field(default_factory=list)
    retroalimentacion: dict[str, Any] = Field(default_factory=dict)
