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
    id_sitio = _resolver_id_sitio(state)
    if id_sitio is None:
        return (
            construir_estado(
                "ficha_sitio",
                orden,
                "error",
                payload={"fallo": "Falta id_sitio para ficha_sitio."},
                nota="Falta id_sitio para ficha_sitio.",
            ),
            tipo_ids,
        )

    try:
        respuesta = await cliente.post("/ficha-sitio", {"id_sitio": id_sitio})
    except Exception as exc:
        return (
            construir_estado(
                "ficha_sitio",
                orden,
                "error",
                payload={"fallo": str(exc), "id_sitio": id_sitio},
                nota=str(exc),
            ),
            tipo_ids,
        )

    if respuesta.get("fallo"):
        return (
            construir_estado(
                "ficha_sitio",
                orden,
                "sin_resultados",
                payload=respuesta,
                nota=str(respuesta["fallo"]),
            ),
            tipo_ids,
        )

    return (
        construir_estado(
            "ficha_sitio",
            orden,
            "ok",
            ids=[id_sitio],
            payload=respuesta,
            nota="Ficha del sitio obtenida.",
        ),
        "sitio",
    )


def _resolver_id_sitio(state: dict[str, Any]) -> int | None:
    try:
        id_sitio = int(state.get("id_sitio"))
    except (TypeError, ValueError):
        return None
    return id_sitio if id_sitio > 0 else None
