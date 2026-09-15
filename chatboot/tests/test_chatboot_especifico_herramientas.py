from __future__ import annotations

import pytest

from application.nodes.chatboot_especifico.herramientas.registry import (
    ejecutar_herramienta,
)
from application.nodes.chatboot_especifico.utilidades.ejecutar_plan_pregunta import (
    ejecutar_plan_pregunta,
)
from application.shared.empaquetar_mensaje import construir_globo


@pytest.mark.asyncio
async def test_conversacional_sitio_devuelve_globo():
    estado, _ = await ejecutar_herramienta(
        nombre="conversacional",
        orden=1,
        parametros={"tipo": "saludo"},
        ids_consulta=[],
        tipo_ids=None,
        state={},
        cliente=None,
    )

    assert estado["status"] == "ok"
    assert estado["payload"]["tipo"] == "saludo"
    assert estado["payload"]["mensaje_app"]["tipo"] == "globo"


@pytest.mark.asyncio
async def test_fallback_sitio_usa_respuesta_sugerida():
    texto = "Puedo ayudarte solo con preguntas de este sitio."
    estado, _ = await ejecutar_herramienta(
        nombre="fallback",
        orden=1,
        parametros={"respuesta_sugerida": texto},
        ids_consulta=[],
        tipo_ids=None,
        state={},
        cliente=None,
    )

    assert estado["status"] == "sin_resultados"
    assert estado["payload"]["mensaje_app"]["tipo"] == "globo"
    assert estado["payload"]["mensaje_app"]["mensaje"]["texto"] == texto


@pytest.mark.asyncio
async def test_fallback_sitio_default_usa_negrita():
    estado, _ = await ejecutar_herramienta(
        nombre="fallback",
        orden=1,
        parametros={},
        ids_consulta=[],
        tipo_ids=None,
        state={},
        cliente=None,
    )

    assert "**" in estado["payload"]["texto"]


@pytest.mark.asyncio
async def test_herramienta_desconocida_devuelve_error():
    estado, _ = await ejecutar_herramienta(
        nombre="no_existe",
        orden=1,
        parametros={},
        ids_consulta=[],
        tipo_ids=None,
        state={},
        cliente=None,
    )

    assert estado["status"] == "error"
    assert "no registrada" in estado["nota"]


@pytest.mark.asyncio
async def test_multimedia_sitio_devuelve_tipo_multimedia():
    estado, _ = await ejecutar_herramienta(
        nombre="multimedia",
        orden=1,
        parametros={},
        ids_consulta=[],
        tipo_ids=None,
        state={"id_sitio": 68},
        cliente=ClienteFake(
            {
                "/multimedia": {
                    "id_sitio": 68,
                    "imagenes": [{"url": "/api/v1/imagenes/sitio.jpg", "es_principal": True}],
                }
            }
        ),
    )

    assert estado["status"] == "ok"
    assert estado["payload"]["mensaje_app"]["tipo"] == "multimedia"


@pytest.mark.asyncio
async def test_como_llegar_devuelve_globo_y_accion_google_maps():
    estado, _ = await ejecutar_herramienta(
        nombre="como_llegar",
        orden=1,
        parametros={},
        ids_consulta=[],
        tipo_ids=None,
        state={"id_sitio": 68, "nombre_sitio": "Mercado de la Merced"},
        cliente=ClienteFake(
            {
                "/como-llegar": {
                    "id_sitio": 68,
                    "nombre": "Mercado de la Merced",
                    "ubicacion": {"lat": -1.67, "lon": -78.64},
                }
            }
        ),
    )

    mensajes = estado["payload"]["mensajes_app"]
    assert estado["status"] == "ok"
    assert mensajes[0]["tipo"] == "globo"
    assert mensajes[1]["mensaje"]["accion"] == "abrir_google_maps"


@pytest.mark.asyncio
async def test_ejecutor_pregunta_conversacional_genera_mensaje_app():
    state = _state_con_plan(
        {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "conversacional",
                                "parametros": {"tipo": "saludo"},
                            },
                        }
                    ]
                }
            ]
        }
    )

    resultado = await ejecutar_plan_pregunta(state)

    assert len(resultado["estados_herramientas"]) == 1
    assert resultado["mensajes_app"][0]["tipo"] == "globo"
    assert resultado["resultado_pregunta_directa"]["mensajes_app"][0]["tipo"] == "globo"


@pytest.mark.asyncio
async def test_ejecutor_pregunta_consultas_en_paralelo_acumula_globos():
    state = _state_con_plan(
        {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "fallback",
                                "parametros": {"respuesta_sugerida": "Uno"},
                            },
                        }
                    ]
                },
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "fallback",
                                "parametros": {"respuesta_sugerida": "Dos"},
                            },
                        }
                    ]
                },
            ]
        }
    )

    resultado = await ejecutar_plan_pregunta(state)

    textos = [
        item["mensaje"]["texto"] for item in resultado["mensajes_app"]
    ]
    assert textos == ["Uno", "Dos"]


@pytest.mark.asyncio
async def test_ejecutor_pregunta_respeta_orden_secuencial():
    state = _state_con_plan(
        {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 2,
                            "herramienta": {
                                "nombre": "fallback",
                                "parametros": {"respuesta_sugerida": "Segundo"},
                            },
                        },
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "fallback",
                                "parametros": {"respuesta_sugerida": "Primero"},
                            },
                        },
                    ]
                }
            ]
        }
    )

    resultado = await ejecutar_plan_pregunta(state)

    textos = [
        item["mensaje"]["texto"] for item in resultado["mensajes_app"]
    ]
    assert textos == ["Primero", "Segundo"]


@pytest.mark.asyncio
async def test_ejecutor_pregunta_plan_invalido_conserva_mensaje_existente():
    mensaje_app = construir_globo("Intenta otra vez", origen="crear_plan_pregunta")
    state = {
        "plan_valido": False,
        "plan": None,
        "errores_formato": [{"tipo": "json_invalido"}],
        "mensaje_app": mensaje_app,
        "mensaje_sistema": "Intenta otra vez",
    }

    resultado = await ejecutar_plan_pregunta(state)

    assert resultado["estados_herramientas"] == []
    assert resultado["mensajes_app"] == [mensaje_app]
    assert resultado["resultado_pregunta_directa"]["mensajes_app"] == [mensaje_app]


def _state_con_plan(plan):
    return {
        "plan_valido": True,
        "plan": plan,
        "errores_formato": [],
        "mensaje_app": None,
        "mensaje_sistema": None,
    }


class ClienteFake:
    def __init__(self, respuestas):
        self.respuestas = respuestas

    async def post(self, endpoint, payload):
        respuesta = self.respuestas.get(endpoint)
        if respuesta is None:
            return {"fallo": f"Sin fake para {endpoint}"}
        return respuesta
