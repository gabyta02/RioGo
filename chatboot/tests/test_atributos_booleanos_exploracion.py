import asyncio
from unittest.mock import patch

from application.nodes.chatboot_exploracion.herramientas.atributos_booleanos_consulta import (
    ejecutar,
)
from application.nodes.chatboot_exploracion.utilidades import ejecutar_plan_tools
from application.shared.sanitizar_plan import sanitizar_plan_exploracion


class ClienteFake:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    async def post_herramienta(self, endpoint, payload, timeout_seconds=None):
        self.llamadas.append(
            {
                "endpoint": endpoint,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.respuesta


def _plan_atributo(parametros):
    return {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {
                            "nombre": "busqueda_semantica",
                            "parametros": {
                                "texto_embeddings": "busqueda inicial",
                                "keywords": ["busqueda"],
                                "excluir_terminos": [],
                            },
                        },
                    },
                    {
                        "orden": 2,
                        "herramienta": {
                            "nombre": "atributos_booleanos",
                            "parametros": parametros,
                        },
                    },
                ]
            }
        ]
    }


def _atributos_base(**overrides):
    parametros = {
        "tiene_wifi": None,
        "permite_mascotas": None,
        "accesibilidad": None,
        "parqueadero": None,
        "es_gratuito": None,
        "excluir": [],
    }
    parametros.update(overrides)
    return parametros


def test_plan_museo_gratuito_conserva_atributo_sin_error():
    plan, errores = sanitizar_plan_exploracion(
        _plan_atributo(_atributos_base(es_gratuito=True))
    )

    pasos = plan["consultas"][0]["ejecucion_herramienta"]
    assert errores == []
    assert pasos[1]["herramienta"]["nombre"] == "atributos_booleanos"
    assert pasos[1]["herramienta"]["parametros"]["es_gratuito"] is True


def test_plan_hotel_wifi_conserva_atributo_sin_error():
    plan, errores = sanitizar_plan_exploracion(
        _plan_atributo(_atributos_base(tiene_wifi=True))
    )

    pasos = plan["consultas"][0]["ejecucion_herramienta"]
    assert errores == []
    assert pasos[1]["herramienta"]["parametros"]["tiene_wifi"] is True


def test_plan_parque_accesibilidad_conserva_atributo_sin_error():
    plan, errores = sanitizar_plan_exploracion(
        _plan_atributo(_atributos_base(accesibilidad=True))
    )

    pasos = plan["consultas"][0]["ejecucion_herramienta"]
    assert errores == []
    assert pasos[1]["herramienta"]["parametros"]["accesibilidad"] is True


def test_atributos_booleanos_llama_endpoint_con_ids_y_payload():
    cliente = ClienteFake(
        {
            "ids_sitio": [69, 70],
            "estado_busqueda": {
                "estado": "cumplido",
                "ids_entrada": [70, 69, 73],
                "ids_salida": [69, 70],
                "filtros": [],
                "retroalimentacion": {},
            },
        }
    )

    estado, tipo_ids = asyncio.run(
        ejecutar(
            orden=2,
            parametros=_atributos_base(es_gratuito=True),
            ids_consulta=[70, 69, 73],
            tipo_ids="sitio",
            state={},
            cliente=cliente,
        )
    )

    assert tipo_ids == "sitio"
    assert estado["status"] == "ok"
    assert estado["ids"] == [69, 70]
    assert cliente.llamadas == [
        {
            "endpoint": "/atributos-booleanos-consulta",
            "payload": {
                "tiene_wifi": None,
                "permite_mascotas": None,
                "accesibilidad": None,
                "parqueadero": None,
                "es_gratuito": True,
                "excluir": [],
                "ids_consulta": [70, 69, 73],
            },
            "timeout_seconds": None,
        }
    ]


def test_atributos_booleanos_interpreta_sin_sitios():
    cliente = ClienteFake(
        {
            "sin_sitios": "Ningún sitio cumple con los atributos booleanos indicados.",
            "estado_busqueda": {
                "estado": "no_cumplido",
                "ids_entrada": [1, 2],
                "ids_salida": [],
                "filtros": [],
                "retroalimentacion": {},
            },
        }
    )

    estado, tipo_ids = asyncio.run(
        ejecutar(
            orden=2,
            parametros=_atributos_base(tiene_wifi=True),
            ids_consulta=[1, 2],
            tipo_ids="sitio",
            state={},
            cliente=cliente,
        )
    )

    assert tipo_ids is None
    assert estado["status"] == "sin_resultados"
    assert estado["ids"] == []
    assert "Ningún sitio cumple" in estado["nota"]


