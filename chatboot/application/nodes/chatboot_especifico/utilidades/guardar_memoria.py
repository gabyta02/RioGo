from __future__ import annotations

from typing import Any

MAX_TURNOS_SITIO = 5


def guardar_memoria_pregunta(state: dict[str, Any]) -> dict[str, Any]:
    from infrastructure.memory import MemoriaSitio, guardar_memoria_sitio

    sesion_id = str(state.get("sesion_id") or "").strip()
    texto_usuario = str(state.get("texto_usuario") or "").strip()
    client_message_id = str(state.get("client_message_id") or "").strip()
    respuesta = _extraer_respuesta(state)

    if not sesion_id or not texto_usuario or not client_message_id or not respuesta:
        return state

    memoria = MemoriaSitio.vacia(sesion_id)
    memoria_raw = state.get("memoria")
    if isinstance(memoria_raw, dict):
        turnos_existentes = memoria_raw.get("turnos") or []
        for turno in reversed(turnos_existentes):
            if not isinstance(turno, dict):
                continue
            pregunta = str(turno.get("pregunta") or "").strip()
            respuesta_turno = str(turno.get("respuesta") or "").strip()
            client_id_turno = str(turno.get("client_message_id") or "").strip()
            if not pregunta or not respuesta_turno or not client_id_turno:
                continue
            memoria.agregar_turno(
                pregunta=pregunta,
                respuesta=respuesta_turno,
                client_message_id=client_id_turno,
                max_turnos=MAX_TURNOS_SITIO,
            )

    memoria.agregar_turno(
        pregunta=texto_usuario,
        respuesta=respuesta,
        client_message_id=client_message_id,
        max_turnos=MAX_TURNOS_SITIO,
    )

    memoria_guardada = guardar_memoria_sitio(sesion_id, memoria.model_dump(mode="json"))
    return {
        **state,
        "memoria": {
            "turnos": [
                {
                    "turno": indice,
                    "pregunta": item.get("pregunta"),
                    "respuesta": item.get("respuesta"),
                    "client_message_id": item.get("client_message_id"),
                }
                for indice, item in enumerate(
                    memoria_guardada.get("turnos") or [],
                    start=1,
                )
                if isinstance(item, dict)
            ]
        },
    }


def _extraer_respuesta(state: dict[str, Any]) -> str:
    mensaje_app = state.get("mensaje_app")
    if isinstance(mensaje_app, dict):
        mensaje = mensaje_app.get("mensaje")
        if isinstance(mensaje, dict):
            texto = str(mensaje.get("texto") or "").strip()
            if texto:
                return texto

    mensajes_app = state.get("mensajes_app")
    if isinstance(mensajes_app, list):
        textos: list[str] = []
        for item in mensajes_app:
            if not isinstance(item, dict):
                continue
            mensaje = item.get("mensaje")
            if isinstance(mensaje, dict) and mensaje.get("texto"):
                textos.append(str(mensaje["texto"]).strip())
        if textos:
            return "\n".join(textos)

    return str(state.get("mensaje_sistema") or "").strip()
