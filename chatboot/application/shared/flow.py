from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from application.shared.empaquetar_mensaje import construir_mensaje_app_desde_estado
from application.shared.inyectar_fecha import ejecutar_inyectar_fecha
from application.shared.inyectar_palabra import ejecutar_inyectar_palabra
from application.shared.limpieza_texto import ejecutar_limpieza_texto
from application.shared.promp_inyection import (
    RIESGO_PROMPT_INYECTION_VACIO,
    ejecutar_prompt_inyection,
)
from application.state import ClasificacionFinal, SharedFlowState


def _resolver_siguiente_paso(state: SharedFlowState) -> str:
    return "finalizacion" if state.get("bloqueado") else "continuar"


def _construir_clasificacion_final(state: SharedFlowState) -> SharedFlowState:
    mensaje = {
        "mensaje_usuario": state.get("mensaje_original", ""),
        "texto_limpio": state.get("mensaje_limpio", ""),
        "riesgo_prompt_inyection": state.get("riesgo_prompt_inyection")
        or RIESGO_PROMPT_INYECTION_VACIO,
        "palabras_inyectadas": list(state.get("palabras_inyectadas", [])),
        "contexto_temporal": state.get("contexto_temporal") or {},
    }

    clasificacion: ClasificacionFinal = {
        "pregunta_chatboot": state["pregunta_chatboot"],
        "mensaje": mensaje,
        "client_message_id": state["client_message_id"],
        "sesion_id": state["sesion_id"],
        "ubicacion_usuario": state["ubicacion_usuario"],
    }

    if state.get("id_usuario") is not None:
        clasificacion["id_usuario"] = state["id_usuario"]
    if state.get("id_sitio") is not None:
        clasificacion["id_sitio"] = state["id_sitio"]
    if state.get("nombre_sitio"):
        clasificacion["nombre_sitio"] = state["nombre_sitio"]
    if state.get("mensaje_sistema"):
        clasificacion["mensaje_sistema"] = state["mensaje_sistema"]
    mensaje_app = construir_mensaje_app_desde_estado(state)
    if mensaje_app:
        clasificacion["mensaje_app"] = mensaje_app

    return {
        **state,
        "clasificacion_final": clasificacion,
    }


@lru_cache(maxsize=1)
def construir_shared_flow():
    graph = StateGraph(SharedFlowState)

    graph.add_node("limpieza_texto", ejecutar_limpieza_texto)
    graph.add_node("promp_inyection", ejecutar_prompt_inyection)
    graph.add_node("inyectar_palabra", ejecutar_inyectar_palabra)
    graph.add_node("inyectar_fecha", ejecutar_inyectar_fecha)
    graph.add_node("finalizacion", _construir_clasificacion_final)

    graph.add_edge(START, "limpieza_texto")
    graph.add_conditional_edges(
        "limpieza_texto",
        _resolver_siguiente_paso,
        {
            "continuar": "promp_inyection",
            "finalizacion": "finalizacion",
        },
    )
    graph.add_conditional_edges(
        "promp_inyection",
        _resolver_siguiente_paso,
        {
            "continuar": "inyectar_palabra",
            "finalizacion": "finalizacion",
        },
    )
    graph.add_edge("inyectar_palabra", "inyectar_fecha")
    graph.add_edge("inyectar_fecha", "finalizacion")
    graph.add_edge("finalizacion", END)

    return graph.compile()


def ejecutar_shared_flow(state_inicial: SharedFlowState) -> SharedFlowState:
    app = construir_shared_flow()
    return app.invoke(state_inicial)
