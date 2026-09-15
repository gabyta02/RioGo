from __future__ import annotations

from typing import Any, Literal

from typing_extensions import NotRequired, TypedDict


class MensajeAppContenido(TypedDict, total=False):
    texto: str
    origen: str
    accion: str
    label: str
    id_sitio: int
    nombre_sitio: str
    url: str
    lat: float
    lon: float
    imagenes: list[dict[str, Any]]
    ids_asociados: list[int]
    opciones: list[Any]


class MensajeApp(TypedDict):
    tipo: Literal[
        "globo",
        "card",
        "stream",
        "accion",
        "ids_asociados",
        "opciones",
        "multimedia",
    ]
    mensaje: MensajeAppContenido


class RiesgoPromptInyection(TypedDict):
    score: float
    porcentaje: float
    bloqueado: bool
    coincidencias: list[dict[str, Any]]
    motivo_principal: str | None


class PalabraInyectada(TypedDict):
    palabra: str
    significado: str
    confianza: str
    score: int
    variante: str
    texto_detectado: str
    termino_normalizado: NotRequired[str]
    correccion_aplicada: NotRequired[bool]
    correccion_sugerida: NotRequired[bool]


class DiaContextoTemporal(TypedDict, total=False):
    fecha: str
    dia_semana: str
    dia_semana_etiqueta: str
    relativo: str


class ContextoTemporal(TypedDict):
    zona_horaria: str
    fecha_actual: str
    dia_actual: str
    dia_actual_etiqueta: str
    hora_actual: str
    dias: list[DiaContextoTemporal]
    proxima_ocurrencia: dict[str, str]


class ClasificacionMensaje(TypedDict):
    mensaje_usuario: str
    texto_limpio: str
    riesgo_prompt_inyection: RiesgoPromptInyection
    palabras_inyectadas: list[PalabraInyectada]
    contexto_temporal: NotRequired[ContextoTemporal]


class ClasificacionFinal(TypedDict):
    pregunta_chatboot: Literal["pregunta_directa", "exploracion"]
    mensaje: ClasificacionMensaje
    client_message_id: str
    sesion_id: str
    id_usuario: NotRequired[int]
    ubicacion_usuario: dict[str, Any]
    id_sitio: NotRequired[int]
    nombre_sitio: NotRequired[str]
    mensaje_sistema: NotRequired[str]
    mensaje_app: NotRequired[MensajeApp]
    exploracion: NotRequired[dict[str, Any]]
    pregunta_directa: NotRequired[dict[str, Any]]


class SharedFlowState(TypedDict):
    pregunta_chatboot: Literal["pregunta_directa", "exploracion"]
    client_message_id: str
    sesion_id: str
    id_usuario: int | None
    ubicacion_usuario: dict[str, Any]
    id_sitio: int | None
    nombre_sitio: str | None
    mensaje_original: str
    mensaje_limpio: str
    riesgo_prompt_inyection: RiesgoPromptInyection
    palabras_inyectadas: list[PalabraInyectada]
    contexto_temporal: NotRequired[ContextoTemporal]
    bloqueado: bool
    motivo_bloqueo: str | None
    mensaje_sistema: str | None
    origen_mensaje_sistema: str | None
    clasificacion_final: ClasificacionFinal | None
