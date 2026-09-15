from __future__ import annotations

import asyncio

import pytest

from application import orquestador
from infrastructure.websockett.websockett import _emitir_pensamiento_fake


class WebSocketFake:
    def __init__(self, stop_event: asyncio.Event, limite: int = 3) -> None:
        self.stop_event = stop_event
        self.limite = limite
        self.mensajes: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.mensajes.append(payload)
        if len(self.mensajes) >= self.limite:
            self.stop_event.set()


def test_validacion_websocket_acepta_id_usuario():
    paquete = orquestador.construir_peticion_websocket(
        pregunta_chatboot="exploracion",
        mensaje_usuario="Quiero museos",
        client_message_id="msg-1",
        sesion_id="sesion-1",
        id_usuario=42,
        ubicacion_usuario={"lat": -1.67, "lng": -78.64},
    )

    assert paquete["mensaje"]["id_usuario"] == 42


@pytest.mark.asyncio
async def test_stream_fake_emite_varios_estados_hasta_stop():
    stop_event = asyncio.Event()
    websocket = WebSocketFake(stop_event, limite=3)

    await _emitir_pensamiento_fake(
        websocket=websocket,
        canal="exploracion",
        client_message_id="msg-stream",
        stop_event=stop_event,
        intervalo_segundos=0.001,
    )

    assert len(websocket.mensajes) == 3
    textos = [
        item["payload"]["mensaje"]["texto"]
        for item in websocket.mensajes
    ]
    assert len(set(textos)) == 3
    assert all(item["tipo"] == "stream" for item in websocket.mensajes)


def test_validacion_pregunta_directa_exige_nombre_sitio():
    paquete = orquestador.construir_peticion_websocket(
        pregunta_chatboot="pregunta_directa",
        mensaje_usuario="¿Cuál es el horario?",
        client_message_id="msg-sitio",
        sesion_id="sesion-sitio",
        id_usuario=42,
        ubicacion_usuario={"lat": -1.67, "lng": -78.64},
        id_sitio=68,
        nombre_sitio="Mercado de la Merced",
    )

    assert paquete["mensaje"]["id_sitio"] == 68
    assert paquete["mensaje"]["nombre_sitio"] == "Mercado de la Merced"

    with pytest.raises(Exception):
        orquestador.construir_peticion_websocket(
            pregunta_chatboot="pregunta_directa",
            mensaje_usuario="¿Cuál es el horario?",
            client_message_id="msg-sitio-2",
            sesion_id="sesion-sitio",
            id_usuario=42,
            ubicacion_usuario={"lat": -1.67, "lng": -78.64},
            id_sitio=68,
        )

    with pytest.raises(Exception):
        orquestador.construir_peticion_websocket(
            pregunta_chatboot="pregunta_directa",
            mensaje_usuario="¿Cuál es el horario?",
            client_message_id="msg-sitio-3",
            sesion_id="sesion-sitio",
            id_usuario=42,
            ubicacion_usuario={"lat": -1.67, "lng": -78.64},
            id_sitio=68,
            nombre_sitio=" ",
        )


def test_extrae_categorias_y_subcategorias_de_cards_finales():
    exploracion = {
        "mensajes_app": [
            {
                "tipo": "card",
                "mensaje": {
                    "categoria": "Alimentos y Bebidas",
                    "subcategoria": "Restaurante",
                },
            },
            {
                "tipo": "card",
                "mensaje": {
                    "categoria": "alimentos y bebidas",
                    "subcategoria": "Restaurante",
                },
            },
        ]
    }

    assert orquestador._extraer_catalogo_respuesta_exploracion(exploracion) == {
        "categorias": ["Alimentos y Bebidas"],
        "subcategorias": ["Restaurante"],
    }


def test_extrae_catalogo_ignora_globos_y_mensajes_sin_card():
    exploracion = {
        "mensajes_app": [
            {"tipo": "globo", "mensaje": {"categoria": "No debe guardarse"}},
            {
                "tipo": "card",
                "mensaje": {
                    "categoria": "",
                    "subcategoria": "Museo",
                },
            },
        ]
    }

    assert orquestador._extraer_catalogo_respuesta_exploracion(exploracion) == {
        "categorias": None,
        "subcategorias": ["Museo"],
    }


def test_guardar_historial_final_envia_json_final(monkeypatch):
    llamadas = []

    async def guardar_fake(payload):
        llamadas.append(payload)
        return {"mensaje": "ok"}

    monkeypatch.setattr(orquestador, "guardar_historial_exploracion", guardar_fake)

    clasificacion_final = {
        "pregunta_chatboot": "exploracion",
        "id_usuario": 7,
        "client_message_id": "msg-7",
        "sesion_id": "sesion-7",
        "mensaje": {
            "mensaje_usuario": "Busco hoteles",
            "texto_limpio": "Busco hoteles",
        },
        "exploracion": {
            "mensajes_app": [
                {"tipo": "globo", "mensaje": {}},
                {
                    "tipo": "card",
                    "mensaje": {
                        "categoria": "Alojamiento",
                        "subcategoria": "Hotel",
                    },
                },
            ]
        },
    }
    estado_exploracion = {"plan": {"consultas": []}}

    orquestador._guardar_historial_exploracion_final(
        clasificacion_final=clasificacion_final,
        estado_exploracion=estado_exploracion,
    )

    assert llamadas == [
        {
            "id_usuario": 7,
            "sesion_id": "sesion-7",
            "client_message_id": "msg-7",
            "texto_usuario": "Busco hoteles",
            "respuesta_json": clasificacion_final,
            "categorias": ["Alojamiento"],
            "subcategorias": ["Hotel"],
        }
    ]


def test_guardar_historial_final_sin_id_usuario_no_llama_api(monkeypatch):
    async def guardar_fake(payload):
        raise AssertionError("No debe llamar historial sin id_usuario")

    monkeypatch.setattr(orquestador, "guardar_historial_exploracion", guardar_fake)

    orquestador._guardar_historial_exploracion_final(
        clasificacion_final={
            "client_message_id": "msg-1",
            "sesion_id": "sesion-1",
            "mensaje": {"texto_limpio": "Hola"},
        },
        estado_exploracion={"plan": None},
    )
