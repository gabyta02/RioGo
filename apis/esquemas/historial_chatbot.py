from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class MensajeHistorialOut(BaseModel):
    id_mensaje: int
    client_mensaje_id: str | None = None
    rol: str
    contenido: str
    creado_en: datetime
    categoria: list[str] | None = None
    subcategoria: list[str] | None = None
    entidad_asociada: str | None = None


class ConversacionHistorialOut(BaseModel):
    id_conversacion: int
    session_id: str
    titulo: str | None = None
    tipo: Literal["general", "sitio", "mixto"]
    ultimo_mensaje: str | None = None
    ultimo_rol: str | None = None
    ultimo_mensaje_en: datetime | None = None
    total_mensajes: int = 0


class DetalleConversacionHistorialOut(BaseModel):
    id_conversacion: int
    session_id: str
    titulo: str | None = None
    tipo: Literal["general", "sitio", "mixto"]
    entidad_asociada: str | None = None
    mensajes: list[MensajeHistorialOut] = Field(default_factory=list)


class ListaConversacionesOut(BaseModel):
    items: list[ConversacionHistorialOut] = Field(default_factory=list)
    total: int = 0


class ListaMensajesOut(BaseModel):
    items: list[MensajeHistorialOut] = Field(default_factory=list)
    total: int = 0


class HistorialResumenOut(BaseModel):
    total_conversaciones: int = 0
    total_explorador: int = 0
    total_detalle: int = 0
    ultima_conversacion_id: int | None = None
    ultima_fecha: datetime | None = None