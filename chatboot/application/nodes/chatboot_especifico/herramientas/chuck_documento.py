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
                "chuck_documento",
                orden,
                "error",
                payload={"fallo": "Falta id_sitio para chuck_documento."},
                nota="Falta id_sitio para chuck_documento.",
            ),
            tipo_ids,
        )

    texto_embeddings = parametros.get("texto_embeddings") or parametros.get(
        "mensaje_chunk"
    )
    mensaje_chunk = _normalizar_mensaje_chunk(texto_embeddings, state)
    payload = {
        "id_sitio": id_sitio,
        "mensaje_chunk": mensaje_chunk,
        "keywords": _normalizar_keywords(parametros.get("keywords")),
    }

    try:
        respuesta = await cliente.post("/chunks-documento", payload)
    except Exception as exc:
        return (
            construir_estado(
                "chuck_documento",
                orden,
                "error",
                payload={"fallo": str(exc), **payload},
                nota=str(exc),
            ),
            tipo_ids,
        )

    if respuesta.get("fallo"):
        return (
            construir_estado(
                "chuck_documento",
                orden,
                "sin_resultados",
                payload=respuesta,
                nota=str(respuesta["fallo"]),
            ),
            tipo_ids,
        )

    chunks = respuesta.get("chunks")
    if isinstance(chunks, list) and chunks:
        return (
            construir_estado(
                "chuck_documento",
                orden,
                "ok",
                ids=[id_sitio],
                payload=respuesta,
                nota=f"Chunks obtenidos: {len(chunks)}.",
            ),
            "sitio",
        )

    return (
        construir_estado(
            "chuck_documento",
            orden,
            "sin_resultados",
            payload=respuesta,
            nota="No se encontraron chunks útiles para el sitio.",
        ),
        tipo_ids,
    )


def _resolver_id_sitio(state: dict[str, Any]) -> int | None:
    try:
        id_sitio = int(state.get("id_sitio"))
    except (TypeError, ValueError):
        return None
    return id_sitio if id_sitio > 0 else None


def _normalizar_mensaje_chunk(valor: Any, state: dict[str, Any]) -> str | list[str]:
    if isinstance(valor, list):
        textos = [str(item).strip() for item in valor if str(item or "").strip()]
        if textos:
            return textos
    texto = str(valor or "").strip()
    if texto:
        return texto
    return str(state.get("texto_usuario") or state.get("nombre_sitio") or "").strip()


def _normalizar_keywords(valor: Any) -> list[str]:
    if not isinstance(valor, list):
        return []
    return [str(item).strip() for item in valor if str(item or "").strip()]
