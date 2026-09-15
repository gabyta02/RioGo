from __future__ import annotations

from application.nodes.chatboot_exploracion.utilidades.guardar_memoria import (
    _extraer_respuesta_exploracion,
    guardar_memoria_exploracion,
)


def test_extraer_respuesta_incluye_globo_y_opciones():
    state = {
        "mensajes_app": [
            {
                "tipo": "globo",
                "mensaje": {
                    "texto": "¿Qué tipo de pesca deportiva te interesa?",
                },
            },
            {
                "tipo": "opciones",
                "mensaje": {"opciones": ["Laguna", "Montaña", "Cascada"]},
            },
        ]
    }

    respuesta = _extraer_respuesta_exploracion(state)

    assert "pesca deportiva" in respuesta
    assert "[Opciones: Laguna, Montaña, Cascada]" in respuesta


def test_guardar_memoria_persiste_respuesta_del_turno(monkeypatch):
    guardado: dict = {}

    def guardar_fake(sesion_id, memoria):
        guardado["sesion_id"] = sesion_id
        guardado["memoria"] = memoria
        return memoria

    monkeypatch.setattr(
        "infrastructure.memory.guardar_memoria",
        guardar_fake,
    )

    state = {
        "sesion_id": "sesion-pesca",
        "client_message_id": "msg-2",
        "texto_usuario": "no importa en cualquier lugar mientras la pueda realizar",
        "memoria": {
            "turnos": [
                {
                    "turno": 1,
                    "pregunta": "podrias recomendarme donde puedo realizar pesca deportiva",
                    "respuesta": (
                        "¿Qué tipo de pesca deportiva te interesa?\n"
                        "[Opciones: Laguna, Montaña, Cascada, Quebrada, otros]"
                    ),
                    "client_message_id": "msg-1",
                }
            ],
            "entidades": [],
        },
        "mensajes_app": [
            {
                "tipo": "globo",
                "mensaje": {"texto": "¿Qué tipo de actividad quieres realizar exactamente?"},
            },
            {
                "tipo": "opciones",
                "mensaje": {"opciones": ["pesca deportiva", "senderismo"]},
            },
        ],
        "entidades_resueltas": [],
    }

    salida = guardar_memoria_exploracion(state)
    preguntas = guardado["memoria"]["preguntas"]

    assert guardado["sesion_id"] == "sesion-pesca"
    assert preguntas[0]["texto"] == state["texto_usuario"]
    assert "actividad quieres realizar" in preguntas[0]["resultado"]
    assert "[Opciones: pesca deportiva, senderismo]" in preguntas[0]["resultado"]
    assert any(
        "pesca deportiva te interesa" in str(item.get("resultado") or "")
        for item in preguntas
    )
    assert salida["memoria"]["turnos"][0]["respuesta"] == preguntas[0]["resultado"]
