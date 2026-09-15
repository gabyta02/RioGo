from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

PROMPT_FILE = (
    Path(__file__).resolve().parents[1] / "promp" / "redactar_respuesta_pregunta.md"
)

StreamCallback = Callable[[str], Awaitable[None]]


@lru_cache(maxsize=1)
def cargar_prompt_redactor_pregunta() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


async def redactar_respuesta_pregunta(
    *,
    state: dict[str, Any],
    contextos_herramientas: list[dict[str, Any]],
    stream_callback: StreamCallback | None = None,
) -> str:
    payload = {
        "texto_usuario": state.get("texto_usuario", ""),
        "nombre_sitio": state.get("nombre_sitio", ""),
        "memoria": state.get("memoria") or {"turnos": []},
        "contextos_herramientas": contextos_herramientas,
    }
    user_content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    from infrastructure.llms import get_llm_router

    router = get_llm_router()
    route_settings = router.get_route_settings("sitio")
    client = router.get_client_for_route("sitio")

    acumulado: list[str] = []

    async def on_content_delta(delta: str) -> None:
        acumulado.append(str(delta))
        if stream_callback:
            await stream_callback("".join(acumulado))

    respuesta = await client.generate_response_stream(
        "",
        thinking_enabled=route_settings.thinking_enabled,
        system_prompt=cargar_prompt_redactor_pregunta(),
        user_content=user_content,
        json_response=False,
        on_content_delta=on_content_delta,
    )
    return str(respuesta or "").strip()
