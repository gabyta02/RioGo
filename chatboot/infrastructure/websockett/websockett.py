from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

websocket_router = APIRouter()
logger = logging.getLogger(__name__)
PROCESSING_TIMEOUT_SECONDS = float(os.getenv("CHATBOOT_MESSAGE_TIMEOUT_SECONDS", "55"))

CHATBOOT_ROOT = Path(__file__).resolve().parents[2]
ORQUESTADOR_PATHS = (
    CHATBOOT_ROOT / "application" / "orquestador.py",
)
CANAL_PUBLICO_A_PREGUNTA = {
    "exploracion": "exploracion",
    "pregunta_directa": "pregunta_directa",
}


@lru_cache(maxsize=1)
def _cargar_orquestador():
    orquestador_path = next((path for path in ORQUESTADOR_PATHS if path.exists()), None)
    if orquestador_path is None:
        raise RuntimeError("No se encontró application/orquestador.py")

    spec = importlib.util.spec_from_file_location(
        "chatboot_orquestador",
        orquestador_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar {orquestador_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _obtener_orquestador_funcion(nombre: str):
    module = _cargar_orquestador()
    funcion = getattr(module, nombre, None)
    if funcion is None:
        raise RuntimeError(f"No se encontró {nombre} en application/orquestador.py")
    return funcion


def _extraer_mensaje_usuario(
    raw: Any,
) -> tuple[str, str, str | None, int | None, dict[str, Any], int | None, str | None]:
    if isinstance(raw, dict):
        mensaje_usuario = str(
            raw.get("mensaje_usuario") or raw.get("mensaje") or ""
        ).strip()
        client_message_id = str(
            raw.get("client_message_id")
            or raw.get("client_menssaje_id")
            or raw.get("client_mensaje_id")
            or ""
        ).strip()
        sesion_id = raw.get("sesion_Id") or raw.get("sesion_id")
        id_usuario = raw.get("id_usuario")
        ubicacion_usuario = raw.get("ubicacion_usuario") or {}
        if not isinstance(ubicacion_usuario, dict):
            ubicacion_usuario = {"raw": ubicacion_usuario}
        nombre_sitio = raw.get("nombre_sitio")
        return (
            mensaje_usuario,
            client_message_id,
            str(sesion_id).strip() if sesion_id is not None else None,
            int(id_usuario)
            if id_usuario is not None and str(id_usuario).strip()
            else None,
            ubicacion_usuario,
            int(raw["id_sitio"]) if raw.get("id_sitio") is not None else None,
            str(nombre_sitio).strip() if nombre_sitio is not None else None,
        )

    return str(raw or "").strip(), "", None, None, {}, None, None


def _crear_paquete_websocket(
    *,
    canal_publico: Literal["exploracion", "pregunta_directa"],
    mensaje_usuario: str,
    client_message_id: str,
    sesion_id: str | None,
    ubicacion_usuario: dict[str, Any],
    id_usuario: int | None,
    id_sitio: int | None = None,
    nombre_sitio: str | None = None,
) -> dict[str, Any]:
    pregunta_chatboot = CANAL_PUBLICO_A_PREGUNTA[canal_publico]
    construir_peticion_websocket = _obtener_orquestador_funcion(
        "construir_peticion_websocket"
    )
    return construir_peticion_websocket(
        pregunta_chatboot=pregunta_chatboot,
        mensaje_usuario=mensaje_usuario,
        client_message_id=client_message_id,
        sesion_id=sesion_id,
        id_usuario=id_usuario,
        ubicacion_usuario=ubicacion_usuario,
        id_sitio=id_sitio if canal_publico == "pregunta_directa" else None,
        nombre_sitio=nombre_sitio if canal_publico == "pregunta_directa" else None,
    )


def _procesar_paquete_websocket(paquete: dict[str, Any]) -> dict[str, Any]:
    procesar_peticion_websocket = _obtener_orquestador_funcion(
        "procesar_peticion_websocket"
    )
    return procesar_peticion_websocket(paquete)


async def _procesar_paquete_websocket_async(
    paquete: dict[str, Any],
    *,
    stream_callback: Any | None = None,
) -> dict[str, Any]:
    procesar_peticion_websocket_async = _obtener_orquestador_funcion(
        "procesar_peticion_websocket_async"
    )
    return await procesar_peticion_websocket_async(
        paquete,
        stream_callback=stream_callback,
    )


def _cargar_pensamiento_fake():
    path = (
        CHATBOOT_ROOT
        / "application"
        / "nodes"
        / "chatboot_exploracion"
        / "herramientas"
        / "pensamiento_fake.py"
    )
    spec = importlib.util.spec_from_file_location("chatboot_pensamiento_fake", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _construir_guion_stream() -> list[dict[str, str]]:
    try:
        module = _cargar_pensamiento_fake()
        guion = module.construir_guion(None)
    except Exception:
        guion = [
            {
                "fase": "entendiendo_consulta",
                "texto": "Estoy entendiendo tu consulta y separando lo importante.",
            },
            {
                "fase": "analizando_intencion",
                "texto": "Estoy analizando qué tipo de búsqueda turística necesitas.",
            },
            {
                "fase": "preparando_respuesta",
                "texto": "Estoy preparando una respuesta clara con las mejores opciones.",
            },
        ]
    return guion


def _calentar_chatboot_sync(canal: str) -> dict[str, Any]:
    _cargar_orquestador()
    rutas = ["exploracion", "exploracion_plan"]
    if canal == "pregunta_directa":
        rutas.append("sitio")

    rutas_calentadas: list[str] = []
    try:
        from infrastructure.llms import get_llm_router

        router = get_llm_router()
        for ruta in rutas:
            router.get_route_settings(ruta)
            router.get_client_for_route(ruta)
            rutas_calentadas.append(ruta)
    except Exception as exc:
        logger.warning("Warmup LLM incompleto para canal %s: %s", canal, exc)
        return {"ok": False, "rutas": rutas_calentadas, "detalle": str(exc)}

    return {"ok": True, "rutas": rutas_calentadas}


async def _calentar_chatboot(canal: str) -> dict[str, Any]:
    return await asyncio.to_thread(_calentar_chatboot_sync, canal)


async def _emitir_pensamiento_fake(
    *,
    websocket: WebSocket,
    canal: str,
    client_message_id: str,
    stop_event: asyncio.Event,
    intervalo_segundos: float = 1.15,
) -> None:
    guion = _construir_guion_stream()
    total = len(guion)
    indice = 0
    while not stop_event.is_set():
        item = guion[indice % total]
        vuelta = indice // total
        indice_visible = (indice % total) + 1
        if stop_event.is_set():
            return
        enviado = await _send_json_si_conectado(
            websocket,
            {
                "tipo": "stream",
                "canal": canal,
                "client_message_id": client_message_id,
                "payload": {
                    "tipo": "stream",
                    "mensaje": {
                        "origen": "pensamiento_fake",
                        "fase": item["fase"],
                        "texto": item["texto"],
                        "indice": indice_visible,
                        "total": total,
                        "ciclo": vuelta + 1,
                    },
                },
            },
        )
        if not enviado:
            stop_event.set()
            return
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=intervalo_segundos)
            return
        except asyncio.TimeoutError:
            indice += 1
            continue


async def _send_json_si_conectado(websocket: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await websocket.send_json(payload)
    except (RuntimeError, WebSocketDisconnect):
        return False
    return True


async def _manejar_canal(websocket: WebSocket, canal: str) -> None:
    await websocket.accept()
    if not await _send_json_si_conectado(
        websocket,
        {
            "tipo": "conexion",
            "estado": "inicializando",
            "canal": canal,
            "pregunta_chatboot": CANAL_PUBLICO_A_PREGUNTA[canal],
        },
    ):
        return
    warmup = await _calentar_chatboot(canal)
    if not await _send_json_si_conectado(
        websocket,
        {
            "tipo": "conexion",
            "estado": "conectado",
            "canal": canal,
            "pregunta_chatboot": CANAL_PUBLICO_A_PREGUNTA[canal],
            "warmup": warmup,
        },
    ):
        return

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"mensaje": raw}

            (
                mensaje_usuario,
                client_message_id,
                sesion_id,
                id_usuario,
                ubicacion_usuario,
                id_sitio,
                nombre_sitio,
            ) = (
                _extraer_mensaje_usuario(payload)
            )
            try:
                paquete = _crear_paquete_websocket(
                    canal_publico=canal,  # type: ignore[arg-type]
                    mensaje_usuario=mensaje_usuario,
                    client_message_id=client_message_id,
                    sesion_id=sesion_id,
                    id_usuario=id_usuario,
                    ubicacion_usuario=ubicacion_usuario,
                    id_sitio=id_sitio,
                    nombre_sitio=nombre_sitio,
                )
                stop_event = asyncio.Event()
                stream_task = asyncio.create_task(
                    _emitir_pensamiento_fake(
                        websocket=websocket,
                        canal=canal,
                        client_message_id=client_message_id,
                        stop_event=stop_event,
                    )
                )

                async def enviar_stream_redactor(texto: str) -> None:
                    stop_event.set()
                    await _send_json_si_conectado(
                        websocket,
                        {
                            "tipo": "stream",
                            "canal": canal,
                            "client_message_id": client_message_id,
                            "payload": {
                                "tipo": "stream",
                                "mensaje": {
                                    "origen": "redactor_pregunta_directa",
                                    "fase": "redactando_respuesta",
                                    "texto": texto,
                                },
                            },
                        },
                    )

                try:
                    if canal == "pregunta_directa":
                        paquete_validado = await asyncio.wait_for(
                            _procesar_paquete_websocket_async(
                                paquete,
                                stream_callback=enviar_stream_redactor,
                            ),
                            timeout=PROCESSING_TIMEOUT_SECONDS,
                        )
                    else:
                        paquete_validado = await asyncio.wait_for(
                            asyncio.to_thread(
                                _procesar_paquete_websocket,
                                paquete,
                            ),
                            timeout=PROCESSING_TIMEOUT_SECONDS,
                        )
                finally:
                    stop_event.set()
                    await stream_task
            except asyncio.TimeoutError:
                enviado = await _send_json_si_conectado(
                    websocket,
                    {
                        "tipo": "error_validacion",
                        "canal": canal,
                        "client_message_id": client_message_id,
                        "sesion_id": sesion_id,
                        "mensaje": "La consulta tardó más de lo esperado. Intenta nuevamente.",
                        "detalle": f"timeout_procesamiento_{PROCESSING_TIMEOUT_SECONDS:.0f}s",
                    },
                )
                if not enviado:
                    return
                continue
            except Exception as exc:
                enviado = await _send_json_si_conectado(
                    websocket,
                    {
                        "tipo": "error_validacion",
                        "canal": canal,
                        "client_message_id": client_message_id,
                        "sesion_id": sesion_id,
                        "mensaje": "El mensaje no pudo procesarse con la estructura requerida.",
                        "detalle": str(exc),
                    },
                )
                if not enviado:
                    return
                continue
            enviado = await _send_json_si_conectado(
                websocket,
                {
                    "tipo": "clasificacion_final",
                    "canal": canal,
                    "payload": paquete_validado,
                },
            )
            if not enviado:
                return
    except WebSocketDisconnect:
        return


@websocket_router.websocket("/ws/exploracion")
async def websocket_exploracion(websocket: WebSocket) -> None:
    await _manejar_canal(websocket, "exploracion")


@websocket_router.websocket("/ws/pregunta_directa")
async def websocket_pregunta_directa(websocket: WebSocket) -> None:
    await _manejar_canal(websocket, "pregunta_directa")
