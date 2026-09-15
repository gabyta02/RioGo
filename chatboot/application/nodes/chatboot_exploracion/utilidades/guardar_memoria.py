from __future__ import annotations

from typing import Any


def guardar_memoria_exploracion(state: dict[str, object]) -> dict[str, object]:
    from infrastructure.config import get_settings
    from infrastructure.memory import MemoriaPlanificador, guardar_memoria

    sesion_id = str(state.get("sesion_id") or "").strip()
    texto_usuario = str(state.get("texto_usuario") or "").strip()
    client_message_id = str(state.get("client_message_id") or "").strip()
    respuesta = _extraer_respuesta_exploracion(state)

    if not sesion_id or not texto_usuario or not client_message_id:
        return state

    max_preguntas = get_settings().memory.max_preguntas
    memoria = _reconstruir_memoria_previa(
        sesion_id=sesion_id,
        memoria_raw=state.get("memoria"),
        max_preguntas=max_preguntas,
    )

    memoria.agregar_pregunta(
        texto=texto_usuario,
        client_message_id=client_message_id,
        max_preguntas=max_preguntas,
        tipo="exploracion_plan",
        resultado=respuesta or None,
    )

    memoria.entidades = _fusionar_entidades_resueltas(
        memoria.entidades,
        state.get("entidades_resueltas"),
    )

    memoria_guardada = guardar_memoria(sesion_id, memoria.model_dump(mode="json"))

    return {
        **state,
        "memoria": {
            "turnos": [
                {
                    "turno": indice,
                    "pregunta": item.get("texto"),
                    "respuesta": item.get("resultado"),
                    "client_message_id": item.get("client_message_id"),
                }
                for indice, item in enumerate(
                    memoria_guardada.get("preguntas") or [],
                    start=1,
                )
                if isinstance(item, dict)
            ],
            "entidades": memoria_guardada.get("entidades") or [],
        },
}


def _reconstruir_memoria_previa(
    *,
    sesion_id: str,
    memoria_raw: object,
    max_preguntas: int,
) -> Any:
    from infrastructure.memory import MemoriaPlanificador

    memoria = MemoriaPlanificador.vacia(sesion_id)
    if not isinstance(memoria_raw, dict):
        return memoria

    memoria.entidades = _deduplicar_texto(
        [
            str(entidad).strip()
            for entidad in memoria_raw.get("entidades") or []
            if str(entidad or "").strip()
        ]
    )

    memoria_existente = memoria_raw.get("turnos") or []
    for turno in reversed(memoria_existente):
        if not isinstance(turno, dict):
            continue
        pregunta = str(turno.get("pregunta") or "").strip()
        if not pregunta:
            continue
        respuesta_turno = turno.get("respuesta")
        memoria.agregar_pregunta(
            texto=pregunta,
            client_message_id=str(turno.get("client_message_id") or "memoria_historica"),
            max_preguntas=max_preguntas,
            resultado=(
                str(respuesta_turno).strip()
                if respuesta_turno is not None and str(respuesta_turno).strip()
                else None
            ),
        )

    return memoria


def _fusionar_entidades_resueltas(
    entidades_actuales: list[str],
    entidades_resueltas: object,
) -> list[str]:
    if not isinstance(entidades_resueltas, list):
        return entidades_actuales

    return _deduplicar_texto(
        [
            *entidades_actuales,
            *[
                str(entidad).strip()
                for entidad in entidades_resueltas
                if str(entidad or "").strip()
            ],
        ]
    )


def _extraer_respuesta_exploracion(state: dict[str, Any]) -> str:
    partes: list[str] = []

    mensaje_app = state.get("mensaje_app")
    if isinstance(mensaje_app, dict):
        mensaje = mensaje_app.get("mensaje")
        if isinstance(mensaje, dict):
            texto = str(mensaje.get("texto") or "").strip()
            if texto:
                partes.append(texto)

    mensajes_app = state.get("mensajes_app")
    if isinstance(mensajes_app, list):
        for item in mensajes_app:
            if not isinstance(item, dict):
                continue
            texto_item = _texto_memoria_desde_mensaje_app(item)
            if texto_item and texto_item not in partes:
                partes.append(texto_item)

    if not partes:
        texto_sistema = str(state.get("mensaje_sistema") or "").strip()
        if texto_sistema:
            partes.append(texto_sistema)

    entidades = state.get("entidades_resueltas")
    if isinstance(entidades, list):
        nombres = [
            str(entidad).strip()
            for entidad in entidades
            if str(entidad or "").strip()
        ]
        if nombres:
            partes.append(f"[Sitios sugeridos: {', '.join(_deduplicar_texto(nombres))}]")

    return "\n".join(partes).strip()


def _texto_memoria_desde_mensaje_app(item: dict[str, Any]) -> str:
    tipo = str(item.get("tipo") or "")
    mensaje = item.get("mensaje")
    if not isinstance(mensaje, dict):
        return ""

    if tipo == "globo":
        return str(mensaje.get("texto") or "").strip()

    if tipo == "opciones":
        opciones = mensaje.get("opciones")
        if isinstance(opciones, list):
            etiquetas = [
                str(opcion).strip()
                for opcion in opciones
                if str(opcion or "").strip()
            ]
            if etiquetas:
                return f"[Opciones: {', '.join(etiquetas)}]"

    return ""


def _deduplicar_texto(valores: list[str]) -> list[str]:
    salida: list[str] = []
    vistos: set[str] = set()
    for valor in valores:
        limpio = str(valor or "").strip()
        if not limpio:
            continue
        clave = limpio.casefold()
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(limpio)
    return salida
