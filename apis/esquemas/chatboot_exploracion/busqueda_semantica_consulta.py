from typing import Literal, Union

from pydantic import BaseModel, Field

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta

CodigoRetroalimentacionSemantica = Literal[
    "encontrado_en_alcance_previo",
    "busqueda_global_por_sin_coincidencias_en_alcance",
    "busqueda_global_sin_filtro_previo",
    "sin_coincidencias_en_alcance_y_global",
]

AlcanceBusquedaSemantica = Literal["ids_consulta", "global"]


class BusquedaSemanticaConsultaEntrada(FiltroIdsConsulta):
    texto_embeddings: str = Field(min_length=1, max_length=500)
    keywords: list[str] = Field(default_factory=list)
    excluir_terminos: list[str] = Field(default_factory=list)


class CandidatoSemanticoItem(BaseModel):
    id_sitio: int
    nombre: str
    score_semantico: float
    score_final: float
    boost_keywords: float
    keywords_match: list[str] = Field(default_factory=list)
    supera_umbral: bool
    motivo: str
    id_chunk: str | None = None
    contenido_chunk: str | None = None


class RetroalimentacionSemantica(BaseModel):
    codigo: CodigoRetroalimentacionSemantica
    alcance_busqueda: AlcanceBusquedaSemantica
    fallback_global_aplicado: bool
    ids_consulta_entrada: list[int] = Field(default_factory=list)
    mensaje: str


class BusquedaSemanticaExito(BaseModel):
    ids_sitio: list[int]
    candidatos: list[CandidatoSemanticoItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionSemantica
    estado_busqueda: EstadoBusqueda | None = None


class BusquedaSemanticaSinSitios(BaseModel):
    sin_sitios: str
    candidatos: list[CandidatoSemanticoItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionSemantica
    estado_busqueda: EstadoBusqueda | None = None


class BusquedaSemanticaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


BusquedaSemanticaConsultaSalida = Union[
    BusquedaSemanticaExito,
    BusquedaSemanticaSinSitios,
    BusquedaSemanticaFallo,
]
