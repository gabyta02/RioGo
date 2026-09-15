import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import patch

from application.nodes.chatboot_exploracion.utilidades import ejecutar_plan_tools
from application.shared.sanitizar_plan import sanitizar_plan_exploracion


class ClienteFake:
    async def obtener_opciones_fallback_exploracion(self):
        return [
            {"categoria": "Alojamiento", "subcategorias": ["Hotel", "Hostal"]},
            {"categoria": "Manifestaciones Culturales", "subcategorias": ["Museo"]},
        ]


class RouteSettingsFake:
    thinking_enabled = False


class ClientLLMFake:
    async def generate_response(self, *_args, **_kwargs):
        return {
            "mensaje": "Puedo ayudarte si buscamos por tipo de lugar o ubicación.",
            "opciones": ["Hotel", "Museo"],
        }


class RouterFake:
    def get_route_settings(self, _route):
        return RouteSettingsFake()

    def get_client_for_route(self, _route):
        return ClientLLMFake()


def _estado_fallback(motivo):
    return {
        "herramienta": "fallback",
        "orden": 1,
        "status": "sin_resultados",
        "ids": [],
        "payload": {"motivo": motivo},
        "nota": motivo,
        "estado_busqueda": {},
    }


def test_sanitizador_acepta_fallback_sin_motivo():
    plan, errores = sanitizar_plan_exploracion(
        {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "fallback",
                                "parametros": {},
                            },
                        }
                    ]
                }
            ]
        }
    )

    herramienta = plan["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]
    assert errores == []
    assert herramienta["parametros"] == {}


def test_redactar_fallback_llm_devuelve_mensaje_y_opciones():
    fake_llms = SimpleNamespace(get_llm_router=lambda: RouterFake())
    with patch.dict(sys.modules, {"infrastructure.llms": fake_llms}):
        salida = asyncio.run(
            ejecutar_plan_tools._redactar_fallback_llm(
                state={"texto_usuario": "cuál hotel es mejor", "memoria": {"turnos": []}},
                estados=[_estado_fallback("capacidad_no_soportada")],
                cliente=ClienteFake(),
            )
        )

    assert "tipo de lugar" in salida["mensaje"]
    assert salida["opciones"] == ["Hotel", "Museo"]


def test_fallback_deterministico_si_llm_falla():
    class RouterFalla:
        def get_route_settings(self, _route):
            return RouteSettingsFake()

        def get_client_for_route(self, _route):
            raise RuntimeError("sin llm")

    fake_llms = SimpleNamespace(get_llm_router=lambda: RouterFalla())
    with patch.dict(sys.modules, {"infrastructure.llms": fake_llms}):
        salida = asyncio.run(
            ejecutar_plan_tools._redactar_fallback_llm(
                state={"texto_usuario": "qué me recomiendas hacer"},
                estados=[_estado_fallback("sin_intencion_clara")],
                cliente=ClienteFake(),
            )
        )

    assert "dime qué tipo" in salida["mensaje"]
    assert salida["opciones"][:2] == ["Hotel", "Hostal"]


def test_fallback_deterministico_rutas_de_bus_remite_al_mapa():
    class RouterFalla:
        def get_route_settings(self, _route):
            return RouteSettingsFake()

        def get_client_for_route(self, _route):
            raise RuntimeError("sin llm")

    fake_llms = SimpleNamespace(get_llm_router=lambda: RouterFalla())
    with patch.dict(sys.modules, {"infrastructure.llms": fake_llms}):
        salida = asyncio.run(
            ejecutar_plan_tools._redactar_fallback_llm(
                state={"texto_usuario": "qué ruta de bus pasa por el centro"},
                estados=[_estado_fallback("no_clasificado")],
                cliente=ClienteFake(),
            )
        )

    assert "mapa del aplicativo" in salida["mensaje"]
    assert salida["opciones"] == []


def test_fallback_deterministico_infiere_fuera_de_chimborazo():
    salida = ejecutar_plan_tools._fallback_deterministico_inteligente(
        "no_clasificado",
        [],
        mensaje_usuario="quiero lugares turísticos en Quito",
    )

    assert "Riobamba y Chimborazo" in salida["mensaje"]
    assert salida["opciones"] == []


def test_fallback_deterministico_infiere_falta_de_memoria():
    salida = ejecutar_plan_tools._fallback_deterministico_inteligente(
        "no_clasificado",
        [],
        mensaje_usuario="y de esos cuál está más cerca",
    )

    assert "nombre del lugar" in salida["mensaje"]
    assert salida["opciones"] == []


def test_fallback_deterministico_infiere_fuera_de_dominio_antes_que_comparacion():
    salida = ejecutar_plan_tools._fallback_deterministico_inteligente(
        "no_clasificado",
        [{"categoria": "Alojamiento", "subcategorias": ["Hotel"]}],
        mensaje_usuario="google es mejor que brave",
    )

    assert "Riobamba y Chimborazo" in salida["mensaje"]
    assert salida["opciones"] == []


def test_fallback_deterministico_infiere_hotel_de_antes_como_memoria():
    salida = ejecutar_plan_tools._fallback_deterministico_inteligente(
        "no_clasificado",
        [{"categoria": "Alojamiento", "subcategorias": ["Hotel"]}],
        mensaje_usuario="me puedes hablar del hotel de antes",
    )

    assert "nombre del lugar" in salida["mensaje"]
    assert salida["opciones"] == []
