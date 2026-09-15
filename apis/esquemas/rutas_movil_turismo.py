from pydantic import BaseModel, Field


class CoordenadaRutaMovilTurismo(BaseModel):
    latitud: float
    longitud: float
    orden: int


class PuntoRutaMovilTurismo(BaseModel):
    id_ruta_punto: int
    id_sitio: int | None = None
    nombre_sitio: str | None = None
    orden: int
    punto_inicio: bool = False
    punto_fin: bool = False
    latitud: float | None = None
    longitud: float | None = None


class RutaMovilTurismo(BaseModel):
    id_ruta: int
    tipo_ruta: str
    titulo: str
    url_imagen: str | None = None
    descripcion: str | None = None
    color: str
    leyenda: str
    activo: bool
    coordenadas: list[CoordenadaRutaMovilTurismo] = []
    puntos: list[PuntoRutaMovilTurismo] = []


class RutasMovilTurismoResponse(BaseModel):
    total: int
    rutas: list[RutaMovilTurismo]