def test_gis_automatico_usa_ids_filtrados_si_existen():
    llamadas = []
    estados = [
        {
            "herramienta": "busqueda_semantica",
            "orden": 1,
            "status": "ok",
            "ids": [70, 69, 73, 17],
            "payload": {
                "candidatos": [
                    {"id_sitio": 70},
                    {"id_sitio": 69},
                    {"id_sitio": 73},
                    {"id_sitio": 17},
                ]
            },
            "nota": "",
            "estado_busqueda": {},
        },
        {
            "herramienta": "atributos_booleanos",
            "orden": 2,
            "status": "ok",
            "ids": [69, 70],
            "payload": {},
            "nota": "",
            "estado_busqueda": {},
        },
    ]

    async def ejecutar_herramienta_fake(**kwargs):
        llamadas.append(kwargs)
        return (
            {
                "herramienta": "gis",
                "orden": kwargs["orden"],
                "status": "ok",
                "ids": kwargs["ids_consulta"],
                "payload": {"ids_sitio": kwargs["ids_consulta"]},
                "nota": "",
                "estado_busqueda": {},
            },
            "sitio",
        )

    with patch.object(
        ejecutar_plan_tools,
        "ejecutar_herramienta",
        ejecutar_herramienta_fake,
    ):
        asyncio.run(
            ejecutar_plan_tools._anexar_gis_automatico(
                state={"ubicacion_usuario": {"lat": -1.67, "lon": -78.65}},
                cliente=ClienteFake({}),
                estados=estados,
                ids_sitio=[69, 70],
            )
        )

    assert llamadas[0]["nombre"] == "busqueda_ubicacion"
    assert llamadas[0]["parametros"]["tipo_busqueda"] == "cercania"
    assert llamadas[0]["ids_consulta"] == [69, 70]


def test_busqueda_ubicacion_normaliza_proximidad_textual_media():
    plan, errores = sanitizar_plan_exploracion(
        {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "busqueda_semantica",
                                "parametros": {
                                    "texto_embeddings": "hostal en riobamba",
                                    "keywords": ["hostal"],
                                    "excluir_terminos": [],
                                },
                            },
                        },
                        {
                            "orden": 2,
                            "herramienta": {
                                "nombre": "busqueda_ubicacion",
                                "parametros": {
                                    "entidad": "sitio",
                                    "tipo_busqueda": "cercania",
                                    "referencia_ubicacion": "",
                                    "usar_ubicacion_usuario": True,
                                    "distancia": None,
                                    "unidad": "",
                                    "proximidad_textual": "media",
                                    "excluir_zonas": [],
                                },
                            },
                        },
                    ]
                }
            ]
        }
    )

    parametros = plan["consultas"][0]["ejecucion_herramienta"][1]["herramienta"][
        "parametros"
    ]
    assert errores == []
    assert parametros["proximidad_textual"] == "media"
    assert parametros["distancia"] == 500
    assert parametros["unidad"] == "m"


def test_busqueda_ubicacion_distancia_numerica_tiene_prioridad():
    plan, errores = sanitizar_plan_exploracion(
        {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "busqueda_semantica",
                                "parametros": {
                                    "texto_embeddings": "museo en riobamba",
                                    "keywords": ["museo"],
                                    "excluir_terminos": [],
                                },
                            },
                        },
                        {
                            "orden": 2,
                            "herramienta": {
                                "nombre": "busqueda_ubicacion",
                                "parametros": {
                                    "entidad": "sitio",
                                    "tipo_busqueda": "cercania",
                                    "referencia_ubicacion": "",
                                    "usar_ubicacion_usuario": True,
                                    "distancia": 20,
                                    "unidad": "km",
                                    "proximidad_textual": "corta",
                                    "excluir_zonas": [],
                                },
                            },
                        },
                    ]
                }
            ]
        }
    )

    parametros = plan["consultas"][0]["ejecucion_herramienta"][1]["herramienta"][
        "parametros"
    ]
    assert errores == []
    assert parametros["distancia"] == 20
    assert parametros["unidad"] == "km"
