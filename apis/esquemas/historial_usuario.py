from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TipoConversacion = Literal["general", "detalle", "mixto"]


class EntidadAsociadaHistorial(BaseModel):
    tipo: Literal["sitio"]
    id: int
    nombre: str


class MensajeHistorialItem(BaseModel):
    id_mensaje: int
    client_mensaje_id: str | None = None
    rol: str
    contenido: str
    creado_en: datetime
    categoria: list[str] | None = None
    subcategoria: list[str] | None = None
    entidad_asociada: EntidadAsociadaHistorial | None = None


class ConversacionResumenItem(BaseModel):
    id_conversacion: int
    session_id: str
    titulo: str | None = None
    tipo: TipoConversacion
    ultimo_mensaje: str | None = None
    ultimo_rol: str | None = None
    ultimo_mensaje_en: datetime | None = None
    creado_en: datetime | None = None
    total_mensajes: int = 0
    entidad_asociada: EntidadAsociadaHistorial | None = None


class ConversacionesListaRespuesta(BaseModel):
    items: list[ConversacionResumenItem] = Field(default_factory=list)
    total: int = 0


class ConversacionDetalleRespuesta(BaseModel):
    id_conversacion: int
    session_id: str
    titulo: str | None = None
    tipo: TipoConversacion
    creado_en: datetime | None = None
    entidad_asociada: EntidadAsociadaHistorial | None = None
    mensajes: list[MensajeHistorialItem] = Field(default_factory=list)
