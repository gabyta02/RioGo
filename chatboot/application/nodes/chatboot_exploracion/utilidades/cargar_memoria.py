from __future__ import annotations

from typing import Any


def _normalizar_turnos(memoria_raw: dict[str, Any]) -> dict[str, Any]:
    preguntas = memoria_raw.get("preguntas") or []
    turnos: list[dict[str, Any]] = []

    for indice, pregunta in enumerate(preguntas, start=1):
        if not isinstance(pregunta, dict):
            continue
        turnos.append(
            {
                "turno": indice,
                "pregunta": str(pregunta.get("texto") or "").strip(),
                "respuesta": pregunta.get("resultado"),
            }
        )

    entidades_raw = memoria_raw.get("entidades") or []
    entidades = [
        str(entidad).strip()
        for entidad in entidades_raw
        if str(entidad or "").strip()
    ]

    return {"turnos": turnos, "entidades": entidades}


def cargar_memoria_exploracion(state: dict[str, Any]) -> dict[str, Any]:
    from infrastructure.memory import cargar_memoria

    sesion_id = str(state.get("sesion_id") or "")
    memoria_raw = cargar_memoria(sesion_id)
    return {
        **state,
        "memoria": _normalizar_turnos(memoria_raw),
    }
