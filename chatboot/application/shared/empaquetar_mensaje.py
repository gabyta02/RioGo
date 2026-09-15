from __future__ import annotations

from typing import Any

from application.state import MensajeApp, SharedFlowState


def construir_globo(texto: str, *, origen: str | None = None) -> MensajeApp:
    mensaje = {"texto": str(texto or "")}
    if origen:
        mensaje["origen"] = origen
    return {
        "tipo": "globo",
        "mensaje": mensaje,
    }


def construir_card(mensaje: dict[str, Any]) -> MensajeApp:
    return {
        "tipo": "card",
        "mensaje": dict(mensaje),
    }


def construir_stream(mensaje: dict[str, Any]) -> MensajeApp:
    return {
        "tipo": "stream",
        "mensaje": dict(mensaje),
    }


def construir_multimedia(
    imagenes: list[dict[str, Any]],
    *,
    origen: str | None = None,
) -> MensajeApp:
    mensaje: dict[str, Any] = {"imagenes": list(imagenes or [])}
    if origen:
        mensaje["origen"] = origen
    return {
        "tipo": "multimedia",
        "mensaje": mensaje,
    }


def construir_mensaje_app_desde_estado(
    state: SharedFlowState,
) -> MensajeApp | None:
    texto = state.get("mensaje_sistema")
    if not texto:
        return None

    origen = state.get("origen_mensaje_sistema")
    if origen in {"limpieza_texto", "promp_inyection"}:
        return construir_globo(texto, origen=origen)

    return construir_globo(texto, origen=origen)
