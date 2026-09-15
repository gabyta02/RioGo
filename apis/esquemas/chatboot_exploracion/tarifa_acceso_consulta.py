from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta

OperadorTarifaConsulta = Literal["", "=", "<", "<=", ">", ">="]
EtiquetaTarifaConsulta = Literal["", "economico", "moderado", "medio", "alto"]
CondicionTarifaConsulta = Literal[
    "",
    "general",
    "adulto",
    "nino",
    "joven",
    "estudiante",
    "tercera_edad",
    "discapacidad",
]


class TarifaAccesoConsultaEntrada(FiltroIdsConsulta):
    entrada_gratuita: bool | None = None
    precio_numero: float | None = Field(default=None, ge=0)
    operador: OperadorTarifaConsulta = ""
    etiqueta: EtiquetaTarifaConsulta = ""
    condicion: CondicionTarifaConsulta = ""
    excluir_condiciones: list[str] = Field(default_factory=list)

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


class CandidatoTarifaAccesoItem(BaseModel):
    id_sitio: int
    precio: float | None = None
    condicion: str | None = None
    entrada_gratuita: bool | None = None
    criterio_cumplido: bool = False


class TarifaAccesoConsultaExito(BaseModel):
    ids_sitio: list[int]
    candidatos: list[CandidatoTarifaAccesoItem] = Field(default_factory=list)
    estado_busqueda: EstadoBusqueda | None = None


class TarifaAccesoConsultaSinSitios(BaseModel):
    sin_sitios: str
    candidatos: list[CandidatoTarifaAccesoItem] = Field(default_factory=list)
    estado_busqueda: EstadoBusqueda | None = None


class TarifaAccesoConsultaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


TarifaAccesoConsultaSalida = Union[
    TarifaAccesoConsultaExito,
    TarifaAccesoConsultaSinSitios,
    TarifaAccesoConsultaFallo,
]
