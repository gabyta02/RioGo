from __future__ import annotations

from typing import Any

from application.nodes.chatboot_exploracion.herramientas.cliente_http import (
    ClienteHerramientasHTTP,
)


async def guardar_historial_pregunta_directa(
    payload: dict[str, Any],
) -> dict[str, Any]:
    cliente_http = ClienteHerramientasHTTP()
    return await cliente_http.post_herramienta("/historial-pregunta-directa", payload)
