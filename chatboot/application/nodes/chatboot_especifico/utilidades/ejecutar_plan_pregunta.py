from __future__ import annotations

import asyncio
from typing import Any

from application.nodes.chatboot_especifico.herramientas.base import (
    ResultadoHerramienta,
    TipoIds,
    normalizar_ids,
)
from application.nodes.chatboot_especifico.herramientas.cliente_http import (
    ClientePreguntaDirectaHTTP,
)
from application.nodes.chatboot_especifico.herramientas.registry import (
    ejecutar_herramienta,
)
from application.shared.empaquetar_mensaje import construir_globo
from application.nodes.chatboot_especifico.utilidades.redactar_respuesta_pregunta import (
    redactar_respuesta_pregunta,
)

HERRAMIENTAS_REDACTABLES = {"ficha_sitio", "chuck_documento", "documento_sitio"}


async def ejecutar_plan_pregunta(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("plan_valido"):
        mensajes_app = _mensajes_existentes(state)
        return _construir_state_final(
            state,
            estados=[],
            ids_asociados=[],
            mensajes_app=mensajes_app,
            entidades_resueltas=[],
            mensaje_app=mensajes_app[0] if mensajes_app else state.get("mensaje_app"),
        )

    plan = state.get("plan")
    consultas = plan.get("consultas") if isinstance(plan, dict) else None
    if not isinstance(consultas, list):
        mensaje = (
            "No pude organizar las herramientas para esta pregunta. "
            "¿Puedes intentarlo de nuevo?"
        )
        mensaje_app = construir_globo(mensaje, origen="ejecutar_plan_pregunta")
        return _construir_state_final(
            state,
            estados=[],
            ids_asociados=[],
            mensajes_app=[mensaje_app],
            entidades_resueltas=[],
            mensaje_sistema=mensaje,
            mensaje_app=mensaje_app,
        )

    cliente = ClientePreguntaDirectaHTTP()
    resultados_consultas = await asyncio.gather(
        *[_ejecutar_consulta(consulta, state, cliente) for consulta in consultas],
        return_exceptions=True,
    )

    estados: list[ResultadoHerramienta] = []
    ids_finales: list[int] = []
    mensajes_app: list[dict[str, Any]] = []
    contextos_redactor: list[dict[str, Any]] = []

    for resultado in resultados_consultas:
        if isinstance(resultado, Exception):
            estados.append(
                {
                    "herramienta": "consulta",
                    "orden": 0,
                    "status": "error",
                    "ids": [],
                    "payload": {"fallo": str(resultado)},
                    "nota": str(resultado),
                }
            )
            continue
        estados.extend(resultado["estados"])
        ids_finales.extend(resultado["ids"])
        mensajes_app.extend(resultado["mensajes_app"])
        contextos_redactor.extend(resultado["contextos_redactor"])

    ids_asociados = _deduplicar(ids_finales)
    mensaje_redactado = await _redactar_si_corresponde(state, contextos_redactor)
    if mensaje_redactado is not None:
        mensajes_app.insert(0, mensaje_redactado)
    elif not mensajes_app:
        mensajes_app.append(_construir_globo_sin_resultados(estados))

    mensaje_app_principal = mensajes_app[0] if mensajes_app else None
    mensaje_sistema = None
    if isinstance(mensaje_app_principal, dict):
        mensaje_sistema = str(
            (mensaje_app_principal.get("mensaje") or {}).get("texto") or ""
        ).strip() or None

    return _construir_state_final(
        state,
        estados=estados,
        ids_asociados=ids_asociados,
        mensajes_app=mensajes_app,
        entidades_resueltas=[],
        mensaje_sistema=mensaje_sistema,
        mensaje_app=mensaje_app_principal,
    )


async def _ejecutar_consulta(
    consulta: Any,
    state: dict[str, Any],
    cliente: ClientePreguntaDirectaHTTP,
) -> dict[str, Any]:
    ejecuciones = []
    if isinstance(consulta, dict) and isinstance(
        consulta.get("ejecucion_herramienta"), list
    ):
        ejecuciones = consulta["ejecucion_herramienta"]

    ordenadas = sorted(
        [item for item in ejecuciones if isinstance(item, dict)],
        key=lambda item: int(item.get("orden") or 0),
    )

    estados: list[ResultadoHerramienta] = []
    ids_actuales: list[int] = []
    tipo_ids: TipoIds | None = None
    mensajes_app: list[dict[str, Any]] = []
    contextos_redactor: list[dict[str, Any]] = []

    for indice, item in enumerate(ordenadas):
        herramienta = (
            item.get("herramienta")
            if isinstance(item.get("herramienta"), dict)
            else {}
        )
        nombre = str(herramienta.get("nombre") or "").strip()
        parametros = (
            herramienta.get("parametros")
            if isinstance(herramienta.get("parametros"), dict)
            else {}
        )
        orden = int(item.get("orden") or indice + 1)

        estado_herramienta, nuevo_tipo = await ejecutar_herramienta(
            nombre=nombre,
            orden=orden,
            parametros=parametros,
            ids_consulta=ids_actuales,
            tipo_ids=tipo_ids,
            state=state,
            cliente=cliente,
        )
        estados.append(estado_herramienta)
        mensajes_app.extend(_extraer_mensajes_app(estado_herramienta))
        if _es_contexto_redactable(estado_herramienta):
            contextos_redactor.append(
                {
                    "herramienta": estado_herramienta["herramienta"],
                    "status": estado_herramienta["status"],
                    "payload": estado_herramienta["payload"],
                    "nota": estado_herramienta["nota"],
                }
            )

        if estado_herramienta["status"] == "ok" and estado_herramienta["ids"]:
            ids_actuales = normalizar_ids(estado_herramienta["ids"])
            tipo_ids = nuevo_tipo or tipo_ids or "sitio"
            continue

        if estado_herramienta["status"] == "error":
            continue

    return {
        "estados": estados,
        "ids": ids_actuales,
        "tipo_ids": tipo_ids or "sitio",
        "mensajes_app": mensajes_app,
        "contextos_redactor": contextos_redactor,
    }


async def _redactar_si_corresponde(
    state: dict[str, Any],
    contextos_redactor: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not contextos_redactor:
        return None

    try:
        texto = await redactar_respuesta_pregunta(
            state=state,
            contextos_herramientas=contextos_redactor,
            stream_callback=state.get("stream_callback"),
        )
    except Exception as exc:
        texto = (
            "Encontré información del sitio, pero no pude redactarla con detalle "
            f"en este momento. Intenta nuevamente. ({exc})"
        )

    if not texto:
        return None
    return construir_globo(texto, origen="redactor_pregunta_directa")


def _extraer_mensajes_app(estado: ResultadoHerramienta) -> list[dict[str, Any]]:
    payload = estado.get("payload") or {}
    mensajes = payload.get("mensajes_app")
    if isinstance(mensajes, list):
        return [item for item in mensajes if isinstance(item, dict)]
    mensaje = payload.get("mensaje_app")
    if isinstance(mensaje, dict):
        return [mensaje]
    return []


def _es_contexto_redactable(estado: ResultadoHerramienta) -> bool:
    if estado.get("herramienta") not in HERRAMIENTAS_REDACTABLES:
        return False
    if estado.get("status") != "ok":
        return False
    return bool(estado.get("payload"))


def _construir_globo_sin_resultados(
    estados: list[ResultadoHerramienta],
) -> dict[str, Any]:
    nota = next(
        (
            str(estado.get("nota") or "").strip()
            for estado in estados
            if str(estado.get("nota") or "").strip()
        ),
        "",
    )
    texto = (
        nota
        if nota
        else "No encontré información suficiente de este lugar para responder esa pregunta."
    )
    return construir_globo(texto, origen="pregunta_directa_sin_resultados")


def _construir_state_final(
    state: dict[str, Any],
    *,
    estados: list[ResultadoHerramienta],
    ids_asociados: list[int],
    mensajes_app: list[dict[str, Any]],
    entidades_resueltas: list[str],
    mensaje_sistema: str | None = None,
    mensaje_app: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resultado = {
        "plan_valido": bool(state.get("plan_valido")),
        "plan": state.get("plan"),
        "errores_formato": list(state.get("errores_formato") or []),
        "estados_herramientas": estados,
        "ids_asociados": ids_asociados,
        "mensajes_app": mensajes_app,
        "entidades_resueltas": entidades_resueltas,
    }
    return {
        **state,
        "estados_herramientas": estados,
        "ids_asociados": ids_asociados,
        "mensajes_app": mensajes_app,
        "entidades_resueltas": entidades_resueltas,
        "mensaje_sistema": mensaje_sistema
        if mensaje_sistema is not None
        else state.get("mensaje_sistema"),
        "mensaje_app": mensaje_app
        if mensaje_app is not None
        else state.get("mensaje_app"),
        "resultado_pregunta_directa": resultado,
    }


def _mensajes_existentes(state: dict[str, Any]) -> list[dict[str, Any]]:
    mensaje_app = state.get("mensaje_app")
    if isinstance(mensaje_app, dict):
        return [mensaje_app]
    return []


def _deduplicar(ids: list[int]) -> list[int]:
    resultado: list[int] = []
    vistos: set[int] = set()
    for item in normalizar_ids(ids):
        if item in vistos:
            continue
        vistos.add(item)
        resultado.append(item)
    return resultado
