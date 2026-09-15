from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from application.nodes.chatboot_exploracion.herramientas.base import (
    ResultadoHerramienta,
    TipoIds,
    construir_estado,
    normalizar_ids,
    normalizar_ubicacion,
)
from application.nodes.chatboot_exploracion.herramientas.cliente_http import (
    ClienteHerramientasHTTP,
)
from application.nodes.chatboot_exploracion.herramientas.registry import (
    ejecutar_herramienta,
)
from application.shared.empaquetar_mensaje import construir_card, construir_globo

MAX_CARDS_VISIBLES = 5
MAX_CANDIDATOS_LLM_FINAL = 20
MOTIVO_UBICACION_REQUERIDA = "ubicacion_usuario_requerida"
MENSAJE_UBICACION_REQUERIDA = (
    "Para buscar opciones cercanas a ti, activa los permisos de ubicación "
    "en la configuración de la app e inténtalo de nuevo."
)
logger = logging.getLogger(__name__)


def _env_float(nombre: str, default: float) -> float:
    try:
        return max(0.1, float(os.getenv(nombre, str(default))))
    except (TypeError, ValueError):
        return default


TOOL_TIMEOUT_SECONDS = _env_float("EXPLORACION_TOOL_TIMEOUT_SECONDS", 12.0)
CONSULTA_TIMEOUT_SECONDS = _env_float("EXPLORACION_CONSULTA_TIMEOUT_SECONDS", 45.0)
CARD_TIMEOUT_SECONDS = _env_float("EXPLORACION_CARD_TIMEOUT_SECONDS", 5.0)
REDACTOR_TIMEOUT_SECONDS = _env_float("EXPLORACION_REDACTOR_TIMEOUT_SECONDS", 18.0)
FALLBACK_TIMEOUT_SECONDS = _env_float("EXPLORACION_FALLBACK_TIMEOUT_SECONDS", 12.0)

PROMPT_REDACCION_FILE = (
    Path(__file__).resolve().parents[1] / "promp" / "redactar_respuesta.md"
)
PROMPT_FALLBACK_FILE = (
    Path(__file__).resolve().parents[1] / "promp" / "redactar_fallback.md"
)


@lru_cache(maxsize=1)
def cargar_prompt_redactor_exploracion() -> str:
    return PROMPT_REDACCION_FILE.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def cargar_prompt_fallback_exploracion() -> str:
    return PROMPT_FALLBACK_FILE.read_text(encoding="utf-8")


