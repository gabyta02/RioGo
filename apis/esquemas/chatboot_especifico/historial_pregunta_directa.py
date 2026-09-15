from typing import Any

from pydantic import BaseModel, Field


class HistorialPreguntaDirectaEntrada(BaseModel):
    id_usuario: int | None = None
    sesion_id: str = ""
    client_message_id: str = ""
    texto_usuario: str = ""
    respuesta_json: dict[str, Any] = Field(default_factory=dict)
    entidad_asociada: str = ""


class HistorialPreguntaDirectaSalida(BaseModel):
    id_conversacion: int | None = None
    client_message_id: str
    usuario_guardado: bool
    respuesta_guardada: bool
    mensaje: str
