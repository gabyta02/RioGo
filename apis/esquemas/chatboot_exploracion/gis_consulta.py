from typing import Literal, Union

from pydantic import BaseModel, Field

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta

UnidadGisConsulta = Literal["", "m", "km"]
EntidadGisConsulta = Literal["sitio", "ruta"]
ModoBusquedaGisConsulta = Literal["progresivo", "fijo"]
CodigoRetroalimentacionGis = Literal[
    "encontrado_en_radio_progresivo",
    "encontrado_en_radio_fijo",
    "sin_coincidencias_en_radios",
]


class UbicacionUsuario(BaseModel):
    lat: float
    lon: float | None = None
    lng: float | None = None

    def coordenadas(self) -> dict[str, float] | None:
        lat = self.lat
        lon = self.lon if self.lon is not None else self.lng
        if lon is None:
            return None
        return {"lat": lat, "lon": lon}


class GisConsultaEntrada(FiltroIdsConsulta):
    entidad: EntidadGisConsulta = "sitio"
    usar_ubicacion_usuario: bool | None = None
    distancia: float | None = Field(default=None, gt=0)
    unidad: UnidadGisConsulta = ""
    punto_referencia: str = ""
    excluir_zonas: list[str] = Field(default_factory=list)
    ubicacion_usuario: UbicacionUsuario | None = None


class CandidatoGisSitioItem(BaseModel):
    id_sitio: int
    nombre: str
    distancia_metros: float
    distancia_aproximada: str


class CandidatoGisRutaItem(BaseModel):
    id_ruta: int
    titulo: str
    distancia_metros: float
    distancia_aproximada: str


class RetroalimentacionGis(BaseModel):
    codigo: CodigoRetroalimentacionGis
    modo_busqueda: ModoBusquedaGisConsulta
    radio_aplicado_metros: float | None = None
    radios_intentados_metros: list[float] = Field(default_factory=list)
    mensaje: str


class GisConsultaExitoSitios(BaseModel):
    ids_sitio: list[int]
    candidatos: list[CandidatoGisSitioItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionGis
    estado_busqueda: EstadoBusqueda | None = None


class GisConsultaExitoRutas(BaseModel):
    ids_ruta: list[int]
    candidatos: list[CandidatoGisRutaItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionGis
    estado_busqueda: EstadoBusqueda | None = None


class GisConsultaSinSitios(BaseModel):
    sin_sitios: str
    candidatos: list[CandidatoGisSitioItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionGis
    estado_busqueda: EstadoBusqueda | None = None


class GisConsultaSinRutas(BaseModel):
    sin_rutas: str
    candidatos: list[CandidatoGisRutaItem] = Field(default_factory=list)
    retroalimentacion: RetroalimentacionGis
    estado_busqueda: EstadoBusqueda | None = None


class GisConsultaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


GisConsultaSalida = Union[
    GisConsultaExitoSitios,
    GisConsultaExitoRutas,
    GisConsultaSinSitios,
    GisConsultaSinRutas,
    GisConsultaFallo,
]
