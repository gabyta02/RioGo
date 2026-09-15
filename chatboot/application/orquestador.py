from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from copy import deepcopy
from threading import Thread
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from application.nodes.chatboot_exploracion.flow import ejecutar_exploracion_flow
from application.nodes.chatboot_exploracion.herramientas.historial_exploracion import (
    guardar_historial_exploracion,
)
from application.nodes.chatboot_especifico.utilidades.crear_plan_pregunta import (
    crear_plan_pregunta_directa,
)
from application.nodes.chatboot_especifico.utilidades.ejecutar_plan_pregunta import (
    ejecutar_plan_pregunta,
)
from application.nodes.chatboot_especifico.herramientas.historial_pregunta_directa import (
    guardar_historial_pregunta_directa,
)
from application.nodes.chatboot_especifico.utilidades.cargar_memoria import (
    cargar_memoria_pregunta,
)
from application.nodes.chatboot_especifico.utilidades.guardar_memoria import (
    guardar_memoria_pregunta,
)
from application.shared.flow import ejecutar_shared_flow
from application.shared.promp_inyection import RIESGO_PROMPT_INYECTION_VACIO
from application.state import SharedFlowState

logger = logging.getLogger(__name__)


class MensajeBaseWebsocket(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mensaje_usuario: str
    client_message_id: str
    id_usuario: int | None = None
    sesion_id: str | None = Field(default=None, alias="sesion_Id")
    ubicacion_usuario: dict[str, Any]

    @model_validator(mode="after")
    def asegurar_sesion_id(self) -> "MensajeBaseWebsocket":
        self.client_message_id = self.client_message_id.strip()
        self.mensaje_usuario = self.mensaje_usuario.strip()
        if not self.client_message_id:
            raise ValueError("client_message_id es obligatorio.")
        if not self.mensaje_usuario:
            raise ValueError("mensaje_usuario es obligatorio.")
        if not self.sesion_id:
            self.sesion_id = str(uuid4())
        return self


class MensajePreguntaDirectaWebsocket(MensajeBaseWebsocket):
    id_sitio: int
    nombre_sitio: str

    @model_validator(mode="after")
    def validar_contexto_sitio(self) -> "MensajePreguntaDirectaWebsocket":
        self.nombre_sitio = self.nombre_sitio.strip()
        if not self.nombre_sitio:
            raise ValueError("nombre_sitio es obligatorio para pregunta_directa.")
        if self.id_sitio <= 0:
            raise ValueError("id_sitio debe ser un entero positivo.")
        return self


class PeticionWebsocket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pregunta_chatboot: Literal["pregunta_directa", "exploracion"]
    mensaje: dict[str, Any]


def validar_peticion_websocket(payload: dict[str, Any]) -> dict[str, Any]:
    peticion = PeticionWebsocket.model_validate(payload)
    mensaje_modelo: MensajeBaseWebsocket
    if peticion.pregunta_chatboot == "pregunta_directa":
        mensaje_modelo = MensajePreguntaDirectaWebsocket.model_validate(
            peticion.mensaje
        )
    else:
        mensaje_modelo = MensajeBaseWebsocket.model_validate(peticion.mensaje)

    return {
        "pregunta_chatboot": peticion.pregunta_chatboot,
        "mensaje": mensaje_modelo.model_dump(mode="json"),
    }


def _construir_estado_inicial(paquete_validado: dict[str, Any]) -> SharedFlowState:
    mensaje = dict(paquete_validado["mensaje"])
    return {
        "pregunta_chatboot": paquete_validado["pregunta_chatboot"],
        "client_message_id": mensaje["client_message_id"],
        "sesion_id": mensaje["sesion_id"],
        "id_usuario": mensaje.get("id_usuario"),
        "ubicacion_usuario": dict(mensaje["ubicacion_usuario"]),
        "id_sitio": mensaje.get("id_sitio"),
        "nombre_sitio": mensaje.get("nombre_sitio"),
        "mensaje_original": mensaje["mensaje_usuario"],
        "mensaje_limpio": "",
        "riesgo_prompt_inyection": deepcopy(RIESGO_PROMPT_INYECTION_VACIO),
        "palabras_inyectadas": [],
        "bloqueado": False,
        "motivo_bloqueo": None,
        "mensaje_sistema": None,
        "origen_mensaje_sistema": None,
        "clasificacion_final": None,
    }


def procesar_peticion_websocket(payload: dict[str, Any]) -> dict[str, Any]:
    inicio_total = time.perf_counter()
    paquete_validado = validar_peticion_websocket(payload)
    inicio_shared = time.perf_counter()
    estado_shared = ejecutar_shared_flow(_construir_estado_inicial(paquete_validado))
    _log_tiempo_etapa(paquete_validado, "shared_flow", inicio_shared)
    clasificacion_final = estado_shared.get("clasificacion_final")
    if not clasificacion_final:
        raise RuntimeError("El flujo shared no generó clasificacion_final.")
    if paquete_validado["pregunta_chatboot"] == "pregunta_directa":
        if estado_shared.get("bloqueado"):
            return clasificacion_final
        resultado = _clasificar_pregunta_directa_final(clasificacion_final)
        _log_tiempo_etapa(paquete_validado, "total", inicio_total)
        return resultado

    if estado_shared.get("bloqueado"):
        return clasificacion_final

    inicio_exploracion = time.perf_counter()
    estado_exploracion = ejecutar_exploracion_flow(
        {
            "sesion_id": clasificacion_final["sesion_id"],
            "client_message_id": clasificacion_final["client_message_id"],
            "ubicacion_usuario": clasificacion_final["ubicacion_usuario"],
            "texto_usuario": clasificacion_final["mensaje"]["texto_limpio"],
            "score_prompt_inyection": clasificacion_final["mensaje"][
                "riesgo_prompt_inyection"
            ]["score"],
            "palabras_inyectadas": [
                dict(item)
                for item in clasificacion_final["mensaje"]["palabras_inyectadas"]
                if item.get("palabra") and item.get("significado")
            ],
            "contexto_temporal": clasificacion_final["mensaje"].get(
                "contexto_temporal", {}
            ),
            "memoria": {"turnos": []},
            "prompt_clasificacion": "",
            "respuesta_llm_cruda": "",
            "plan": None,
            "plan_valido": False,
            "errores_formato": [],
            "mensaje_sistema": None,
            "mensaje_app": None,
            "resultado_exploracion": None,
        }
    )
    _log_tiempo_etapa(paquete_validado, "exploracion_flow", inicio_exploracion)

    resultado_exploracion = estado_exploracion.get("resultado_exploracion") or {
        "plan_valido": False,
        "plan": None,
        "errores_formato": [],
    }
    clasificacion_final["exploracion"] = resultado_exploracion

    if estado_exploracion.get("mensaje_sistema"):
        clasificacion_final["mensaje_sistema"] = str(
            estado_exploracion["mensaje_sistema"]
        )
    if estado_exploracion.get("mensaje_app"):
        clasificacion_final["mensaje_app"] = estado_exploracion["mensaje_app"]

    _guardar_historial_exploracion_final(
        clasificacion_final=clasificacion_final,
        estado_exploracion=estado_exploracion,
    )

    _log_tiempo_etapa(paquete_validado, "total", inicio_total)
    return clasificacion_final


async def procesar_peticion_websocket_async(
    payload: dict[str, Any],
    *,
    stream_callback: Any | None = None,
) -> dict[str, Any]:
    inicio_total = time.perf_counter()
    paquete_validado = validar_peticion_websocket(payload)
    if paquete_validado["pregunta_chatboot"] != "pregunta_directa":
        resultado = await asyncio.to_thread(procesar_peticion_websocket, payload)
        _log_tiempo_etapa(paquete_validado, "total_async_wrapper", inicio_total)
        return resultado

    inicio_shared = time.perf_counter()
    estado_shared = await asyncio.to_thread(
        ejecutar_shared_flow,
        _construir_estado_inicial(paquete_validado),
    )
    _log_tiempo_etapa(paquete_validado, "shared_flow", inicio_shared)
    clasificacion_final = estado_shared.get("clasificacion_final")
    if not clasificacion_final:
        raise RuntimeError("El flujo shared no generó clasificacion_final.")
    if estado_shared.get("bloqueado"):
        return clasificacion_final

    inicio_pregunta = time.perf_counter()
    resultado = await _clasificar_pregunta_directa_final_async(
        clasificacion_final,
        stream_callback=stream_callback,
    )
    _log_tiempo_etapa(paquete_validado, "pregunta_directa_flow", inicio_pregunta)
    _log_tiempo_etapa(paquete_validado, "total", inicio_total)
    return resultado


def _clasificar_pregunta_directa_final(
    clasificacion_final: dict[str, Any],
) -> dict[str, Any]:
    estado_pregunta = _ejecutar_corutina_sincrona(
        _clasificar_pregunta_directa_estado_async(clasificacion_final)
    )
    return _aplicar_estado_pregunta(clasificacion_final, estado_pregunta)


async def _clasificar_pregunta_directa_final_async(
    clasificacion_final: dict[str, Any],
    *,
    stream_callback: Any | None = None,
) -> dict[str, Any]:
    estado_pregunta = await _clasificar_pregunta_directa_estado_async(
        clasificacion_final,
        stream_callback=stream_callback,
    )
    return _aplicar_estado_pregunta(clasificacion_final, estado_pregunta)


async def _clasificar_pregunta_directa_estado_async(
    clasificacion_final: dict[str, Any],
    *,
    stream_callback: Any | None = None,
) -> dict[str, Any]:
    inicio_memoria = time.perf_counter()
    estado_base = cargar_memoria_pregunta(_construir_estado_pregunta(clasificacion_final))
    _log_tiempo_clasificacion(clasificacion_final, "cargar_memoria", inicio_memoria)
    inicio_plan = time.perf_counter()
    estado_pregunta = await crear_plan_pregunta_directa(estado_base)
    _log_tiempo_clasificacion(clasificacion_final, "llm_plan_pregunta", inicio_plan)
    if stream_callback is not None:
        estado_pregunta["stream_callback"] = stream_callback
    inicio_herramientas = time.perf_counter()
    estado_pregunta = await ejecutar_plan_pregunta(estado_pregunta)
    _log_tiempo_clasificacion(
        clasificacion_final,
        "herramientas_y_redactor_pregunta",
        inicio_herramientas,
    )
    inicio_guardar_memoria = time.perf_counter()
    estado_pregunta = guardar_memoria_pregunta(estado_pregunta)
    _log_tiempo_clasificacion(
        clasificacion_final,
        "guardar_memoria",
        inicio_guardar_memoria,
    )
    return estado_pregunta


def _construir_estado_pregunta(clasificacion_final: dict[str, Any]) -> dict[str, Any]:
    return {
        "sesion_id": clasificacion_final["sesion_id"],
        "client_message_id": clasificacion_final["client_message_id"],
        "ubicacion_usuario": clasificacion_final["ubicacion_usuario"],
        "id_usuario": clasificacion_final.get("id_usuario"),
        "id_sitio": clasificacion_final.get("id_sitio"),
        "nombre_sitio": clasificacion_final.get("nombre_sitio"),
        "texto_usuario": clasificacion_final["mensaje"]["texto_limpio"],
        "score_prompt_inyection": clasificacion_final["mensaje"][
            "riesgo_prompt_inyection"
        ]["score"],
        "palabras_inyectadas": [
            f"{item['palabra']}:{item['significado']}"
            for item in clasificacion_final["mensaje"]["palabras_inyectadas"]
            if item.get("palabra") and item.get("significado")
        ],
        "contexto_temporal": clasificacion_final["mensaje"].get(
            "contexto_temporal", {}
        ),
        "memoria": {"turnos": []},
        "prompt_clasificacion": "",
        "respuesta_llm_cruda": "",
        "plan": None,
        "plan_valido": False,
        "errores_formato": [],
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_pregunta_directa": None,
    }


def _aplicar_estado_pregunta(
    clasificacion_final: dict[str, Any],
    estado_pregunta: dict[str, Any],
) -> dict[str, Any]:
    resultado_pregunta = estado_pregunta.get("resultado_pregunta_directa") or {
        "plan_valido": False,
        "plan": None,
        "errores_formato": [],
    }
    clasificacion_final["pregunta_directa"] = resultado_pregunta

    if estado_pregunta.get("mensaje_sistema"):
        clasificacion_final["mensaje_sistema"] = str(
            estado_pregunta["mensaje_sistema"]
        )
    if estado_pregunta.get("mensaje_app"):
        clasificacion_final["mensaje_app"] = estado_pregunta["mensaje_app"]

    _guardar_historial_pregunta_directa_final(
        clasificacion_final=clasificacion_final,
        estado_pregunta=estado_pregunta,
    )

    return clasificacion_final


def _guardar_historial_pregunta_directa_final(
    *,
    clasificacion_final: dict[str, Any],
    estado_pregunta: dict[str, Any],
) -> None:
    id_usuario = clasificacion_final.get("id_usuario")
    if id_usuario is None:
        logger.info(
            "No se guardó historial de pregunta directa: falta id_usuario para client_message_id=%s",
            clasificacion_final.get("client_message_id"),
        )
        return

    payload = {
        "id_usuario": id_usuario,
        "sesion_id": clasificacion_final.get("sesion_id") or "",
        "client_message_id": clasificacion_final.get("client_message_id") or "",
        "texto_usuario": (clasificacion_final.get("mensaje") or {}).get(
            "texto_limpio"
        )
        or (clasificacion_final.get("mensaje") or {}).get("mensaje_usuario")
        or "",
        "respuesta_json": deepcopy(clasificacion_final),
        "entidad_asociada": clasificacion_final.get("nombre_sitio") or "",
    }

    try:
        _ejecutar_corutina_sincrona(guardar_historial_pregunta_directa(payload))
    except Exception as exc:
        logger.warning(
            "No se pudo guardar historial de pregunta directa para client_message_id=%s: %s",
            payload["client_message_id"],
            exc,
        )


def _guardar_historial_exploracion_final(
    *,
    clasificacion_final: dict[str, Any],
    estado_exploracion: dict[str, Any],
) -> None:
    id_usuario = clasificacion_final.get("id_usuario")
    if id_usuario is None:
        logger.info(
            "No se guardó historial de exploración: falta id_usuario para client_message_id=%s",
            clasificacion_final.get("client_message_id"),
        )
        return

    payload = {
        "id_usuario": id_usuario,
        "sesion_id": clasificacion_final.get("sesion_id") or "",
        "client_message_id": clasificacion_final.get("client_message_id") or "",
        "texto_usuario": (clasificacion_final.get("mensaje") or {}).get(
            "texto_limpio"
        )
        or (clasificacion_final.get("mensaje") or {}).get("mensaje_usuario")
        or "",
        "respuesta_json": deepcopy(clasificacion_final),
        **_extraer_catalogo_respuesta_exploracion(
            clasificacion_final.get("exploracion")
        ),
    }

    try:
        _ejecutar_corutina_sincrona(guardar_historial_exploracion(payload))
    except Exception as exc:
        logger.warning(
            "No se pudo guardar historial de exploración para client_message_id=%s: %s",
            payload["client_message_id"],
            exc,
        )


def _extraer_catalogo_respuesta_exploracion(
    exploracion: Any,
) -> dict[str, list[str] | None]:
    categorias: list[str] = []
    subcategorias: list[str] = []
    vistos_categorias: set[str] = set()
    vistos_subcategorias: set[str] = set()

    def agregar(valor: Any, *, destino: list[str], vistos: set[str]) -> None:
        items = valor if isinstance(valor, list) else [valor]
        for item in items:
            texto = str(item or "").strip()
            if not texto:
                continue
            clave = texto.casefold()
            if clave in vistos:
                continue
            vistos.add(clave)
            destino.append(texto)

    mensajes_app = (
        exploracion.get("mensajes_app")
        if isinstance(exploracion, dict)
        else None
    )
    if isinstance(mensajes_app, list):
        for mensaje_app in mensajes_app:
            if not isinstance(mensaje_app, dict) or mensaje_app.get("tipo") != "card":
                continue
            mensaje = mensaje_app.get("mensaje")
            if not isinstance(mensaje, dict):
                continue
            agregar(
                mensaje.get("categoria"),
                destino=categorias,
                vistos=vistos_categorias,
            )
            agregar(
                mensaje.get("subcategoria"),
                destino=subcategorias,
                vistos=vistos_subcategorias,
            )

    return {
        "categorias": categorias or None,
        "subcategorias": subcategorias or None,
    }


def _extraer_catalogo_plan(plan: Any) -> dict[str, list[str] | None]:
    return {"categorias": None, "subcategorias": None}


def _log_tiempo_etapa(
    paquete_validado: dict[str, Any],
    etapa: str,
    inicio: float,
) -> None:
    mensaje = paquete_validado.get("mensaje") or {}
    logger.warning(
        "chatboot_timing pregunta_chatboot=%s etapa=%s client_message_id=%s sesion_id=%s duration_seconds=%.3f",
        paquete_validado.get("pregunta_chatboot"),
        etapa,
        mensaje.get("client_message_id"),
        mensaje.get("sesion_id"),
        time.perf_counter() - inicio,
    )


def _log_tiempo_clasificacion(
    clasificacion_final: dict[str, Any],
    etapa: str,
    inicio: float,
) -> None:
    logger.warning(
        "chatboot_timing pregunta_chatboot=%s etapa=%s client_message_id=%s sesion_id=%s duration_seconds=%.3f",
        clasificacion_final.get("pregunta_chatboot"),
        etapa,
        clasificacion_final.get("client_message_id"),
        clasificacion_final.get("sesion_id"),
        time.perf_counter() - inicio,
    )


def _ejecutar_corutina_sincrona(corutina: Coroutine[Any, Any, Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(corutina)

    resultado: dict[str, Any] = {}

    def runner() -> None:
        try:
            resultado["valor"] = asyncio.run(corutina)
        except Exception as exc:  # pragma: no cover - defensivo para event loops externos
            resultado["error"] = exc

    thread = Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in resultado:
        raise resultado["error"]
    return resultado.get("valor")


def construir_peticion_websocket(
    *,
    pregunta_chatboot: Literal["pregunta_directa", "exploracion"],
    mensaje_usuario: str,
    client_message_id: str,
    sesion_id: str | None,
    ubicacion_usuario: dict[str, Any],
    id_usuario: int | None = None,
    id_sitio: int | None = None,
    nombre_sitio: str | None = None,
) -> dict[str, Any]:
    mensaje: dict[str, Any] = {
        "mensaje_usuario": mensaje_usuario,
        "client_message_id": client_message_id,
        "id_usuario": id_usuario,
        "sesion_Id": sesion_id,
        "ubicacion_usuario": ubicacion_usuario,
    }
    if id_sitio is not None:
        mensaje["id_sitio"] = id_sitio
    if nombre_sitio is not None:
        mensaje["nombre_sitio"] = nombre_sitio

    return validar_peticion_websocket(
        {
            "pregunta_chatboot": pregunta_chatboot,
            "mensaje": mensaje,
        }
    )


MensajeBaseWebsocket.model_rebuild()
MensajePreguntaDirectaWebsocket.model_rebuild()
PeticionWebsocket.model_rebuild()
