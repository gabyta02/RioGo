from __future__ import annotations

from typing import Any


def cargar_memoria_pregunta(state: dict[str, Any]) -> dict[str, Any]:
    from infrastructure.memory import cargar_memoria_sitio

    sesion_id = str(state.get("sesion_id") or "")
    memoria_raw = cargar_memoria_sitio(sesion_id)
    return {
        **state,
        "memoria": _normalizar_turnos(memoria_raw),
    }


def _normalizar_turnos(memoria_raw: dict[str, Any]) -> dict[str, Any]:
    turnos_raw = memoria_raw.get("turnos") or []
    turnos: list[dict[str, Any]] = []
    for indice, turno in enumerate(turnos_raw, start=1):
        if not isinstance(turno, dict):
            continue
        turnos.append(
            {
                "turno": indice,
                "pregunta": str(turno.get("pregunta") or "").strip(),
                "respuesta": str(turno.get("respuesta") or "").strip(),
                "client_message_id": str(turno.get("client_message_id") or "").strip(),
            }
        )
    return {"turnos": turnos}
