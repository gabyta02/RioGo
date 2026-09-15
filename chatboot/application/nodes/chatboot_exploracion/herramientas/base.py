from __future__ import annotations

import time
from copy import deepcopy
from typing import Any, Literal, TypedDict

StatusHerramienta = Literal["ok", "sin_resultados", "error"]
TipoIds = Literal["sitio", "ruta"]


class ResultadoHerramienta(TypedDict):
    herramienta: str
    orden: int
    status: StatusHerramienta
    ids: list[int]
    payload: dict[str, Any]
    nota: str
    estado_busqueda: dict[str, Any]


def normalizar_ids(valor: Any) -> list[int]:
    if not isinstance(valor, list):
        return []

    ids: list[int] = []
    vistos: set[int] = set()
    for item in valor:
        try:
            item_int = int(item)
        except (TypeError, ValueError):
            continue
        if item_int in vistos:
            continue
        vistos.add(item_int)
        ids.append(item_int)
    return ids


def normalizar_ubicacion(ubicacion: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(ubicacion, dict):
        return None

    lat = ubicacion.get("lat")
    lon = ubicacion.get("lon", ubicacion.get("lng"))
    if lat is None or lon is None:
        return None
    return {"lat": lat, "lon": lon}


def construir_estado(
    herramienta: str,
    orden: int,
    status: StatusHerramienta,
    *,
    ids: list[int] | None = None,
    payload: dict[str, Any] | None = None,
    nota: str = "",
    estado_busqueda: dict[str, Any] | None = None,
) -> ResultadoHerramienta:
    ids_normalizados = normalizar_ids(ids or [])
    payload_normalizado = dict(payload or {})
    return {
        "herramienta": herramienta,
        "orden": int(orden or 0),
        "status": status,
        "ids": ids_normalizados,
        "payload": payload_normalizado,
        "nota": str(nota or ""),
        "estado_busqueda": estado_busqueda
        or construir_estado_busqueda_local(
            herramienta=herramienta,
            status=status,
            ids_salida=ids_normalizados,
            parametros={},
            ids_entrada=[],
            nota=nota,
        ),
    }


def construir_estado_busqueda_local(
    *,
    herramienta: str,
    status: StatusHerramienta,
    ids_salida: list[int] | None = None,
    parametros: dict[str, Any] | None = None,
    ids_entrada: list[int] | None = None,
    nota: str = "",
    estado: str | None = None,
    retroalimentacion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    estado_resuelto = estado or {
        "ok": "cumplido",
        "sin_resultados": "no_cumplido",
        "error": "error",
    }.get(status, "error")
    ids_entrada_norm = normalizar_ids(ids_entrada or [])
    ids_salida_norm = normalizar_ids(ids_salida or [])
    return {
        "estado": estado_resuelto,
        "ids_entrada": ids_entrada_norm,
        "ids_salida": ids_salida_norm,
        "filtros": [
            {
                "nombre": herramienta,
                "valor": deepcopy(parametros or {}),
                "estado": estado_resuelto,
                "detalle": str(nota or ""),
            }
        ],
        "retroalimentacion": dict(retroalimentacion or {}),
    }


def extraer_ids_y_tipo(payload: dict[str, Any]) -> tuple[list[int], TipoIds | None]:
    ids_sitio = normalizar_ids(payload.get("ids_sitio"))
    if ids_sitio:
        return ids_sitio, "sitio"

    ids_ruta = normalizar_ids(payload.get("ids_ruta"))
    if ids_ruta:
        return ids_ruta, "ruta"

    return [], None


def extraer_nota(payload: dict[str, Any]) -> str:
    retroalimentacion = payload.get("retroalimentacion")
    if isinstance(retroalimentacion, dict) and retroalimentacion.get("mensaje"):
        return str(retroalimentacion["mensaje"]).strip()

    for clave in ("sin_sitios", "sin_rutas", "fallo", "mensaje"):
        valor = payload.get(clave)
        if valor:
            return str(valor).strip()

    return ""


def _describir_excepcion(exc: Exception) -> str:
    texto = str(exc).strip()
    if texto:
        return texto

    nombre = type(exc).__name__
    if nombre.endswith("Timeout") or nombre == "TimeoutError" or isinstance(exc, TimeoutError):
        return "La llamada a la API excedió el tiempo de espera."
    return f"Error al llamar a la API ({nombre})."


def _detalle_estado_busqueda(estado_busqueda: dict[str, Any] | None) -> str:
    if not isinstance(estado_busqueda, dict):
        return ""

    filtros = estado_busqueda.get("filtros")
    if isinstance(filtros, list):
        for filtro in filtros:
            if not isinstance(filtro, dict):
                continue
            detalle = str(filtro.get("detalle") or "").strip()
            if detalle:
                return detalle

    retroalimentacion = estado_busqueda.get("retroalimentacion")
    if isinstance(retroalimentacion, dict):
        mensaje = str(retroalimentacion.get("mensaje") or "").strip()
        if mensaje:
            return mensaje

    return ""


def _payload_tiene_fallo(payload: dict[str, Any]) -> bool:
    if "fallo" not in payload:
        return False
    return bool(str(payload.get("fallo") or "").strip())


def _estado_busqueda_es_error(estado_busqueda: dict[str, Any] | None) -> bool:
    if not isinstance(estado_busqueda, dict):
        return False
    return str(estado_busqueda.get("estado") or "") == "error"


def interpretar_payload_http(
    herramienta: str,
    orden: int,
    payload: dict[str, Any],
    *,
    parametros: dict[str, Any] | None = None,
    ids_consulta: list[int] | None = None,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    ids, tipo_ids = extraer_ids_y_tipo(payload)
    nota = extraer_nota(payload)
    estado_busqueda = payload.get("estado_busqueda")
    if not isinstance(estado_busqueda, dict):
        estado_busqueda = construir_estado_busqueda_local(
            herramienta=herramienta,
            status=(
                "ok"
                if ids
                else (
                    "error"
                    if _payload_tiene_fallo(payload)
                    or _estado_busqueda_es_error(estado_busqueda)
                    else "sin_resultados"
                )
            ),
            ids_salida=ids,
            parametros=parametros or {},
            ids_entrada=ids_consulta or [],
            nota=nota,
            retroalimentacion=(
                payload.get("retroalimentacion")
                if isinstance(payload.get("retroalimentacion"), dict)
                else None
            ),
        )

    if ids:
        return (
            construir_estado(
                herramienta,
                orden,
                "ok",
                ids=ids,
                payload=payload,
                nota=nota,
                estado_busqueda=estado_busqueda,
            ),
            tipo_ids,
        )

    if _payload_tiene_fallo(payload) or _estado_busqueda_es_error(estado_busqueda):
        detalle = (
            nota
            or _detalle_estado_busqueda(estado_busqueda)
            or "La herramienta falló sin detalle."
        )
        payload_error = dict(payload)
        payload_error["fallo"] = detalle
        return (
            construir_estado(
                herramienta,
                orden,
                "error",
                payload=payload_error,
                nota=detalle,
                estado_busqueda=estado_busqueda,
            ),
            None,
        )

    if payload.get("sin_sitios") or payload.get("sin_rutas"):
        return (
            construir_estado(
                herramienta,
                orden,
                "sin_resultados",
                payload=payload,
                nota=nota,
                estado_busqueda=estado_busqueda,
            ),
            None,
        )

    return (
        construir_estado(
            herramienta,
            orden,
            "sin_resultados",
            payload=payload,
            nota=nota or "La herramienta no devolvió IDs.",
            estado_busqueda=estado_busqueda,
        ),
        None,
    )


def preparar_payload(
    parametros: dict[str, Any] | None,
    ids_consulta: list[int],
) -> dict[str, Any]:
    payload = deepcopy(parametros or {})
    payload["ids_consulta"] = normalizar_ids(ids_consulta)
    return payload


def _path_herramienta_diagnostico(cliente: Any, endpoint: str) -> str:
    if hasattr(cliente, "_path_herramienta"):
        return cliente._path_herramienta(endpoint)
    endpoint_normalizado = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"/api/v1/chatboot/herramientas{endpoint_normalizado}"


async def ejecutar_http_generico(
    *,
    herramienta: str,
    endpoint: str,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    cliente: Any,
    timeout_seconds: float | None = None,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    payload = preparar_payload(parametros, ids_consulta)
    timeout_efectivo = (
        float(timeout_seconds)
        if timeout_seconds is not None
        else getattr(cliente, "timeout_seconds", None)
    )
    inicio = time.perf_counter()
    try:
        respuesta = await cliente.post_herramienta(
            endpoint,
            payload,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        duracion_ms = int((time.perf_counter() - inicio) * 1000)
        detalle = _describir_excepcion(exc)
        diagnostico = {
            "endpoint": endpoint,
            "base_url": getattr(cliente, "base_url", None),
            "path": _path_herramienta_diagnostico(cliente, endpoint),
            "timeout_seconds": timeout_efectivo,
            "duracion_ms": duracion_ms,
            "tipo_error": type(exc).__name__,
        }
        estado_busqueda = construir_estado_busqueda_local(
            herramienta=herramienta,
            status="error",
            parametros=payload,
            ids_entrada=ids_consulta,
            nota=detalle,
            retroalimentacion={"diagnostico_http": diagnostico},
        )
        return (
            construir_estado(
                herramienta,
                orden,
                "error",
                payload={"fallo": detalle, "diagnostico_http": diagnostico},
                nota=detalle,
                estado_busqueda=estado_busqueda,
            ),
            None,
        )
    return interpretar_payload_http(
        herramienta,
        orden,
        respuesta,
        parametros=payload,
        ids_consulta=ids_consulta,
    )
