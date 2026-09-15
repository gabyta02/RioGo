from __future__ import annotations

from typing import Any

from application.shared.empaquetar_mensaje import construir_multimedia

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
                "multimedia",
                orden,
                "error",
                payload={"fallo": "Falta id_sitio para multimedia."},
                nota="Falta id_sitio para multimedia.",
            ),
            tipo_ids,
        )

    try:
        respuesta = await cliente.post("/multimedia", {"id_sitio": id_sitio})
    except Exception as exc:
        return (
            construir_estado(
                "multimedia",
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
                "multimedia",
                orden,
                "sin_resultados",
                payload=respuesta,
                nota=str(respuesta["fallo"]),
            ),
            tipo_ids,
        )

    imagenes = respuesta.get("imagenes")
    if not isinstance(imagenes, list) or not imagenes:
        return (
            construir_estado(
                "multimedia",
                orden,
                "sin_resultados",
                payload=respuesta,
                nota="El sitio no tiene imágenes activas.",
            ),
            tipo_ids,
        )

    mensaje_app = construir_multimedia(imagenes, origen="multimedia")
    return (
        construir_estado(
            "multimedia",
            orden,
            "ok",
            ids=[id_sitio],
            payload={**respuesta, "mensaje_app": mensaje_app},
            nota=f"Imágenes obtenidas: {len(imagenes)}.",
        ),
        "sitio",
    )


def _resolver_id_sitio(state: dict[str, Any]) -> int | None:
    try:
        id_sitio = int(state.get("id_sitio"))
    except (TypeError, ValueError):
        return None
    return id_sitio if id_sitio > 0 else None
