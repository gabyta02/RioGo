from __future__ import annotations

from typing import Any

from typing_extensions import NotRequired, TypedDict

from application.state import MensajeApp, PalabraInyectada


class ExploracionState(TypedDict):
    sesion_id: str
    client_message_id: str
    ubicacion_usuario: dict[str, Any]
    texto_usuario: str
    score_prompt_inyection: float
    palabras_inyectadas: list[str | PalabraInyectada]
    contexto_temporal: NotRequired[dict[str, Any]]
    memoria: dict[str, Any]
    prompt_clasificacion: str
    respuesta_llm_cruda: str
    plan: dict[str, Any] | None
    plan_valido: bool
    errores_formato: list[dict[str, Any]]
    mensaje_sistema: str | None
    mensaje_app: MensajeApp | None
    resultado_exploracion: dict[str, Any] | None
    estados_herramientas: NotRequired[list[dict[str, Any]]]
    ids_asociados: NotRequired[list[int]]
    mensajes_app: NotRequired[list[dict[str, Any]]]
    entidades_resueltas: NotRequired[list[str]]