async def ejecutar_plan_exploracion(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("plan_valido"):
        return {
            **state,
            "estados_herramientas": [],
            "ids_asociados": [],
            "mensajes_app": _mensajes_existentes(state),
            "entidades_resueltas": [],
        }

    plan = state.get("plan")
    consultas = plan.get("consultas") if isinstance(plan, dict) else None
    if not isinstance(consultas, list):
        mensaje = "No pude organizar las herramientas para esta consulta. ¿Puedes intentarlo de nuevo?"
        mensaje_app = construir_globo(mensaje, origen="ejecutar_plan_tools")
        return _construir_state_final(
            state,
            estados=[],
            ids_asociados=[],
            mensajes_app=[mensaje_app],
            entidades_resueltas=[],
            mensaje_sistema=mensaje,
            mensaje_app=mensaje_app,
        )

    cliente = ClienteHerramientasHTTP()
    sitios_cache: dict[str, Any] = {}
    resultados_consultas = await asyncio.gather(
        *[
            asyncio.wait_for(
                _ejecutar_consulta(consulta, state, cliente),
                timeout=CONSULTA_TIMEOUT_SECONDS,
            )
            for consulta in consultas
        ],
        return_exceptions=True,
    )

    estados: list[ResultadoHerramienta] = []
    diagnostico_redactor: dict[str, Any] | None = None
    resultados_normalizados, ids_sitio_finales, ids_ruta_finales = (
        _normalizar_resultados_consultas(resultados_consultas, estados)
    )

    await _anexar_gis_automatico(
        state=state,
        cliente=cliente,
        estados=estados,
        ids_sitio=ids_sitio_finales,
    )

    estado_ubicacion_requerida = _estado_ubicacion_requerida(estados)

    ids_asociados = _deduplicar(ids_sitio_finales)
    respuesta_pregunta_directa = _construir_respuesta_pregunta_directa(
        estados,
        ids_asociados,
    )
    if respuesta_pregunta_directa is not None:
        mensajes_app = respuesta_pregunta_directa["mensajes_app"]
        globo = mensajes_app[0] if mensajes_app else None
        return _construir_state_final(
            state,
            estados=estados,
            ids_asociados=respuesta_pregunta_directa["ids_asociados"],
            mensajes_app=mensajes_app,
            entidades_resueltas=respuesta_pregunta_directa["entidades_resueltas"],
            mensaje_sistema=(
                globo.get("mensaje", {}).get("texto")
                if isinstance(globo, dict)
                else None
            ),
            mensaje_app=globo if isinstance(globo, dict) else None,
        )

    bloques_app, entidades_resueltas, cards_redactor = await _construir_bloques_por_consulta(
        resultados=resultados_normalizados,
        cliente=cliente,
        sitios_cache=sitios_cache,
    )
    mensajes_directos = _extraer_mensajes_opciones(estados)
    mensaje_ubicacion_requerida = (
        construir_globo(
            MENSAJE_UBICACION_REQUERIDA,
            origen="busqueda_ubicacion",
        )
        if estado_ubicacion_requerida is not None
        else None
    )
    hay_candidatos_semanticos = _hay_candidatos_semanticos_debug(estados)

    if cards_redactor or ids_asociados or ids_ruta_finales or hay_candidatos_semanticos:
        if hay_candidatos_semanticos:
            ids_cards_existentes = _ids_desde_cards(cards_redactor)
            ids_candidatos_semanticos = [
                id_sitio
                for id_sitio in _ids_candidatos_semanticos_debug(estados)
                if id_sitio not in ids_cards_existentes
            ]
            if ids_candidatos_semanticos:
                cards_redactor.extend(
                    await _construir_cards(
                        ids_candidatos_semanticos,
                        cliente,
                        estados,
                        sitios_cache=sitios_cache,
                    )
                )
        resultado_final = await _rankear_y_redactar_resultados(
            state=state,
            estados=estados,
            cards=cards_redactor,
            ids_ruta=ids_ruta_finales,
        )
        diagnostico_redactor = resultado_final.pop("_debug_redactor", None)
        ids_validos = _deduplicar(resultado_final.get("ids_validos", []))[
            :MAX_CARDS_VISIBLES
        ]
        ids_posibles = _deduplicar(resultado_final.get("ids_posibles", []))
        ids_asociados = _deduplicar([*ids_validos, *ids_posibles])
        cards_visibles = _filtrar_cards_por_ids(cards_redactor, ids_validos)
        ids_sin_card = _ids_sin_card(ids_validos, cards_visibles)
        if ids_sin_card:
            cards_visibles.extend(
                await _construir_cards(
                    ids_sin_card,
                    cliente,
                    estados,
                    sitios_cache=sitios_cache,
                )
            )
        entidades_resueltas = _extraer_nombres_cards(cards_visibles)
        globo_principal = construir_globo(
            str(resultado_final.get("mensaje") or "").strip()
            or _globo_deterministico(estados, cards_visibles, ids_asociados, ids_ruta_finales),
            origen="redactor_exploracion",
        )
        bloques_app = _anexar_bloque_ids_asociados(
            _limitar_cards_visibles(cards_visibles, MAX_CARDS_VISIBLES),
            ids_asociados,
        )
        mensajes_app = [
            globo_principal,
            *bloques_app,
            *mensajes_directos,
        ]
        if mensaje_ubicacion_requerida is not None:
            mensajes_app.append(mensaje_ubicacion_requerida)
    elif _estado_fallback_principal(estados) is not None:
        mensajes_fallback = await _construir_mensajes_fallback_llm(
            state=state,
            estados=estados,
            cliente=cliente,
        )
        mensajes_app = mensajes_fallback
        if mensaje_ubicacion_requerida is not None:
            mensajes_app.append(mensaje_ubicacion_requerida)
        globo_principal = next(
            (mensaje for mensaje in mensajes_app if mensaje.get("tipo") == "globo"),
            mensajes_app[0] if mensajes_app else None,
        )
        ids_asociados = []
        entidades_resueltas = []
    elif mensajes_directos:
        mensajes_app = mensajes_directos
        if mensaje_ubicacion_requerida is not None:
            mensajes_app.append(mensaje_ubicacion_requerida)
        globo_principal = next(
            (mensaje for mensaje in mensajes_app if mensaje.get("tipo") == "globo"),
            mensajes_app[0] if mensajes_app else None,
        )
    else:
        globo_principal = construir_globo(
            _globo_deterministico(estados, [], ids_asociados, ids_ruta_finales),
            origen="redactor_exploracion",
        )
        mensajes_app = [globo_principal]
        if mensaje_ubicacion_requerida is not None:
            mensajes_app.append(mensaje_ubicacion_requerida)

    mensaje_app_principal = (
        globo_principal if isinstance(globo_principal, dict) else None
    )

    return _construir_state_final(
        state,
        estados=estados,
        ids_asociados=ids_asociados,
        mensajes_app=mensajes_app,
        entidades_resueltas=entidades_resueltas,
        mensaje_sistema=(
            mensaje_app_principal.get("mensaje", {}).get("texto")
            if isinstance(mensaje_app_principal, dict)
            else None
        ),
        mensaje_app=mensaje_app_principal,
        diagnostico_redactor=diagnostico_redactor,
    )


def _normalizar_resultados_consultas(
    resultados_consultas: list[Any],
    estados: list[ResultadoHerramienta],
) -> tuple[list[dict[str, Any]], list[int], list[int]]:
    """Convierte salidas de consultas paralelas en acumuladores del ejecutor."""

    ids_sitio_finales: list[int] = []
    ids_ruta_finales: list[int] = []
    resultados_normalizados: list[dict[str, Any]] = []

    for resultado in resultados_consultas:
        if isinstance(resultado, Exception):
            estado_error = _construir_estado_error_consulta(resultado)
            estados.append(estado_error)
            resultados_normalizados.append(
                {
                    "estados": [estado_error],
                    "ids": [],
                    "tipo_ids": "sitio",
                    "herramientas_plan": [],
                }
            )
            continue

        resultados_normalizados.append(resultado)
        estados.extend(resultado["estados"])
        if resultado["tipo_ids"] == "ruta":
            ids_ruta_finales.extend(resultado["ids"])
        else:
            ids_sitio_finales.extend(resultado["ids"])

    return resultados_normalizados, ids_sitio_finales, ids_ruta_finales


def _construir_estado_error_consulta(exc: Exception) -> ResultadoHerramienta:
    detalle = _describir_timeout_o_error(exc, "consulta")
    return {
        "herramienta": "consulta",
        "orden": 0,
        "status": "error",
        "ids": [],
        "payload": {"fallo": detalle},
        "nota": detalle,
    }


async def _ejecutar_consulta(
    consulta: Any,
    state: dict[str, Any],
    cliente: ClienteHerramientasHTTP,
) -> dict[str, Any]:
    ejecuciones = []
    if isinstance(consulta, dict) and isinstance(consulta.get("ejecucion_herramienta"), list):
        ejecuciones = consulta["ejecucion_herramienta"]

    ordenadas = sorted(
        [item for item in ejecuciones if isinstance(item, dict)],
        key=lambda item: int(item.get("orden") or 0),
    )

    estados: list[ResultadoHerramienta] = []
    ids_actuales: list[int] = []
    tipo_ids: TipoIds | None = None
    herramientas_plan: list[dict[str, Any]] = []

    for indice, item in enumerate(ordenadas):
        herramienta = item.get("herramienta") if isinstance(item.get("herramienta"), dict) else {}
        nombre = str(herramienta.get("nombre") or "").strip()
        parametros = herramienta.get("parametros") if isinstance(herramienta.get("parametros"), dict) else {}
        orden = int(item.get("orden") or indice + 1)
        herramientas_plan.append({"nombre": nombre, "parametros": parametros})

        estado_herramienta, nuevo_tipo = await _ejecutar_herramienta_con_timeout(
            nombre=nombre,
            orden=orden,
            parametros=parametros,
            ids_consulta=ids_actuales,
            tipo_ids=tipo_ids,
            state=state,
            cliente=cliente,
        )
        estados.append(estado_herramienta)

        status = estado_herramienta["status"]
        es_primera = indice == 0
        es_ultima = indice == len(ordenadas) - 1

        if status == "ok" and estado_herramienta["ids"]:
            ids_actuales = normalizar_ids(estado_herramienta["ids"])
            tipo_ids = nuevo_tipo or tipo_ids or "sitio"
            continue

        ids_candidatos_semanticos = _ids_candidatos_semanticos_estado(
            estado_herramienta
        )
        if (
            nombre in {"busqueda_semantica", "busqueda_semantica_consulta"}
            and ids_candidatos_semanticos
            and not es_ultima
        ):
            ids_actuales = ids_candidatos_semanticos
            tipo_ids = "sitio"
            continue

        if status != "ok" and es_primera:
            break

        if status in {"sin_resultados", "error"}:
            if es_ultima:
                if (
                    status == "sin_resultados"
                    and nombre not in {
                        "busqueda_semantica",
                        "busqueda_semantica_consulta",
                    }
                    and _estado_ubicacion_requerida([estado_herramienta]) is None
                ):
                    ids_actuales = []
                break
            continue

    return {
        "estados": estados,
        "ids": ids_actuales,
        "tipo_ids": tipo_ids or "sitio",
        "herramientas_plan": herramientas_plan,
    }


async def _ejecutar_herramienta_con_timeout(
    *,
    nombre: str,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: ClienteHerramientasHTTP,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    try:
        return await asyncio.wait_for(
            ejecutar_herramienta(
                nombre=nombre,
                orden=orden,
                parametros=parametros,
                ids_consulta=ids_consulta,
                tipo_ids=tipo_ids,
                state=state,
                cliente=cliente,
            ),
            timeout=TOOL_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        detalle = _describir_timeout_o_error(exc, nombre or "herramienta")
        logger.warning(
            "exploracion_tool_error herramienta=%s orden=%s timeout_seconds=%.1f error_type=%s error=%s",
            nombre,
            orden,
            TOOL_TIMEOUT_SECONDS,
            type(exc).__name__,
            detalle,
        )
        return (
            construir_estado(
                nombre or "herramienta",
                orden,
                "error",
                payload={
                    "fallo": detalle,
                    "timeout_seconds": TOOL_TIMEOUT_SECONDS,
                    "ids_entrada": ids_consulta,
                },
                nota=detalle,
            ),
            tipo_ids,
        )


def _describir_timeout_o_error(
    exc: Exception,
    contexto: str,
    timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return f"timeout_{contexto}_{timeout_seconds:.0f}s"
    texto = str(exc).strip()
    return texto or f"{type(exc).__name__} en {contexto}"


async def _anexar_gis_automatico(
    *,
    state: dict[str, Any],
    cliente: ClienteHerramientasHTTP,
    estados: list[ResultadoHerramienta],
    ids_sitio: list[int],
) -> None:
    if any(
        estado.get("herramienta") in {"gis", "gis_consulta", "busqueda_ubicacion", "busqueda_ubicacion_consulta"}
        for estado in estados
    ):
        return
    if not normalizar_ubicacion(state.get("ubicacion_usuario")):
        return
    if not _deduplicar(ids_sitio) and _hay_refinador_sin_resultados(estados):
        return

    ids_filtrados = _deduplicar(ids_sitio)
    ids_para_gis = (
        ids_filtrados
        if ids_filtrados
        else _ids_candidatos_semanticos_debug(estados)
    )[:MAX_CANDIDATOS_LLM_FINAL]
    if not ids_para_gis:
        return

    orden = max([int(estado.get("orden") or 0) for estado in estados] or [0]) + 1
    estado_gis, _ = await _ejecutar_herramienta_con_timeout(
        nombre="busqueda_ubicacion",
        orden=orden,
        parametros={
            "entidad": "sitio",
            "tipo_busqueda": "cercania",
            "referencia_ubicacion": "",
            "usar_ubicacion_usuario": True,
            "distancia": None,
            "unidad": "",
            "excluir_zonas": [],
        },
        ids_consulta=ids_para_gis,
        tipo_ids="sitio",
        state=state,
        cliente=cliente,
    )
    _marcar_estado_gis_automatico(estado_gis)
    estados.append(estado_gis)


def _marcar_estado_gis_automatico(estado: ResultadoHerramienta) -> None:
    payload = estado.setdefault("payload", {})
    payload["_origen"] = "gis_automatico"
    estado_busqueda = estado.get("estado_busqueda")
    if isinstance(estado_busqueda, dict):
        retroalimentacion = estado_busqueda.get("retroalimentacion")
        if not isinstance(retroalimentacion, dict):
            retroalimentacion = {}
            estado_busqueda["retroalimentacion"] = retroalimentacion
        retroalimentacion["origen"] = "gis_automatico"


def _estado_es_gis_automatico(estado: ResultadoHerramienta) -> bool:
    payload = estado.get("payload") or {}
    if payload.get("_origen") == "gis_automatico":
        return True
    estado_busqueda = estado.get("estado_busqueda")
    retroalimentacion = (
        estado_busqueda.get("retroalimentacion")
        if isinstance(estado_busqueda, dict)
        else {}
    )
    return (
        isinstance(retroalimentacion, dict)
        and retroalimentacion.get("origen") == "gis_automatico"
    )


def _construir_respuesta_pregunta_directa(
    estados: list[ResultadoHerramienta],
    ids_asociados: list[int],
) -> dict[str, Any] | None:
    estado = next(
        (item for item in estados if item.get("herramienta") == "pregunta_directa"),
        None,
    )
    if estado is None:
        return None

    payload = estado.get("payload") or {}
    if estado.get("status") == "ok":
        id_sitio = _primer_id_pregunta_directa(estado, payload)
        nombre = _primer_texto(payload.get("nombre"), payload.get("nombre_sitio"))
        texto = (
            f"Para conocer más a detalle sobre \"{nombre}\", te debo delegar "
            "al chatbot específico del sitio."
            if nombre
            else "Para conocer más a detalle sobre ese sitio, te debo delegar al chatbot específico del sitio."
        )
        globo = construir_globo(texto, origen="pregunta_directa")
        mensajes_app: list[dict[str, Any]] = [globo]
        if id_sitio is not None:
            mensajes_app.append(
                {
                    "tipo": "accion",
                    "mensaje": {
                        "accion": "abrir_chatbot_sitio",
                        "label": "Abrir chatbot del sitio",
                        "id_sitio": id_sitio,
                        "nombre_sitio": nombre,
                    },
                }
            )

        return {
            "ids_asociados": [id_sitio] if id_sitio is not None else ids_asociados,
            "mensajes_app": mensajes_app,
            "entidades_resueltas": [nombre] if nombre else [],
        }

    if estado.get("status") == "error":
        texto = (
            "No pude consultar el sitio específico en este momento. "
            "Intenta nuevamente con el nombre exacto del lugar."
        )
    else:
        sugerencias = _sugerencias_pregunta_directa(payload)
        if sugerencias:
            nombres = [sugerencia["nombre"] for sugerencia in sugerencias]
            texto = (
                "No identifiqué el sitio con total seguridad. "
                "Quizás te refieres a una de estas opciones registradas."
            )
            return {
                "ids_asociados": [
                    sugerencia["id_sitio"]
                    for sugerencia in sugerencias
                    if sugerencia.get("id_sitio") is not None
                ],
                "mensajes_app": [
                    construir_globo(texto, origen="pregunta_directa"),
                    {"tipo": "opciones", "mensaje": {"opciones": nombres}},
                ],
                "entidades_resueltas": nombres,
            }
        texto = (
            "No encontré un sitio registrado parecido a ese nombre. "
            "Intenta escribir el nombre del lugar con un poco más de detalle."
        )
    globo = construir_globo(texto, origen="pregunta_directa")
    return {
        "ids_asociados": [],
        "mensajes_app": [globo],
        "entidades_resueltas": [],
    }


def _primer_id_pregunta_directa(
    estado: ResultadoHerramienta,
    payload: dict[str, Any],
) -> int | None:
    for valor in [payload.get("id_sitio"), *(estado.get("ids") or [])]:
        try:
            id_sitio = int(valor)
        except (TypeError, ValueError):
            continue
        if id_sitio > 0:
            return id_sitio
    return None


def _sugerencias_pregunta_directa(payload: dict[str, Any]) -> list[dict[str, Any]]:
    valor = payload.get("sugerencias")
    if not isinstance(valor, list):
        return []
    sugerencias: list[dict[str, Any]] = []
    for item in valor:
        if not isinstance(item, dict):
            continue
        nombre = _primer_texto(item.get("nombre"), item.get("nombre_sitio"))
        if not nombre:
            continue
        try:
            id_sitio = int(item.get("id_sitio"))
        except (TypeError, ValueError):
            id_sitio = None
        sugerencias.append({"id_sitio": id_sitio, "nombre": nombre})
    return sugerencias[:5]


async def _obtener_sitios_catalogo(
    cliente: ClienteHerramientasHTTP,
    sitios_cache: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if sitios_cache is not None and "sitios" in sitios_cache:
        return sitios_cache["sitios"]
    try:
        sitios = await cliente.listar_sitios()
    except Exception:
        sitios = []
    if sitios_cache is not None:
        sitios_cache["sitios"] = sitios
    return sitios


async def _construir_cards(
    ids_asociados: list[int],
    cliente: ClienteHerramientasHTTP,
    estados: list[ResultadoHerramienta] | None = None,
    *,
    sitios_cache: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not ids_asociados:
        return []

    sitios = await _obtener_sitios_catalogo(cliente, sitios_cache)
    por_id: dict[int, dict[str, Any]] = {}
    for sitio in sitios:
        try:
            id_sitio = int(sitio.get("id_sitio"))
        except (TypeError, ValueError):
            continue
        por_id[id_sitio] = sitio

    ids_para_cards = [id_sitio for id_sitio in ids_asociados if id_sitio in por_id][
        :MAX_CANDIDATOS_LLM_FINAL
    ]
    completados = await asyncio.gather(
        *[
            asyncio.wait_for(
                _completar_datos_card(id_sitio, por_id[id_sitio], cliente),
                timeout=CARD_TIMEOUT_SECONDS,
            )
            for id_sitio in ids_para_cards
        ],
        return_exceptions=True,
    )
    completados_por_id = dict(zip(ids_para_cards, completados, strict=False))
    cards: list[dict[str, Any]] = []
    for id_sitio in ids_asociados:
        sitio = por_id.get(id_sitio)
        if not sitio:
            continue
        completado = completados_por_id.get(id_sitio)
        if isinstance(completado, Exception):
            direccion = _primer_texto(
                sitio.get("direccion"),
                sitio.get("direccion_texto"),
            )
            imagen_url = _primer_texto(
                sitio.get("img_Url"),
                sitio.get("imagen_url"),
                sitio.get("imagen_principal"),
            )
        else:
            direccion, imagen_url = completado or ("", "")
        cards.append(
            construir_card(
                {
                    "id_sitio": id_sitio,
                    "nombre_sitio": str(sitio.get("nombre") or ""),
                    "categoria": str(sitio.get("categoria") or ""),
                    "subcategoria": str(sitio.get("subcategoria") or ""),
                    "direccion": direccion,
                    "imagen_url": imagen_url,
                }
            )
        )
    return cards


async def _completar_datos_card(
    id_sitio: int,
    sitio: dict[str, Any],
    cliente: ClienteHerramientasHTTP,
) -> tuple[str, str]:
    direccion = _primer_texto(
        sitio.get("direccion"),
        sitio.get("direccion_texto"),
    )
    imagen_url = _primer_texto(
        sitio.get("img_Url"),
        sitio.get("imagen_url"),
        sitio.get("imagen_principal"),
    )
    if direccion and imagen_url:
        return direccion, imagen_url

    try:
        ficha = await cliente.obtener_ficha_sitio(id_sitio)
    except Exception:
        ficha = None
    if not isinstance(ficha, dict):
        return direccion, imagen_url

    direccion = direccion or _primer_texto(ficha.get("direccion"))
    imagen_url = imagen_url or _extraer_imagen_principal(ficha)
    return direccion, imagen_url


def _extraer_imagen_principal(ficha: dict[str, Any]) -> str:
    imagenes = ficha.get("imagenes")
    if not isinstance(imagenes, list):
        return ""

    for imagen in imagenes:
        if isinstance(imagen, dict) and imagen.get("es_principal"):
            url = _primer_texto(imagen.get("url"))
            if url:
                return url

    for imagen in imagenes:
        if isinstance(imagen, dict):
            url = _primer_texto(imagen.get("url"))
            if url:
                return url
    return ""


def _primer_texto(*valores: Any) -> str:
    for valor in valores:
        texto = str(valor or "").strip()
        if texto:
            return texto
    return ""


def _distancias_sitios_por_id(
    estados: list[ResultadoHerramienta],
) -> dict[int, dict[str, Any]]:
    distancias: dict[int, dict[str, Any]] = {}
    for estado in estados:
        if estado.get("herramienta") not in {"gis", "gis_consulta", "busqueda_ubicacion", "busqueda_ubicacion_consulta"}:
            continue
        if _estado_es_gis_automatico(estado):
            continue
        payload = estado.get("payload") or {}
        candidatos = payload.get("candidatos")
        if not isinstance(candidatos, list):
            continue
        for candidato in candidatos:
            if not isinstance(candidato, dict):
                continue
            try:
                id_sitio = int(candidato.get("id_sitio"))
            except (TypeError, ValueError):
                continue
            distancias[id_sitio] = {
                "id_sitio": id_sitio,
                "nombre": _primer_texto(candidato.get("nombre")),
                "distancia_metros": candidato.get("distancia_metros"),
                "distancia_aproximada": _primer_texto(
                    candidato.get("distancia_aproximada"),
                    _formatear_distancia(candidato.get("distancia_metros")),
                ),
            }
    return distancias


def _formatear_distancia(valor: Any) -> str:
    try:
        metros = float(valor)
    except (TypeError, ValueError):
        return ""
    if metros >= 1000:
        return f"{metros / 1000:.1f} km"
    return f"{int(round(metros))} m"


async def _construir_bloques_por_consulta(
    *,
    resultados: list[dict[str, Any]],
    cliente: ClienteHerramientasHTTP,
    sitios_cache: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    mensajes_app: list[dict[str, Any]] = []
    entidades_resueltas: list[str] = []
    cards_redactor: list[dict[str, Any]] = []

    for resultado in resultados:
        estados_consulta = [
            estado for estado in resultado.get("estados", []) if isinstance(estado, dict)
        ]
        ids_resultado = _deduplicar(resultado.get("ids") or [])
        if resultado.get("tipo_ids") == "ruta":
            ids_sitio: list[int] = []
            ids_ruta = ids_resultado
        else:
            ids_sitio = ids_resultado
            ids_ruta: list[int] = []

        mensajes_directos = _extraer_mensajes_opciones(estados_consulta)
        if mensajes_directos and not ids_sitio and not ids_ruta:
            continue

        cards = await _construir_cards(
            ids_sitio, cliente, estados_consulta, sitios_cache=sitios_cache
        )
        cards_redactor.extend(cards)
        mensajes_app.extend(cards)

        if ids_sitio:
            mensajes_app.append(
                {
                    "tipo": "ids_asociados",
                    "mensaje": {"ids_asociados": ids_sitio},
                }
            )

        entidades_resueltas.extend(_extraer_entidades_resueltas(estados_consulta, cards))

    return mensajes_app, _deduplicar_texto(entidades_resueltas), cards_redactor


def _resultados_para_redactor(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    vistos: set[int] = set()
    for card in cards:
        mensaje = card.get("mensaje") if isinstance(card, dict) else {}
        if not isinstance(mensaje, dict):
            continue
        try:
            id_sitio = int(mensaje.get("id_sitio"))
        except (TypeError, ValueError):
            continue
        if id_sitio <= 0 or id_sitio in vistos:
            continue
        nombre = _primer_texto(mensaje.get("nombre_sitio"), mensaje.get("nombre"))
        if not nombre:
            continue
        vistos.add(id_sitio)
        resultados.append({"id_sitio": id_sitio, "nombre_sitio": nombre})
    return resultados


def _ids_pipeline(estados: list[ResultadoHerramienta]) -> list[int]:
    ids: list[int] = []
    for estado in estados:
        ids.extend(normalizar_ids(estado.get("ids") or []))
    return _deduplicar(ids)


def _semanticos_por_id(estados: list[ResultadoHerramienta]) -> dict[int, dict[str, Any]]:
    por_id: dict[int, dict[str, Any]] = {}
    for estado in estados:
        if estado.get("herramienta") != "busqueda_semantica":
            continue
        payload = estado.get("payload") or {}
        candidatos = payload.get("candidatos")
        if not isinstance(candidatos, list):
            continue
        for candidato in candidatos:
            if not isinstance(candidato, dict):
                continue
            try:
                id_sitio = int(candidato.get("id_sitio"))
            except (TypeError, ValueError):
                continue
            actual = por_id.setdefault(id_sitio, {})
            actual.update(
                {
                    "nombre_sitio": _primer_texto(candidato.get("nombre")),
                    "score_semantico": candidato.get("score_semantico"),
                    "score_final": candidato.get("score_final"),
                    "boost_keywords": candidato.get("boost_keywords"),
                    "keywords_match": candidato.get("keywords_match") or [],
                    "supera_umbral": candidato.get("supera_umbral"),
                    "motivo": candidato.get("motivo"),
                    "contenido_chunk": _recortar_texto(
                        candidato.get("contenido_chunk"),
                        max_chars=400,
                    ),
                }
            )
    return por_id


def _candidatos_para_auditor(
    cards: list[dict[str, Any]],
    estados: list[ResultadoHerramienta],
) -> list[dict[str, Any]]:
    candidatos_por_id: dict[int, dict[str, Any]] = {}
    distancias = _distancias_sitios_por_id(estados)
    semanticos = _semanticos_por_id(estados)

    for card in cards:
        mensaje = card.get("mensaje") if isinstance(card, dict) else {}
        if not isinstance(mensaje, dict):
            continue
        try:
            id_sitio = int(mensaje.get("id_sitio"))
        except (TypeError, ValueError):
            continue
        candidatos_por_id[id_sitio] = {
            "id_sitio": id_sitio,
            "nombre_sitio": _primer_texto(mensaje.get("nombre_sitio"), mensaje.get("nombre")),
            "categoria": _primer_texto(mensaje.get("categoria")),
            "subcategoria": _primer_texto(mensaje.get("subcategoria")),
            "direccion": _primer_texto(mensaje.get("direccion")),
        }

    if not candidatos_por_id:
        for id_sitio in _ids_pipeline(estados):
            if id_sitio in candidatos_por_id:
                continue
            candidatos_por_id[id_sitio] = {
                "id_sitio": id_sitio,
                "nombre_sitio": "",
                "categoria": "",
            }

        for id_sitio, sem in semanticos.items():
            if id_sitio not in candidatos_por_id:
                candidatos_por_id[id_sitio] = {
                    "id_sitio": id_sitio,
                    "nombre_sitio": sem.get("nombre_sitio") or "",
                    "categoria": "",
                }

    for id_sitio, item in candidatos_por_id.items():
        if semanticos.get(id_sitio):
            sem = semanticos[id_sitio]
            item.update(sem)
            if not item.get("nombre_sitio"):
                item["nombre_sitio"] = sem.get("nombre_sitio") or ""
        distancia = distancias.get(id_sitio)
        if distancia:
            item["distancia_metros"] = distancia.get("distancia_metros")
            item["distancia_aproximada"] = distancia.get("distancia_aproximada")

    salida = list(candidatos_por_id.values())
    salida.sort(
        key=lambda item: (
            float(item.get("score_final") or 0),
            -int(item.get("id_sitio") or 0),
        ),
        reverse=True,
    )
    return [item for item in salida if item.get("nombre_sitio") or item.get("id_sitio")]


def _candidatos_compactos_llm(
    cards: list[dict[str, Any]],
    estados: list[ResultadoHerramienta],
) -> list[dict[str, Any]]:
    candidatos = _candidatos_para_auditor(cards, estados)
    motivos_por_id = _motivos_por_candidato(estados)
    evidencias_por_id = _evidencias_por_candidato(estados)
    compactos: list[dict[str, Any]] = []
    for candidato in candidatos:
        id_sitio = int(candidato.get("id_sitio") or 0)
        evidencias = evidencias_por_id.get(id_sitio, {})
        compactos.append(
            {
                "id": id_sitio,
                "categoria": _primer_texto(candidato.get("categoria")),
                "subcategoria": _primer_texto(candidato.get("subcategoria")),
                "nombre": _primer_texto(
                    candidato.get("nombre_sitio"),
                    candidato.get("nombre"),
                ),
                "score_semantico": _redondear_score(candidato.get("score_semantico")),
                "score_final": _redondear_score(candidato.get("score_final")),
                "tipo_coincidencia": (
                    "fuerte" if candidato.get("supera_umbral") is True else "candidato"
                ),
                "keywords_match": _lista_textos(candidato.get("keywords_match"))[:5],
                "fragmento_semantico": _primer_texto(candidato.get("contenido_chunk")),
                "distancia_metros": candidato.get("distancia_metros"),
                "distancia_aproximada": _primer_texto(
                    candidato.get("distancia_aproximada")
                ),
                "precio_evidencia": evidencias.get("precio"),
                "tarifa_evidencia": evidencias.get("tarifa_acceso"),
                "horario_evidencia": evidencias.get("horario"),
                "atributos_evidencia": evidencias.get("atributos_booleanos"),
                "filtros_cumplidos": evidencias.get("filtros_cumplidos", []),
                "filtros_no_confirmados": evidencias.get("filtros_no_confirmados", []),
                "motivos": motivos_por_id.get(id_sitio, []),
                "_score": _score_candidato(candidato),
            }
        )
    compactos.sort(key=lambda item: (float(item.get("_score") or 0), -int(item["id"])), reverse=True)
    for item in compactos:
        item.pop("_score", None)
    return compactos[:MAX_CANDIDATOS_LLM_FINAL]


def _evidencias_por_candidato(
    estados: list[ResultadoHerramienta],
) -> dict[int, dict[str, Any]]:
    evidencias: dict[int, dict[str, Any]] = {}
    herramientas_evidencia = {
        "precio",
        "tarifa_acceso",
        "horario",
        "atributos_booleanos",
    }
    for estado in estados:
        herramienta = str(estado.get("herramienta") or "")
        payload = estado.get("payload") or {}
        ids_estado = normalizar_ids(estado.get("ids") or [])
        if herramienta in herramientas_evidencia:
            candidatos = payload.get("candidatos")
            if isinstance(candidatos, list):
                for candidato in candidatos:
                    if not isinstance(candidato, dict):
                        continue
                    try:
                        id_sitio = int(candidato.get("id_sitio"))
                    except (TypeError, ValueError):
                        continue
                    if id_sitio <= 0:
                        continue
                    item = evidencias.setdefault(
                        id_sitio,
                        {"filtros_cumplidos": [], "filtros_no_confirmados": []},
                    )
                    item[herramienta] = _limpiar_evidencia_herramienta(
                        herramienta,
                        candidato,
                    )
                    if candidato.get("criterio_cumplido") is True:
                        _agregar_unico(item["filtros_cumplidos"], herramienta)
                    else:
                        _agregar_unico(item["filtros_no_confirmados"], herramienta)
                continue
        if ids_estado and herramienta in herramientas_evidencia:
            for id_sitio in ids_estado:
                item = evidencias.setdefault(
                    id_sitio,
                    {"filtros_cumplidos": [], "filtros_no_confirmados": []},
                )
                if herramienta == "atributos_booleanos":
                    item[herramienta] = _evidencia_atributos_desde_estado(estado)
                _agregar_unico(item["filtros_cumplidos"], herramienta)

    herramientas_no_confirmadas = [
        str(estado.get("herramienta") or "")
        for estado in estados
        if str(estado.get("herramienta") or "") in herramientas_evidencia
        and estado.get("status") != "ok"
    ]
    if herramientas_no_confirmadas:
        ids_candidatos = _ids_pipeline(estados)
        for id_sitio in ids_candidatos:
            item = evidencias.setdefault(
                id_sitio,
                {"filtros_cumplidos": [], "filtros_no_confirmados": []},
            )
            for herramienta in herramientas_no_confirmadas:
                _agregar_unico(item["filtros_no_confirmados"], herramienta)
    return evidencias


def _limpiar_evidencia_herramienta(
    herramienta: str,
    candidato: dict[str, Any],
) -> dict[str, Any]:
    claves_por_herramienta = {
        "precio": {
            "es_gratuito",
            "precio_min",
            "precio_max",
            "etiqueta_precio",
            "criterio_cumplido",
        },
        "tarifa_acceso": {
            "precio",
            "condicion",
            "entrada_gratuita",
            "criterio_cumplido",
        },
        "horario": {
            "abierto_24h",
            "horario_texto",
            "comentario",
            "cumplimiento_condicional",
            "dias_semana_resueltos",
            "hora_consultada",
            "criterio_cumplido",
        },
        "atributos_booleanos": {
            "tiene_wifi",
            "permite_mascotas",
            "accesibilidad",
            "parqueadero",
            "es_gratuito",
            "criterio_cumplido",
        },
    }
    claves = claves_por_herramienta.get(herramienta, set())
    return {
        clave: candidato.get(clave)
        for clave in claves
        if candidato.get(clave) not in (None, "", [])
    }


def _evidencia_atributos_desde_estado(estado: ResultadoHerramienta) -> dict[str, Any]:
    estado_busqueda = estado.get("estado_busqueda")
    filtros = (
        estado_busqueda.get("filtros")
        if isinstance(estado_busqueda, dict)
        else None
    )
    valor: dict[str, Any] = {}
    if isinstance(filtros, list):
        for filtro in filtros:
            if not isinstance(filtro, dict):
                continue
            filtro_valor = filtro.get("valor")
            if isinstance(filtro_valor, dict):
                valor.update(filtro_valor)
    payload = estado.get("payload") or {}
    if not valor:
        valor.update(
            {
                key: payload.get(key)
                for key in (
                    "tiene_wifi",
                    "permite_mascotas",
                    "accesibilidad",
                    "parqueadero",
                    "es_gratuito",
                )
                if payload.get(key) not in (None, "", [])
            }
        )
    salida = {
        key: valor.get(key)
        for key in (
            "tiene_wifi",
            "permite_mascotas",
            "accesibilidad",
            "parqueadero",
            "es_gratuito",
        )
        if valor.get(key) not in (None, "", [])
    }
    if salida:
        salida["criterio_cumplido"] = estado.get("status") == "ok"
    return salida


def _agregar_unico(lista: list[Any], valor: Any) -> None:
    if valor not in lista:
        lista.append(valor)


def _redondear_score(valor: Any) -> float | None:
    try:
        return round(float(valor), 4)
    except (TypeError, ValueError):
        return None


def _lista_textos(valor: Any) -> list[str]:
    if not isinstance(valor, list):
        return []
    return [str(item).strip() for item in valor if str(item or "").strip()]


def _hay_candidatos_semanticos_debug(estados: list[ResultadoHerramienta]) -> bool:
    return bool(_ids_candidatos_semanticos_debug(estados))


def _hay_refinador_sin_resultados(estados: list[ResultadoHerramienta]) -> bool:
    herramientas_base = {
        "busqueda_semantica",
        "busqueda_semantica_consulta",
        "gis",
        "gis_consulta",
        "busqueda_ubicacion",
        "busqueda_ubicacion_consulta",
        "fallback",
        "conversacional",
        "pregunta_directa",
    }
    return any(
        estado.get("status") == "sin_resultados"
        and estado.get("herramienta") not in herramientas_base
        for estado in estados
    )


def _ids_candidatos_semanticos_debug(estados: list[ResultadoHerramienta]) -> list[int]:
    ids: list[int] = []
    for estado in estados:
        if estado.get("herramienta") != "busqueda_semantica":
            continue
        ids.extend(_ids_candidatos_semanticos_estado(estado))
    return _deduplicar(ids)[:MAX_CANDIDATOS_LLM_FINAL]


def _ids_candidatos_semanticos_estado(estado: ResultadoHerramienta) -> list[int]:
    ids: list[int] = []
    if estado.get("herramienta") != "busqueda_semantica":
        return ids
    payload = estado.get("payload") or {}
    candidatos = payload.get("candidatos")
    if not isinstance(candidatos, list):
        return ids
    for candidato in candidatos:
        if not isinstance(candidato, dict):
            continue
        try:
            id_sitio = int(candidato.get("id_sitio"))
        except (TypeError, ValueError):
            continue
        if id_sitio > 0:
            ids.append(id_sitio)
    return _deduplicar(ids)[:MAX_CANDIDATOS_LLM_FINAL]


def _motivos_por_candidato(
    estados: list[ResultadoHerramienta],
) -> dict[int, list[dict[str, Any]]]:
    motivos: dict[int, list[dict[str, Any]]] = {}
    for estado in estados:
        ids = normalizar_ids(estado.get("ids") or [])
        if ids:
            motivo = {
                "herramienta": estado.get("herramienta"),
                "estado": _estado_busqueda_simple(estado),
                "detalle": _recortar_texto(estado.get("nota"), max_chars=180),
            }
            for id_sitio in ids:
                motivos.setdefault(id_sitio, []).append(motivo)
        if estado.get("herramienta") != "busqueda_semantica":
            continue
        payload = estado.get("payload") or {}
        candidatos = payload.get("candidatos")
        if not isinstance(candidatos, list):
            continue
        for candidato in candidatos:
            if not isinstance(candidato, dict):
                continue
            try:
                id_sitio = int(candidato.get("id_sitio"))
            except (TypeError, ValueError):
                continue
            if id_sitio <= 0:
                continue
            detalle = _primer_texto(
                candidato.get("motivo"),
                candidato.get("contenido_chunk"),
                estado.get("nota"),
            )
            motivos.setdefault(id_sitio, []).append(
                {
                    "herramienta": estado.get("herramienta"),
                    "estado": _estado_busqueda_simple(estado),
                    "detalle": _recortar_texto(detalle, max_chars=180),
                }
            )
    return motivos


def _estado_busqueda_simple(estado: ResultadoHerramienta) -> str:
    estado_busqueda = estado.get("estado_busqueda")
    if isinstance(estado_busqueda, dict) and estado_busqueda.get("estado"):
        return str(estado_busqueda.get("estado"))
    return str(estado.get("status") or "")


def _score_candidato(candidato: dict[str, Any]) -> float:
    for clave in ("score_final", "score_semantico"):
        try:
            return float(candidato.get(clave) or 0)
        except (TypeError, ValueError):
            continue
    return 0.0


def _recortar_estado_busqueda(estado_busqueda: dict[str, Any]) -> dict[str, Any]:
    salida = {
        "estado": estado_busqueda.get("estado"),
        "ids_entrada": estado_busqueda.get("ids_entrada") or [],
        "ids_salida": estado_busqueda.get("ids_salida") or [],
        "filtros": [],
        "retroalimentacion": estado_busqueda.get("retroalimentacion") or {},
    }
    filtros = estado_busqueda.get("filtros")
    if isinstance(filtros, list):
        for filtro in filtros:
            if not isinstance(filtro, dict):
                continue
            salida["filtros"].append(
                {
                    "nombre": filtro.get("nombre"),
                    "valor": filtro.get("valor") or {},
                    "estado": filtro.get("estado"),
                    "detalle": _recortar_texto(filtro.get("detalle"), max_chars=240),
                }
            )
    return salida


def _construir_resumen_busqueda(
    estados: list[ResultadoHerramienta],
) -> dict[str, list[dict[str, Any]]]:
    resumen: dict[str, list[dict[str, Any]]] = {
        "cumplidos": [],
        "no_cumplidos": [],
        "aproximados": [],
        "errores": [],
    }
    mapa = {
        "cumplido": "cumplidos",
        "no_cumplido": "no_cumplidos",
        "aproximado": "aproximados",
        "error": "errores",
    }
    for estado in estados:
        if _estado_es_gis_automatico(estado):
            continue
        estado_busqueda = estado.get("estado_busqueda")
        if not isinstance(estado_busqueda, dict):
            continue
        clave = mapa.get(str(estado_busqueda.get("estado") or ""))
        if not clave:
            continue
        filtros = estado_busqueda.get("filtros")
        detalle = estado.get("nota") or ""
        valor: dict[str, Any] = {}
        if isinstance(filtros, list) and filtros:
            filtro = filtros[0] if isinstance(filtros[0], dict) else {}
            detalle = str(filtro.get("detalle") or detalle)
            valor = filtro.get("valor") if isinstance(filtro.get("valor"), dict) else {}
        resumen[clave].append(
            {
                "herramienta": estado.get("herramienta"),
                "detalle": _recortar_texto(detalle, max_chars=220),
                "valor": valor,
                "ids_salida": estado_busqueda.get("ids_salida") or [],
            }
        )
    return resumen


def _estados_herramientas_redactor(
    estados: list[ResultadoHerramienta],
) -> list[dict[str, Any]]:
    compactos: list[dict[str, Any]] = []
    for estado in estados:
        if _estado_es_gis_automatico(estado):
            continue
        estado_busqueda = estado.get("estado_busqueda")
        compactos.append(
            {
                "herramienta": estado.get("herramienta"),
                "orden": estado.get("orden"),
                "status": estado.get("status"),
                "nota": _recortar_texto(estado.get("nota"), max_chars=220),
                "ids": normalizar_ids(estado.get("ids") or []),
                "estado_busqueda": (
                    _recortar_estado_busqueda(estado_busqueda)
                    if isinstance(estado_busqueda, dict)
                    else {}
                ),
            }
        )
    return compactos


def _recortar_texto(valor: Any, *, max_chars: int) -> str:
    texto = str(valor or "").strip()
    if len(texto) <= max_chars:
        return texto
    return f"{texto[:max_chars].rstrip()}..."


async def _rankear_y_redactar_resultados(
    *,
    state: dict[str, Any],
    estados: list[ResultadoHerramienta],
    cards: list[dict[str, Any]],
    ids_ruta: list[int],
) -> dict[str, Any]:
    candidatos = _candidatos_compactos_llm(cards, estados)
    if not candidatos:
        resultado_sin_candidatos = {
            "mensaje": _globo_deterministico(estados, cards, [], ids_ruta),
            "ids_validos": [],
            "ids_posibles": [],
        }
        if state.get("debug_redactor"):
            resultado_sin_candidatos["_debug_redactor"] = {
                "plan": state.get("plan"),
                "estados_herramientas": estados,
                "candidatos_llm": [],
                "respuesta_llm_cruda": None,
                "ids_pintados": [],
            }
        return resultado_sin_candidatos

    prompt = {
        "mensaje_usuario": state.get("texto_usuario", ""),
        "instruccion": (
            "Elige hasta 5 ids_validos en orden de conveniencia para la persona. "
            "Solo ids_validos se muestran como tarjetas. No nombres ids_posibles en el mensaje. "
            "Si no hay coincidencias razonables, devuelve ids_validos vacío y dilo con honestidad."
        ),
        "candidatos": candidatos[:MAX_CANDIDATOS_LLM_FINAL],
        "resumen_busqueda": _construir_resumen_busqueda(estados),
        "estados_herramientas": _estados_herramientas_redactor(estados),
    }
    try:
        from infrastructure.llms import get_llm_router

        router = get_llm_router()
        route_settings = router.get_route_settings("exploracion")
        client = router.get_client_for_route("exploracion")
        respuesta_llm = await asyncio.wait_for(
            client.generate_response(
                "",
                thinking_enabled=route_settings.thinking_enabled,
                system_prompt=cargar_prompt_redactor_exploracion(),
                user_content=json.dumps(prompt, ensure_ascii=False, indent=2),
                json_response=True,
            ),
            timeout=REDACTOR_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning(
            "exploracion_redactor_error timeout_seconds=%.1f error_type=%s error=%s",
            REDACTOR_TIMEOUT_SECONDS,
            type(exc).__name__,
            _describir_timeout_o_error(exc, "redactor", REDACTOR_TIMEOUT_SECONDS),
        )
        resultado_fallback = _fallback_ranker_redactor(candidatos, estados, cards, ids_ruta)
        if state.get("debug_redactor"):
            resultado_fallback["_debug_redactor"] = _diagnostico_redactor(
                state,
                estados,
                candidatos,
                None,
                resultado_fallback.get("ids_validos", []),
            )
        return resultado_fallback

    resultado = _extraer_resultado_ranker(
        respuesta_llm,
        _ids_desde_resultados(candidatos),
    )
    if resultado is None:
        resultado_fallback = _fallback_ranker_redactor(candidatos, estados, cards, ids_ruta)
        if state.get("debug_redactor"):
            resultado_fallback["_debug_redactor"] = _diagnostico_redactor(
                state,
                estados,
                candidatos,
                respuesta_llm,
                resultado_fallback.get("ids_validos", []),
            )
        return resultado_fallback
    if not resultado["mensaje"]:
        resultado["mensaje"] = _globo_deterministico(
            estados,
            _filtrar_cards_por_ids(cards, resultado["ids_validos"]),
            resultado["ids_validos"],
            ids_ruta,
        )
    if state.get("debug_redactor"):
        resultado["_debug_redactor"] = _diagnostico_redactor(
            state,
            estados,
            candidatos,
            respuesta_llm,
            resultado.get("ids_validos", []),
        )
    return resultado


def _diagnostico_redactor(
    state: dict[str, Any],
    estados: list[ResultadoHerramienta],
    candidatos: list[dict[str, Any]],
    respuesta_llm: Any,
    ids_pintados: list[int],
) -> dict[str, Any]:
    return {
        "plan": state.get("plan"),
        "estados_herramientas": estados,
        "candidatos_llm": candidatos[:MAX_CANDIDATOS_LLM_FINAL],
        "respuesta_llm_cruda": _json_debugable(respuesta_llm),
        "ids_pintados": _deduplicar(ids_pintados),
    }


def _json_debugable(valor: Any) -> Any:
    try:
        json.dumps(valor, ensure_ascii=False)
        return valor
    except (TypeError, ValueError):
        return repr(valor)


def _extraer_resultado_ranker(
    respuesta_llm: Any,
    ids_permitidos: list[int],
) -> dict[str, Any] | None:
    data = respuesta_llm
    if isinstance(data, str):
        data = _extraer_json_objeto(data)
    if not isinstance(data, dict):
        return None

    permitidos = set(_deduplicar(ids_permitidos))
    ids_validos = _ids_desde_lista_permitida(data.get("ids_validos"), permitidos)[
        :MAX_CARDS_VISIBLES
    ]
    ids_posibles = [
        id_sitio
        for id_sitio in _ids_desde_lista_permitida(data.get("ids_posibles"), permitidos)
        if id_sitio not in set(ids_validos)
    ]

    return {
        "mensaje": _limpiar_texto_redactor(data.get("mensaje") or ""),
        "ids_validos": ids_validos,
        "ids_posibles": ids_posibles,
    }


def _ids_desde_lista_permitida(valor: Any, permitidos: set[int]) -> list[int]:
    if not isinstance(valor, list):
        return []
    ids: list[int] = []
    for item in valor:
        try:
            id_sitio = int(item)
        except (TypeError, ValueError):
            continue
        if id_sitio in permitidos:
            ids.append(id_sitio)
    return _deduplicar(ids)


def _fallback_ranker_redactor(
    candidatos: list[dict[str, Any]],
    estados: list[ResultadoHerramienta],
    cards: list[dict[str, Any]],
    ids_ruta: list[int],
) -> dict[str, Any]:
    ids = _ids_desde_resultados(candidatos)
    ids_validos = ids[:MAX_CARDS_VISIBLES]
    ids_posibles = ids[MAX_CARDS_VISIBLES:MAX_CANDIDATOS_LLM_FINAL]
    return {
        "mensaje": _globo_deterministico(
            estados,
            _filtrar_cards_por_ids(cards, ids_validos),
            ids_validos,
            ids_ruta,
        ),
        "ids_validos": ids_validos,
        "ids_posibles": ids_posibles,
    }


async def _redactar_fallback_llm(
    *,
    state: dict[str, Any],
    estados: list[ResultadoHerramienta],
    cliente: ClienteHerramientasHTTP,
) -> dict[str, Any]:
    estado_fallback = _estado_fallback_principal(estados)
    motivo = _motivo_fallback(estado_fallback)
    try:
        opciones_catalogo = await cliente.obtener_opciones_fallback_exploracion()
    except Exception:
        opciones_catalogo = []

    prompt = {
        "mensaje_usuario": state.get("texto_usuario", ""),
        "motivo": motivo,
        "memoria": dict(state.get("memoria") or {"turnos": []}),
        "estado_herramientas": _estados_compactos_fallback(estados),
        "opciones_catalogo": opciones_catalogo,
    }
    try:
        from infrastructure.llms import get_llm_router

        router = get_llm_router()
        try:
            route_settings = router.get_route_settings("exploracion_fallback")
            client_llm = router.get_client_for_route("exploracion_fallback")
        except Exception:
            route_settings = router.get_route_settings("exploracion")
            client_llm = router.get_client_for_route("exploracion")
        respuesta_llm = await asyncio.wait_for(
            client_llm.generate_response(
                "",
                thinking_enabled=route_settings.thinking_enabled,
                system_prompt=cargar_prompt_fallback_exploracion(),
                user_content=json.dumps(prompt, ensure_ascii=False, indent=2),
                json_response=True,
            ),
            timeout=FALLBACK_TIMEOUT_SECONDS,
        )
    except Exception:
        return _fallback_deterministico_inteligente(
            motivo,
            opciones_catalogo,
            mensaje_usuario=state.get("texto_usuario", ""),
        )

    resultado = _extraer_resultado_fallback_llm(respuesta_llm)
    if resultado is None or not resultado["mensaje"]:
        return _fallback_deterministico_inteligente(
            motivo,
            opciones_catalogo,
            mensaje_usuario=state.get("texto_usuario", ""),
        )
    motivo_resuelto = _inferir_motivo_fallback_deterministico(
        motivo,
        state.get("texto_usuario", ""),
    )
    if not _debe_mostrar_opciones_fallback(motivo_resuelto):
        resultado["opciones"] = []
    return resultado


async def _construir_mensajes_fallback_llm(
    *,
    state: dict[str, Any],
    estados: list[ResultadoHerramienta],
    cliente: ClienteHerramientasHTTP,
) -> list[dict[str, Any]]:
    if _estado_fallback_principal(estados) is None:
        return []
    respuesta = await _redactar_fallback_llm(
        state=state,
        estados=estados,
        cliente=cliente,
    )
    mensajes: list[dict[str, Any]] = [
        construir_globo(respuesta["mensaje"], origen="fallback_llm")
    ]
    if respuesta["opciones"]:
        mensajes.append({"tipo": "opciones", "mensaje": {"opciones": respuesta["opciones"]}})
    return mensajes


def _extraer_resultado_fallback_llm(respuesta_llm: Any) -> dict[str, Any] | None:
    data = respuesta_llm
    if isinstance(data, str):
        data = _extraer_json_objeto(data)
    if not isinstance(data, dict):
        return None
    mensaje = _limpiar_texto_redactor(data.get("mensaje") or "")
    opciones = _opciones_fallback_desde_valor(data.get("opciones"))
    return {"mensaje": mensaje, "opciones": opciones[:6]}


def _opciones_fallback_desde_valor(valor: Any) -> list[str]:
    if not isinstance(valor, list):
        return []
    opciones: list[str] = []
    for item in valor:
        texto = str(item or "").strip()
        if texto and texto not in opciones:
            opciones.append(texto)
    return opciones


def _fallback_deterministico_inteligente(
    motivo: str,
    opciones_catalogo: list[dict[str, Any]],
    *,
    mensaje_usuario: str = "",
) -> dict[str, Any]:
    motivo_resuelto = _inferir_motivo_fallback_deterministico(motivo, mensaje_usuario)
    mensajes = {
        "fuera_de_dominio": (
            "Puedo orientarte mejor con búsquedas turísticas de Riobamba y Chimborazo: "
            "lugares para visitar, comer, hospedarte o recorrer."
        ),
        "fuera_de_riobamba": (
            "Por ahora mi alcance está centrado en Riobamba y Chimborazo. "
            "Si buscas algo dentro de esa zona, te ayudo a filtrarlo."
        ),
        "prompt_inyeccion": (
            "Puedo ayudarte con consultas turísticas de forma segura. "
            "Cuéntame qué lugar o experiencia quieres encontrar."
        ),
        "sin_entidad_previa": (
            "Necesito un poco más de contexto: dime el nombre del lugar o qué opción "
            "quieres revisar."
        ),
        "consultas_rutas_distancias": (
            "Para orientarte mejor, dime si buscas una ruta turística de senderismo, "
            "ciclismo, caminata urbana o montañismo, y desde dónde quieres partir."
        ),
        "capacidad_no_soportada": (
            "Puedo ayudarte a buscar por tipo de lugar, ubicación, horario, precio, "
            "accesibilidad, mascotas, entrada, contacto o rutas turísticas; pero no "
            "afirmar cuál es el mejor sin datos verificables."
        ),
        "rutas_buses": (
            "Este chat no responde directamente rutas de buses, pero puedes revisarlas "
            "en el mapa del aplicativo. Si buscas una ruta turística o un lugar cercano, "
            "también puedo ayudarte a encontrarlo."
        ),
    }
    return {
        "mensaje": mensajes.get(
            motivo_resuelto,
            "Para ayudarte mejor, dime qué tipo de lugar o experiencia turística buscas.",
        ),
        "opciones": (
            _opciones_desde_catalogo_fallback(opciones_catalogo)
            if _debe_mostrar_opciones_fallback(motivo_resuelto)
            else []
        ),
    }


def _inferir_motivo_fallback_deterministico(motivo: str, mensaje_usuario: str) -> str:
    if motivo and motivo != "no_clasificado":
        return motivo
    texto = str(mensaje_usuario or "").lower()
    if any(palabra in texto for palabra in ("google", "brave", "facebook", "instagram", "whatsapp", "tiktok")):
        return "fuera_de_dominio"
    if any(palabra in texto for palabra in ("quito", "guayaquil", "cuenca", "ambato", "baños", "banos")):
        return "fuera_de_riobamba"
    if any(palabra in texto for palabra in ("ruta de bus", "rutas de bus", "bus", "transporte público", "transporte publico", "parada")):
        return "rutas_buses"
    if any(palabra in texto for palabra in ("de antes", "del anterior", "de esos", "de esas", "anterior", "anteriores", "esas opciones")):
        return "sin_entidad_previa"
    if any(palabra in texto for palabra in ("mejor", "mejores", "ranking", "comparar", "cuál de", "cual de")):
        return "capacidad_no_soportada"
    return "sin_intencion_clara"


def _debe_mostrar_opciones_fallback(motivo: str) -> bool:
    return motivo in {
        "sin_intencion_clara",
        "consultas_rutas_distancias",
        "capacidad_no_soportada",
    }


def _opciones_desde_catalogo_fallback(opciones_catalogo: list[dict[str, Any]]) -> list[str]:
    opciones: list[str] = []
    for item in opciones_catalogo:
        subcategorias = item.get("subcategorias")
        if isinstance(subcategorias, list):
            for subcategoria in subcategorias:
                texto = str(subcategoria or "").strip()
                if texto and texto not in opciones:
                    opciones.append(texto)
                if len(opciones) >= 6:
                    return opciones
        categoria = str(item.get("categoria") or "").strip()
        if categoria and categoria not in opciones:
            opciones.append(categoria)
        if len(opciones) >= 6:
            return opciones
    return opciones


def _estado_fallback_principal(
    estados: list[ResultadoHerramienta],
) -> ResultadoHerramienta | None:
    return next((estado for estado in estados if estado.get("herramienta") == "fallback"), None)


def _estado_ubicacion_requerida(
    estados: list[ResultadoHerramienta],
) -> ResultadoHerramienta | None:
    for estado in estados:
        if estado.get("herramienta") not in {
            "gis",
            "gis_consulta",
            "busqueda_ubicacion",
            "busqueda_ubicacion_consulta",
        }:
            continue
        payload = estado.get("payload") or {}
        if payload.get("motivo") == MOTIVO_UBICACION_REQUERIDA:
            return estado
        estado_busqueda = estado.get("estado_busqueda")
        retroalimentacion = (
            estado_busqueda.get("retroalimentacion")
            if isinstance(estado_busqueda, dict)
            else {}
        )
        if (
            isinstance(retroalimentacion, dict)
            and retroalimentacion.get("motivo") == MOTIVO_UBICACION_REQUERIDA
        ):
            return estado
    return None


def _motivo_fallback(estado: ResultadoHerramienta | None) -> str:
    payload = estado.get("payload") if isinstance(estado, dict) else {}
    motivo = str((payload or {}).get("motivo") or "").strip()
    if motivo:
        return motivo
    return "sin_intencion_clara"


def _estados_compactos_fallback(
    estados: list[ResultadoHerramienta],
) -> list[dict[str, Any]]:
    compactos: list[dict[str, Any]] = []
    for estado in estados:
        compactos.append(
            {
                "herramienta": estado.get("herramienta"),
                "status": estado.get("status"),
                "nota": _recortar_texto(estado.get("nota"), max_chars=180),
                "payload": {
                    key: value
                    for key, value in (estado.get("payload") or {}).items()
                    if key in {"motivo", "fallo", "sin_sitios", "sin_rutas"}
                },
            }
        )
    return compactos


def _extraer_json_objeto(texto: str) -> dict[str, Any] | None:
    limpio = str(texto or "").strip()
    if not limpio:
        return None
    if limpio.startswith("```"):
        limpio = re.sub(r"^```(?:json)?\s*", "", limpio, flags=re.IGNORECASE)
        limpio = re.sub(r"\s*```$", "", limpio).strip()
    try:
        data = json.loads(limpio)
    except json.JSONDecodeError:
        inicio = limpio.find("{")
        fin = limpio.rfind("}")
        if inicio < 0 or fin <= inicio:
            return None
        try:
            data = json.loads(limpio[inicio : fin + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _seleccionar_resultados_visibles(
    resultados: list[dict[str, Any]],
    max_resultados: int,
    *,
    bloques_app: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if max_resultados <= 0:
        return []
    if len(resultados) <= max_resultados:
        return resultados
    ids_por_bloque = _ids_por_bloque_cards(bloques_app or [])
    if ids_por_bloque:
        return _seleccionar_resultados_por_bloques(
            resultados,
            max_resultados,
            ids_por_bloque,
        )
    return resultados[:max_resultados]


def _ids_por_bloque_cards(mensajes_app: list[dict[str, Any]]) -> list[list[int]]:
    bloques: list[list[int]] = []
    bloque_actual: list[int] = []

    for mensaje_app in mensajes_app:
        if not isinstance(mensaje_app, dict):
            continue
        if mensaje_app.get("tipo") == "card":
            mensaje = mensaje_app.get("mensaje") or {}
            try:
                id_sitio = int(mensaje.get("id_sitio"))
            except (TypeError, ValueError, AttributeError):
                continue
            bloque_actual.append(id_sitio)
            continue
        if mensaje_app.get("tipo") == "ids_asociados" and bloque_actual:
            bloques.append(_deduplicar(bloque_actual))
            bloque_actual = []

    if bloque_actual:
        bloques.append(_deduplicar(bloque_actual))

    return [bloque for bloque in bloques if bloque]


def _seleccionar_resultados_por_bloques(
    resultados: list[dict[str, Any]],
    max_resultados: int,
    ids_por_bloque: list[list[int]],
) -> list[dict[str, Any]]:
    por_id = {
        int(resultado["id_sitio"]): resultado
        for resultado in resultados
        if isinstance(resultado.get("id_sitio"), int)
    }
    ids_validos = set(por_id)
    seleccionados: list[int] = []

    bloques_validos = [
        [id_sitio for id_sitio in bloque if id_sitio in ids_validos]
        for bloque in ids_por_bloque
    ]
    bloques_validos = [bloque for bloque in bloques_validos if bloque]

    for bloque in bloques_validos:
        if len(seleccionados) >= max_resultados:
            break
        candidatos = [id_sitio for id_sitio in bloque if id_sitio not in seleccionados]
        if candidatos:
            seleccionados.append(candidatos[0])

    restantes = [
        int(resultado["id_sitio"])
        for resultado in resultados
        if int(resultado["id_sitio"]) not in seleccionados
    ]
    faltantes = max_resultados - len(seleccionados)
    if faltantes > 0:
        seleccionados.extend(restantes[:faltantes])

    return [por_id[id_sitio] for id_sitio in seleccionados if id_sitio in por_id]


def _ids_desde_resultados(resultados: list[dict[str, Any]]) -> list[int]:
    ids: list[int] = []
    for resultado in resultados:
        try:
            ids.append(int(resultado.get("id_sitio", resultado.get("id"))))
        except (TypeError, ValueError):
            continue
    return _deduplicar(ids)


def _ids_desde_cards(cards: list[dict[str, Any]]) -> list[int]:
    ids: list[int] = []
    for card in cards:
        mensaje = card.get("mensaje") if isinstance(card, dict) else {}
        if not isinstance(mensaje, dict):
            continue
        try:
            ids.append(int(mensaje.get("id_sitio")))
        except (TypeError, ValueError):
            continue
    return _deduplicar(ids)


def _filtrar_cards_por_ids(
    cards: list[dict[str, Any]],
    ids_permitidos: list[int],
) -> list[dict[str, Any]]:
    permitidos = set(_deduplicar(ids_permitidos))
    if not permitidos:
        return []

    filtradas: list[dict[str, Any]] = []
    for card in cards:
        mensaje = card.get("mensaje") if isinstance(card, dict) else {}
        if not isinstance(mensaje, dict):
            continue
        try:
            id_sitio = int(mensaje.get("id_sitio"))
        except (TypeError, ValueError):
            continue
        if id_sitio in permitidos:
            filtradas.append(card)
    return filtradas


def _ids_sin_card(ids: list[int], cards: list[dict[str, Any]]) -> list[int]:
    ids_cards = set()
    for card in cards:
        mensaje = card.get("mensaje") if isinstance(card, dict) else {}
        try:
            ids_cards.add(int(mensaje.get("id_sitio")))
        except (TypeError, ValueError, AttributeError):
            continue
    return [id_sitio for id_sitio in _deduplicar(ids) if id_sitio not in ids_cards]


def _ids_cards_visibles_ordenados(
    cards: list[dict[str, Any]],
    ids_asociados: list[int],
    max_cards: int = MAX_CARDS_VISIBLES,
) -> list[int]:
    ids_con_card: set[int] = set()
    for card in cards:
        mensaje = card.get("mensaje") if isinstance(card, dict) else {}
        if not isinstance(mensaje, dict):
            continue
        try:
            ids_con_card.add(int(mensaje.get("id_sitio")))
        except (TypeError, ValueError):
            continue

    visibles: list[int] = []
    for id_sitio in _deduplicar(ids_asociados):
        if id_sitio in ids_con_card:
            visibles.append(id_sitio)
        if len(visibles) >= max_cards:
            break
    return visibles


def _anexar_bloque_ids_asociados(
    mensajes_app: list[dict[str, Any]],
    ids_asociados: list[int],
) -> list[dict[str, Any]]:
    sin_bloques_ids = [
        mensaje
        for mensaje in mensajes_app
        if not (isinstance(mensaje, dict) and mensaje.get("tipo") == "ids_asociados")
    ]
    if not ids_asociados:
        return sin_bloques_ids
    return [
        *sin_bloques_ids,
        {
            "tipo": "ids_asociados",
            "mensaje": {"ids_asociados": _deduplicar(ids_asociados)},
        },
    ]


def _resultados_visibles_por_ids(
    resultados: list[dict[str, Any]],
    ids_visibles: list[int],
) -> list[dict[str, Any]]:
    por_id = {
        int(resultado["id_sitio"]): resultado
        for resultado in resultados
        if isinstance(resultado.get("id_sitio"), int)
    }
    return [por_id[id_sitio] for id_sitio in ids_visibles if id_sitio in por_id]


def _filtrar_bloques_por_ids(
    mensajes_app: list[dict[str, Any]],
    ids_permitidos: list[int],
    ids_cards_visibles: list[int] | None = None,
) -> list[dict[str, Any]]:
    permitidos = set(_deduplicar(ids_permitidos))
    if not permitidos:
        return []
    visibles = set(_deduplicar(ids_cards_visibles or ids_permitidos))

    salida: list[dict[str, Any]] = []
    for mensaje_app in mensajes_app:
        if not isinstance(mensaje_app, dict):
            continue

        if mensaje_app.get("tipo") == "card":
            mensaje = mensaje_app.get("mensaje") or {}
            try:
                id_sitio = int(mensaje.get("id_sitio"))
            except (TypeError, ValueError, AttributeError):
                continue
            if id_sitio in visibles:
                salida.append(mensaje_app)
            continue

        if mensaje_app.get("tipo") == "ids_asociados":
            ids_originales = mensaje_app.get("mensaje", {}).get("ids_asociados", [])
            ids = [id_sitio for id_sitio in _deduplicar(ids_originales) if id_sitio in permitidos]
            if ids:
                salida.append({"tipo": "ids_asociados", "mensaje": {"ids_asociados": ids}})
            continue

        salida.append(mensaje_app)

    return salida


def _limitar_cards_visibles(
    mensajes_app: list[dict[str, Any]],
    max_cards: int,
) -> list[dict[str, Any]]:
    if max_cards <= 0:
        return [
            mensaje
            for mensaje in mensajes_app
            if not isinstance(mensaje, dict) or mensaje.get("tipo") != "card"
        ]

    indices_cards = [
        indice
        for indice, mensaje in enumerate(mensajes_app)
        if isinstance(mensaje, dict) and mensaje.get("tipo") == "card"
    ]
    if len(indices_cards) <= max_cards:
        return mensajes_app

    indices_visibles = set(indices_cards[:max_cards])
    return [
        mensaje
        for indice, mensaje in enumerate(mensajes_app)
        if not isinstance(mensaje, dict)
        or mensaje.get("tipo") != "card"
        or indice in indices_visibles
    ]


def _extraer_nombres_cards(cards: list[dict[str, Any]]) -> list[str]:
    nombres: list[str] = []
    for card in cards:
        mensaje = card.get("mensaje") if isinstance(card, dict) else {}
        if isinstance(mensaje, dict):
            nombres.append(_primer_texto(mensaje.get("nombre_sitio")))
    return _deduplicar_texto(nombres)


def _limpiar_texto_redactor(texto: str) -> str:
    texto_limpio = str(texto or "").strip()
    patrones_prohibidos = [
        r"\s*si necesitas más detalles sobre alguno,?\s*¡?av[ií]same!?\s*$",
        r"\s*si quieres saber más sobre alguno,?\s*¡?av[ií]same!?\s*$",
        r"\s*si deseas más información sobre alguno,?\s*¡?av[ií]same!?\s*$",
        r"\s*si necesitas más detalles,?\s*¡?av[ií]same!?\s*$",
        r"\s*¡?av[ií]same si (quieres|necesitas).*$",
    ]
    for patron in patrones_prohibidos:
        texto_limpio = re.sub(
            patron,
            "",
            texto_limpio,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
    return texto_limpio


def _globo_deterministico(
    estados: list[ResultadoHerramienta],
    cards: list[dict[str, Any]],
    ids_asociados: list[int],
    ids_ruta: list[int],
    *,
    modo_respuesta: str = "exacto",
    motivo: str = "",
) -> str:
    if cards:
        total = min(len(cards), len(ids_asociados) or len(cards))
        extra = _resumen_distancia_globo(estados, ids_asociados)
        if modo_respuesta == "fallback_probable":
            prefijo = motivo or (
                "No encontré una opción exacta para lo que pediste, pero te recomiendo "
                "esta alternativa para que sigas explorando."
            )
            return f"{prefijo} Abajo te dejo las opciones disponibles.{extra}"
        if _solo_candidatos_aproximados(estados):
            return (
                "No encontré una coincidencia clara para lo que pediste, pero estas "
                f"{total} alternativa{'s' if total != 1 else ''} podrían servirte como referencia.{extra}"
            )
        return (
            f"Te muestro {total} opción{'es' if total != 1 else ''} que puede servirte "
            f"según la evidencia disponible.{extra}"
        )
    if ids_ruta:
        total = len(_deduplicar(ids_ruta))
        return (
            f"Encontré {total} ruta{'s' if total != 1 else ''} relacionada con tu búsqueda."
        )

    notas = [estado["nota"] for estado in estados if estado.get("nota")]
    if notas:
        return notas[-1]
    return "No encontré resultados claros, pero puedo ayudarte si me das un poco más de detalle."


def _resumen_distancia_globo(
    estados: list[ResultadoHerramienta],
    ids_asociados: list[int],
) -> str:
    distancias = _distancias_sitios_por_id(estados)
    ids = _deduplicar(ids_asociados)
    disponibles = [distancias[id_sitio] for id_sitio in ids if id_sitio in distancias]
    if not disponibles:
        return ""

    def ordenar(item: dict[str, Any]) -> float:
        try:
            return float(item.get("distancia_metros"))
        except (TypeError, ValueError):
            return float("inf")

    mas_cercana = min(disponibles, key=ordenar)
    distancia = _primer_texto(mas_cercana.get("distancia_aproximada"))
    nombre = _primer_texto(mas_cercana.get("nombre"))
    if not distancia:
        return ""
    if nombre:
        return f" La opción más cercana es {nombre}, a {distancia}."
    return f" La opción más cercana está a {distancia}."


def _solo_candidatos_aproximados(estados: list[ResultadoHerramienta]) -> bool:
    encontro_semantica = False
    for estado in estados:
        if estado.get("herramienta") != "busqueda_semantica":
            continue
        payload = estado.get("payload") or {}
        candidatos = payload.get("candidatos")
        if not isinstance(candidatos, list):
            continue
        encontro_semantica = True
        for candidato in candidatos:
            if isinstance(candidato, dict) and candidato.get("supera_umbral") is True:
                return False
    return encontro_semantica


def _construir_contexto_redaccion(
    estados: list[ResultadoHerramienta],
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    estados_api: list[dict[str, Any]] = []
    for estado in estados:
        payload = estado.get("payload") or {}
        retroalimentacion = payload.get("retroalimentacion")
        item: dict[str, Any] = {
            "herramienta": estado.get("herramienta"),
            "orden": estado.get("orden"),
            "status": estado.get("status"),
            "ids": estado.get("ids", []),
            "nota": estado.get("nota", ""),
        }
        estado_busqueda = estado.get("estado_busqueda")
        if isinstance(estado_busqueda, dict):
            item["estado_busqueda"] = _recortar_estado_busqueda(estado_busqueda)
        if isinstance(retroalimentacion, dict):
            item["retroalimentacion"] = {
                "codigo": retroalimentacion.get("codigo"),
                "mensaje": retroalimentacion.get("mensaje"),
                "fallback_global_aplicado": retroalimentacion.get("fallback_global_aplicado"),
                "radio_aplicado_metros": retroalimentacion.get("radio_aplicado_metros"),
                "radios_intentados_metros": retroalimentacion.get("radios_intentados_metros"),
            }
        if estado.get("herramienta") in {"gis", "gis_consulta", "busqueda_ubicacion", "busqueda_ubicacion_consulta"}:
            item["candidatos_con_distancia"] = _candidatos_gis_redaccion(payload)
        if estado.get("herramienta") == "busqueda_semantica":
            item["candidatos_semanticos"] = _candidatos_semanticos_redaccion(payload)
        estados_api.append(item)

    return {
        "estados_api": estados_api,
        "distancias_gis": _distancias_gis_redaccion(estados),
    }


def _candidatos_gis_redaccion(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidatos = payload.get("candidatos")
    if not isinstance(candidatos, list):
        return []
    salida: list[dict[str, Any]] = []
    for candidato in candidatos[:5]:
        if not isinstance(candidato, dict):
            continue
        salida.append(
            {
                "id_sitio": candidato.get("id_sitio"),
                "id_ruta": candidato.get("id_ruta"),
                "nombre": candidato.get("nombre") or candidato.get("titulo"),
                "distancia_metros": candidato.get("distancia_metros"),
                "distancia_aproximada": candidato.get("distancia_aproximada")
                or _formatear_distancia(candidato.get("distancia_metros")),
            }
        )
    return salida


def _candidatos_semanticos_redaccion(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidatos = payload.get("candidatos")
    if not isinstance(candidatos, list):
        return []
    salida: list[dict[str, Any]] = []
    for candidato in candidatos[:5]:
        if not isinstance(candidato, dict):
            continue
        salida.append(
            {
                "id_sitio": candidato.get("id_sitio"),
                "nombre": candidato.get("nombre"),
                "keywords_match": candidato.get("keywords_match"),
                "contenido_chunk": _recortar_texto(
                    candidato.get("contenido_chunk"),
                    max_chars=500,
                ),
            }
        )
    return salida


def _distancias_gis_redaccion(estados: list[ResultadoHerramienta]) -> list[dict[str, Any]]:
    salida: list[dict[str, Any]] = []
    for distancia in _distancias_sitios_por_id(estados).values():
        salida.append(distancia)
    return salida


def _distancia_mas_cercana_estados(estados: list[ResultadoHerramienta]) -> str:
    distancias = _distancias_gis_redaccion(estados)
    if not distancias:
        return ""

    def ordenar(item: dict[str, Any]) -> float:
        try:
            return float(item.get("distancia_metros"))
        except (TypeError, ValueError):
            return float("inf")

    mas_cercana = min(distancias, key=ordenar)
    return _primer_texto(mas_cercana.get("distancia_aproximada"))


def _extraer_mensajes_opciones(estados: list[ResultadoHerramienta]) -> list[dict[str, Any]]:
    mensajes: list[dict[str, Any]] = []
    for estado in estados:
        payload = estado.get("payload") or {}
        mensaje_app = payload.get("mensaje_app")
        if estado["herramienta"] in {"conversacional", "fallback"} and isinstance(
            mensaje_app, dict
        ):
            mensajes.append(mensaje_app)
        opciones = payload.get("opciones")
        if isinstance(opciones, list) and opciones:
            mensajes.append({"tipo": "opciones", "mensaje": {"opciones": opciones}})
    return mensajes


def _extraer_entidades_resueltas(
    estados: list[ResultadoHerramienta],
    cards: list[dict[str, Any]],
) -> list[str]:
    entidades: list[str] = []
    for card in cards:
        mensaje = card.get("mensaje") if isinstance(card, dict) else {}
        if isinstance(mensaje, dict):
            entidades.append(str(mensaje.get("nombre_sitio") or "").strip())

    for estado in estados:
        if estado.get("status") != "ok":
            continue
        payload = estado.get("payload") or {}
        candidatos = payload.get("candidatos")
        if isinstance(candidatos, list):
            for candidato in candidatos:
                if isinstance(candidato, dict):
                    entidades.append(str(candidato.get("nombre") or "").strip())

    return _deduplicar_texto(entidades)


def _construir_state_final(
    state: dict[str, Any],
    *,
    estados: list[ResultadoHerramienta],
    ids_asociados: list[int],
    mensajes_app: list[dict[str, Any]],
    entidades_resueltas: list[str],
    mensaje_sistema: str | None,
    mensaje_app: dict[str, Any] | None,
    diagnostico_redactor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resultado_previo = state.get("resultado_exploracion")
    resultado = dict(resultado_previo) if isinstance(resultado_previo, dict) else {}
    resultado.update(
        {
            "plan_valido": bool(state.get("plan_valido")),
            "plan": state.get("plan"),
            "errores_formato": state.get("errores_formato", []),
            "estados_herramientas": estados,
            "ids_asociados": ids_asociados,
            "mensajes_app": mensajes_app,
        }
    )
    if diagnostico_redactor is not None:
        resultado["diagnostico_redactor"] = diagnostico_redactor

    salida = {
        **state,
        "estados_herramientas": estados,
        "ids_asociados": ids_asociados,
        "mensajes_app": mensajes_app,
        "entidades_resueltas": entidades_resueltas,
        "mensaje_sistema": mensaje_sistema,
        "mensaje_app": mensaje_app,
        "resultado_exploracion": resultado,
    }
    if diagnostico_redactor is not None:
        salida["diagnostico_redactor"] = diagnostico_redactor
    return salida


def _mensajes_existentes(state: dict[str, Any]) -> list[dict[str, Any]]:
    mensaje_app = state.get("mensaje_app")
    return [mensaje_app] if isinstance(mensaje_app, dict) else []


def _deduplicar(ids: list[int]) -> list[int]:
    salida: list[int] = []
    vistos: set[int] = set()
    for item in normalizar_ids(ids):
        if item in vistos:
            continue
        vistos.add(item)
        salida.append(item)
    return salida


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
