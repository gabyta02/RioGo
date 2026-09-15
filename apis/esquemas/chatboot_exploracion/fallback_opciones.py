from pydantic import BaseModel, Field


class OpcionFallbackExploracion(BaseModel):
    categoria: str
    subcategorias: list[str] = Field(default_factory=list)


class OpcionesFallbackExploracionSalida(BaseModel):
    opciones: list[OpcionFallbackExploracion] = Field(default_factory=list)
