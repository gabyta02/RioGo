from __future__ import annotations

from copy import deepcopy
from typing import Any

from .base import (
    ResultadoHerramienta,
    TipoIds,
    construir_estado,
    construir_estado_busqueda_local,
    interpretar_payload_http,
    normalizar_ids,
    normalizar_ubicacion,
)

MENSAJE_UBICACION_REQUERIDA = (
    "Para buscar opciones cercanas a ti, activa los permisos de ubicación "
    "en la configuración de la app e inténtalo de nuevo."
)


async def ejecutar(
    *,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    if (parametros or {}).get("usar_ubicacion_usuario") is True:
        ubicacion = normalizar_ubicacion(state.get("ubicacion_usuario"))
        if not ubicacion:
            estado_busqueda = construir_estado_busqueda_local(
                herramienta="busqueda_ubicacion",
                status="sin_resultados",
                parametros=parametros,
                ids_entrada=ids_consulta,
                nota=MENSAJE_UBICACION_REQUERIDA,
                retroalimentacion={"motivo": "ubicacion_usuario_requerida"},
            )
            return (
                construir_estado(
                    "busqueda_ubicacion",
                    orden,
                    "sin_resultados",
                    payload={
                        "sin_sitios": MENSAJE_UBICACION_REQUERIDA,
                        "motivo": "ubicacion_usuario_requerida",
                    },
                    nota=MENSAJE_UBICACION_REQUERIDA,
                    estado_busqueda=estado_busqueda,
                ),
                tipo_ids,
            )

    ids_normalizados = normalizar_ids(ids_consulta)
    if not ids_normalizados:
        estado_busqueda = construir_estado_busqueda_local(
            herramienta="busqueda_ubicacion",
            status="sin_resultados",
            parametros=parametros,
            ids_entrada=ids_consulta,
            nota="busqueda_ubicacion requiere candidatos previos del pipeline.",
        )
        return (
            construir_estado(
                "busqueda_ubicacion",
                orden,
                "sin_resultados",
                payload={"sin_sitios": "busqueda_ubicacion requiere candidatos previos."},
                nota="busqueda_ubicacion requiere candidatos previos del pipeline.",
                estado_busqueda=estado_busqueda,
            ),
            tipo_ids,
        )

    payload = deepcopy(parametros or {})
    if tipo_ids == "ruta":
        payload["entidad"] = "ruta"
    else:
        payload.setdefault("entidad", "sitio")

    if payload.get("usar_ubicacion_usuario") is True:
        ubicacion = normalizar_ubicacion(state.get("ubicacion_usuario"))
        payload["ubicacion_usuario"] = ubicacion

    payload["ids_consulta"] = ids_normalizados

    try:
        respuesta = await cliente.post_herramienta("/busqueda-ubicacion", payload)
    except Exception as exc:
        estado_busqueda = construir_estado_busqueda_local(
            herramienta="busqueda_ubicacion",
            status="error",
            parametros=payload,
            ids_entrada=ids_normalizados,
            nota=str(exc),
        )
        return (
            construir_estado(
                "busqueda_ubicacion",
                orden,
                "error",
                payload={"fallo": str(exc)},
                nota=str(exc),
                estado_busqueda=estado_busqueda,
            ),
            None,
        )

    return interpretar_payload_http(
        "busqueda_ubicacion",
        orden,
        respuesta,
        parametros=payload,
        ids_consulta=ids_normalizados,
    )
