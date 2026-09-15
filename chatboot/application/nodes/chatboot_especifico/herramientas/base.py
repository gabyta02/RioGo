from __future__ import annotations

from typing import Any, Literal, TypedDict

StatusHerramienta = Literal["ok", "sin_resultados", "error"]
TipoIds = Literal["sitio", "ruta"]


class ResultadoHerramienta(TypedDict):
    herramienta: str
    orden: int
    status: StatusHerramienta
    ids: list[int]
    payload: dict[str, Any]
    nota: str


def normalizar_ids(valor: Any) -> list[int]:
    if not isinstance(valor, list):
        return []

    ids: list[int] = []
    vistos: set[int] = set()
    for item in valor:
        try:
            item_int = int(item)
        except (TypeError, ValueError):
            continue
        if item_int in vistos:
            continue
        vistos.add(item_int)
        ids.append(item_int)
    return ids


def construir_estado(
    herramienta: str,
    orden: int,
    status: StatusHerramienta,
    *,
    ids: list[int] | None = None,
    payload: dict[str, Any] | None = None,
    nota: str = "",
) -> ResultadoHerramienta:
    return {
        "herramienta": herramienta,
        "orden": int(orden or 0),
        "status": status,
        "ids": normalizar_ids(ids or []),
        "payload": dict(payload or {}),
        "nota": str(nota or ""),
    }
