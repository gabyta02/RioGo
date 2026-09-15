from __future__ import annotations

from typing import Any

from .base import ResultadoHerramienta, TipoIds, construir_estado


async def ejecutar(
    *,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    motivo = str((parametros or {}).get("motivo") or "no_clasificado").strip()
    payload = {
        "motivo": motivo,
        "parametros": dict(parametros or {}),
    }

    return (
        construir_estado(
            "fallback",
            orden,
            "sin_resultados",
            payload=payload,
            nota=motivo,
        ),
        tipo_ids,
    )
