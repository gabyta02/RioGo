from __future__ import annotations

import os
from typing import Any

from .base import ResultadoHerramienta, TipoIds, ejecutar_http_generico

_TIMEOUT_SEMANTICA_SECONDS = float(
    os.getenv("APIS_TIMEOUT_SEMANTICA_SECONDS")
    or os.getenv("APIS_TIMEOUT_SECONDS")
    or 90
)


async def ejecutar(
    *,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    resultado, nuevo_tipo = await ejecutar_http_generico(
        herramienta="busqueda_semantica",
        endpoint="/busqueda-semantica-consulta",
        orden=orden,
        parametros=parametros,
        ids_consulta=ids_consulta,
        cliente=cliente,
        timeout_seconds=_TIMEOUT_SEMANTICA_SECONDS,
    )

    retroalimentacion = resultado["payload"].get("retroalimentacion")
    if (
        resultado["status"] == "ok"
        and isinstance(retroalimentacion, dict)
        and retroalimentacion.get("fallback_global_aplicado") is True
    ):
        nota = str(retroalimentacion.get("mensaje") or "").strip()
        resultado["nota"] = (
            nota
            or "No se encontraron coincidencias en el filtro previo; se amplió la búsqueda."
        )

    return resultado, nuevo_tipo
