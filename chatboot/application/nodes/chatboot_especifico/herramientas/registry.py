from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from . import (
    chuck_documento,
    como_llegar,
    conversacional,
    documento_sitio,
    fallback,
    ficha_sitio,
    multimedia,
)
from .base import ResultadoHerramienta, TipoIds, construir_estado

EjecutorHerramienta = Callable[..., Awaitable[tuple[ResultadoHerramienta, TipoIds | None]]]

REGISTRY: dict[str, EjecutorHerramienta] = {
    "conversacional": conversacional.ejecutar,
    "fallback": fallback.ejecutar,
    "documento_sitio": documento_sitio.ejecutar,
    "ficha_sitio": ficha_sitio.ejecutar,
    "chuck_documento": chuck_documento.ejecutar,
    "chunk_documento": chuck_documento.ejecutar,
    "multimedia": multimedia.ejecutar,
    "como_llegar": como_llegar.ejecutar,
}


async def ejecutar_herramienta(
    *,
    nombre: str,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    nombre_normalizado = str(nombre or "").strip()
    ejecutor = REGISTRY.get(nombre_normalizado)
    if ejecutor is None:
        return (
            construir_estado(
                nombre_normalizado or "desconocida",
                orden,
                "error",
                payload={"fallo": f"Herramienta no registrada: {nombre_normalizado}"},
                nota=f"Herramienta no registrada: {nombre_normalizado}",
            ),
            tipo_ids,
        )

    return await ejecutor(
        orden=orden,
        parametros=parametros,
        ids_consulta=ids_consulta,
        tipo_ids=tipo_ids,
        state=state,
        cliente=cliente,
    )
