from __future__ import annotations

from typing import Any

from application.shared.empaquetar_mensaje import construir_globo

from .base import ResultadoHerramienta, TipoIds, construir_estado

MENSAJE_FALLBACK = (
    "No tengo suficiente información para responder eso sobre **este sitio**. "
    "Puedes preguntarme por **horarios, servicios, historia o cómo llegar**."
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
    texto = str((parametros or {}).get("respuesta_sugerida") or "").strip()
    if not texto:
        texto = MENSAJE_FALLBACK

    mensaje = construir_globo(texto, origen="fallback")
    payload = {
        "mensaje_app": mensaje,
        "texto": texto,
        "respuesta_sugerida": texto,
    }
    return (
        construir_estado(
            "fallback",
            orden,
            "sin_resultados",
            payload=payload,
            nota=texto,
        ),
        tipo_ids,
    )
