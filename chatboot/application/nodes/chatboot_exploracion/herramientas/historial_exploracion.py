from __future__ import annotations

from typing import Any

from .cliente_http import ClienteHerramientasHTTP


async def guardar_historial_exploracion(
    payload: dict[str, Any],
    *,
    cliente: Any | None = None,
) -> dict[str, Any]:
    cliente_http = cliente or ClienteHerramientasHTTP()
    return await cliente_http.post_herramienta("/historial-exploracion", payload)

