from __future__ import annotations

from typing import Any

from .base import ResultadoHerramienta, TipoIds, ejecutar_http_generico


async def ejecutar(
    *,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    return await ejecutar_http_generico(
        herramienta="pregunta_directa",
        endpoint="/pregunta-directa",
        orden=orden,
        parametros=parametros,
        ids_consulta=ids_consulta,
        cliente=cliente,
    )
