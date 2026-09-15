from __future__ import annotations

from typing import Any
from urllib.parse import quote

from application.shared.empaquetar_mensaje import construir_globo

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
                "como_llegar",
                orden,
                "error",
                payload={"fallo": "Falta id_sitio para como_llegar."},
                nota="Falta id_sitio para como_llegar.",
            ),
            tipo_ids,
        )

    try:
        respuesta = await cliente.post("/como-llegar", {"id_sitio": id_sitio})
    except Exception as exc:
        return (
            construir_estado(
                "como_llegar",
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
                "como_llegar",
                orden,
                "sin_resultados",
                payload=respuesta,
                nota=str(respuesta["fallo"]),
            ),
            tipo_ids,
        )

    ubicacion = respuesta.get("ubicacion") if isinstance(respuesta, dict) else None
    if not isinstance(ubicacion, dict):
        return (
            construir_estado(
                "como_llegar",
                orden,
                "sin_resultados",
                payload=respuesta,
                nota="La respuesta no incluyó ubicación.",
            ),
            tipo_ids,
        )

    lat = ubicacion.get("lat")
    lon = ubicacion.get("lon")
    try:
        lat_float = float(lat)
        lon_float = float(lon)
    except (TypeError, ValueError):
        return (
            construir_estado(
                "como_llegar",
                orden,
                "sin_resultados",
                payload=respuesta,
                nota="La ubicación del sitio no tiene coordenadas válidas.",
            ),
            tipo_ids,
        )

    nombre = str(respuesta.get("nombre") or state.get("nombre_sitio") or "el sitio")
    maps_url = _construir_google_maps_url(lat_float, lon_float, nombre)
    texto = (
        "Para llegar puedes presionar el botón de Google Maps. "
        "También puedes visitar el mapa del aplicativo para revisar rutas de buses "
        "urbanos que pasen por ese sector."
    )
    mensajes_app = [
        construir_globo(texto, origen="como_llegar"),
        {
            "tipo": "accion",
            "mensaje": {
                "accion": "abrir_google_maps",
                "label": "Abrir Google Maps",
                "url": maps_url,
                "lat": lat_float,
                "lon": lon_float,
                "nombre_sitio": nombre,
            },
        },
    ]
    return (
        construir_estado(
            "como_llegar",
            orden,
            "ok",
            ids=[id_sitio],
            payload={**respuesta, "mensajes_app": mensajes_app, "maps_url": maps_url},
            nota="Ubicación del sitio obtenida.",
        ),
        "sitio",
    )


def _construir_google_maps_url(lat: Any, lon: Any, nombre: str) -> str:
    try:
        lat_float = float(lat)
        lon_float = float(lon)
        return f"https://www.google.com/maps/search/?api=1&query={lat_float},{lon_float}"
    except (TypeError, ValueError):
        return "https://www.google.com/maps/search/?api=1&query=" + quote(nombre)


def _resolver_id_sitio(state: dict[str, Any]) -> int | None:
    try:
        id_sitio = int(state.get("id_sitio"))
    except (TypeError, ValueError):
        return None
    return id_sitio if id_sitio > 0 else None
