from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta

OperadorPrecioConsulta = Literal["", "=", "<", "<=", ">", ">="]
EtiquetaPrecioConsulta = Literal["", "economico", "moderado", "medio", "alto"]


class PrecioConsultaEntrada(FiltroIdsConsulta):
    es_gratuito: bool | None = None
    precio_numero: float | None = Field(default=None, ge=0)
    operador: OperadorPrecioConsulta = ""
    etiqueta: EtiquetaPrecioConsulta = ""
    excluir_etiquetas: list[str] = Field(default_factory=list)

    @field_validator("etiqueta", mode="before")
    @classmethod
    def normalizar_etiqueta_entrada(cls, valor: str | None) -> str:
        if valor is None:
            return ""
        texto = str(valor).strip().lower()
        if texto == "moderado":
            return "medio"
        return texto

    @field_validator("etiqueta")
    @classmethod
    def validar_etiqueta(cls, valor: str) -> str:
        if valor and valor not in {"economico", "medio", "alto"}:
            raise ValueError(
                "etiqueta debe ser vacía, 'economico', 'medio' o 'alto'."
            )
        return valor


class CandidatoPrecioItem(BaseModel):
    id_sitio: int
    es_gratuito: bool | None = None
    precio_min: float | None = None
    precio_max: float | None = None
    etiqueta_precio: str | None = None
    criterio_cumplido: bool = False


class PrecioConsultaExito(BaseModel):
    ids_sitio: list[int]
    candidatos: list[CandidatoPrecioItem] = Field(default_factory=list)
    estado_busqueda: EstadoBusqueda | None = None


class PrecioConsultaSinSitios(BaseModel):
    sin_sitios: str
    candidatos: list[CandidatoPrecioItem] = Field(default_factory=list)
    estado_busqueda: EstadoBusqueda | None = None


class PrecioConsultaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


PrecioConsultaSalida = Union[
    PrecioConsultaExito,
    PrecioConsultaSinSitios,
    PrecioConsultaFallo,
]
