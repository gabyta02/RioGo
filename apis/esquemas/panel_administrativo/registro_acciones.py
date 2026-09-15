from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

TipoAccionVisual = Literal[
    "creacion",
    "edicion",
    "actualizacion",
    "desactivacion",
    "eliminacion",
    "sesion",
    "otro",
]
ModuloRegistro = Literal[
    "all",
    "attractions",
    "categories",
    "routes",
    "noticias",
    "chatbot_content",
    "admin_accounts",
    "sistema",
]
FiltroAccion = Literal["all", "creacion", "edicion", "actualizacion", "desactivacion", "eliminacion", "sesion"]
VistaRegistro = Literal["acciones", "inicios_sesion"]
ResultadoInicioSesion = Literal["all", "exitoso", "fallido"]


class RegistroAccionItem(BaseModel):
    id_evento: int
    administrador: str
    username: str
    iniciales: str
    accion: str
    accion_label: str
    accion_tipo: TipoAccionVisual
    modulo: str
    modulo_label: str
    direccion: str
    fecha_modificacion: datetime


class RegistroAccionesListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[RegistroAccionItem]


class RegistroAccionDetalleResponse(BaseModel):
    id_evento: int
    administrador: str
    username: str
    iniciales: str
    accion: str
    accion_label: str
    accion_tipo: TipoAccionVisual
    modulo: str
    modulo_label: str
    direccion: str
    esquema_modificado: str
    tabla_modificada: str
    entidad_modificada: str | None = None
    referencia: str | None = None
    fecha_modificacion: datetime
    datos_anteriores: dict[str, Any] | None = None
    datos_nuevos: dict[str, Any] | None = None
    resultado: str | None = None
    detalle: str | None = None
    user_agent: str | None = None


class RegistroAccionesCatalogosResponse(BaseModel):
    administradores: list[str]
    modulos: list[dict[str, str]]
