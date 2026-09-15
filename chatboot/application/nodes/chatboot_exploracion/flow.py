from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:  # pragma: no cover - fallback para entornos mínimos
    END = START = None
    StateGraph = None

from application.nodes.chatboot_exploracion.state import ExploracionState
from application.nodes.chatboot_exploracion.utilidades.cargar_memoria import (
    cargar_memoria_exploracion,
)
from application.nodes.chatboot_exploracion.utilidades.crear_plan_tools import (
    crear_plan_exploracion,
)
from application.nodes.chatboot_exploracion.utilidades.ejecutar_plan_tools import (
    ejecutar_plan_exploracion,
)
from application.nodes.chatboot_exploracion.utilidades.guardar_memoria import (
    guardar_memoria_exploracion,
)


@lru_cache(maxsize=1)
def construir_exploracion_flow():
    if StateGraph is None:
        return _ExploracionFlowSecuencial()

    graph = StateGraph(ExploracionState)
    graph.add_node("cargar_memoria", cargar_memoria_exploracion)
    graph.add_node("crear_plan", crear_plan_exploracion)
    graph.add_node("ejecutar_plan", ejecutar_plan_exploracion)
    graph.add_node("guardar_memoria", guardar_memoria_exploracion)
    graph.add_edge(START, "cargar_memoria")
    graph.add_edge("cargar_memoria", "crear_plan")
    graph.add_edge("crear_plan", "ejecutar_plan")
    graph.add_edge("ejecutar_plan", "guardar_memoria")
    graph.add_edge("guardar_memoria", END)
    return graph.compile()


class _ExploracionFlowSecuencial:
    async def ainvoke(self, state_inicial: dict[str, Any]) -> dict[str, Any]:
        state = cargar_memoria_exploracion(state_inicial)
        state = await crear_plan_exploracion(state)
        state = await ejecutar_plan_exploracion(state)
        return guardar_memoria_exploracion(state)


async def ejecutar_exploracion_flow_async(
    state_inicial: dict[str, Any],
) -> dict[str, Any]:
    return await construir_exploracion_flow().ainvoke(state_inicial)


def ejecutar_exploracion_flow(state_inicial: dict[str, Any]) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ejecutar_exploracion_flow_async(state_inicial))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            lambda: asyncio.run(ejecutar_exploracion_flow_async(state_inicial))
        )
        return future.result()
