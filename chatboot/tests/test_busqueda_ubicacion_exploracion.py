import asyncio

from application.nodes.chatboot_exploracion.herramientas.busqueda_ubicacion import (
    ejecutar as ejecutar_busqueda_ubicacion,
)
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


def _plan_ubicacion(parametros):
    return {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {
                            "nombre": "busqueda_semantica",
                            "parametros": {
                                "texto_embeddings": "busqueda inicial turistica",
                                "keywords": [],
                                "excluir_terminos": [],
                            },
                        },
                    },
                    {
                        "orden": 2,
                        "herramienta": {
                            "nombre": "busqueda_ubicacion",
                            "parametros": parametros,
                        },
                    },
                ]
            }
        ]
    }


def _parametros_ubicacion(plan):
    return plan["consultas"][0]["ejecucion_herramienta"][1]["herramienta"][
        "parametros"
    ]


def _assert_plan_valido(parametros):
    plan, errores = sanitizar_plan_exploracion(_plan_ubicacion(parametros))
    assert errores == []
    return _parametros_ubicacion(plan)


def test_plan_hotel_cerca_mercado_condamine_usa_cercania():
    parametros = _assert_plan_valido(
        {
            "entidad": "sitio",
            "tipo_busqueda": "cercania",
            "referencia_ubicacion": "mercado la condamine",
            "usar_ubicacion_usuario": False,
            "distancia": None,
            "unidad": "",
            "excluir_zonas": [],
        }
    )

    assert parametros["tipo_busqueda"] == "cercania"
    assert parametros["referencia_ubicacion"] == "mercado la condamine"


def test_plan_hoteles_cerca_mi_posicion_usa_ubicacion_usuario():
    parametros = _assert_plan_valido(
        {
            "entidad": "sitio",
            "tipo_busqueda": "cercania",
            "referencia_ubicacion": "",
            "usar_ubicacion_usuario": True,
            "distancia": None,
            "unidad": "",
            "excluir_zonas": [],
        }
    )

    assert parametros["usar_ubicacion_usuario"] is True
    assert parametros["referencia_ubicacion"] == ""


def test_plan_hoteles_a_5_minutos_convierte_a_400_metros():
    parametros = _assert_plan_valido(
        {
            "entidad": "sitio",
            "tipo_busqueda": "cercania",
            "referencia_ubicacion": "",
            "usar_ubicacion_usuario": True,
            "distancia": 400,
            "unidad": "m",
            "excluir_zonas": [],
        }
    )

    assert parametros["distancia"] == 400
    assert parametros["unidad"] == "m"


def test_plan_restaurantes_menos_1km_parque_sucre_usa_radio_fijo():
    parametros = _assert_plan_valido(
        {
            "entidad": "sitio",
            "tipo_busqueda": "cercania",
            "referencia_ubicacion": "parque sucre",
            "usar_ubicacion_usuario": False,
            "distancia": 1,
            "unidad": "km",
            "excluir_zonas": [],
        }
    )

    assert parametros["distancia"] == 1
    assert parametros["unidad"] == "km"
    assert parametros["referencia_ubicacion"] == "parque sucre"


def test_plan_museos_cerca_estacion_tren_usa_cercania():
    parametros = _assert_plan_valido(
        {
            "entidad": "sitio",
            "tipo_busqueda": "cercania",
            "referencia_ubicacion": "estacion del tren riobamba",
            "usar_ubicacion_usuario": False,
            "distancia": None,
            "unidad": "",
            "excluir_zonas": [],
        }
    )

    assert parametros["referencia_ubicacion"] == "estacion del tren riobamba"


def test_plan_calle_daniel_leon_borja_usa_cercania():
    parametros = _assert_plan_valido(
        {
            "entidad": "sitio",
            "tipo_busqueda": "cercania",
            "referencia_ubicacion": "Av. Daniel León Borja y Duchicela",
            "usar_ubicacion_usuario": False,
            "distancia": None,
            "unidad": "",
            "excluir_zonas": [],
        }
    )

    assert parametros["referencia_ubicacion"] == "Av. Daniel León Borja y Duchicela"


def test_plan_leopoldo_ormaza_usa_zona_textual_si_no_pide_cerca():
    parametros = _assert_plan_valido(
        {
            "entidad": "sitio",
            "tipo_busqueda": "zona_textual",
            "referencia_ubicacion": "Leopoldo Ormaza y Agustín Cascante",
            "usar_ubicacion_usuario": None,
            "distancia": None,
            "unidad": "",
            "excluir_zonas": [],
        }
    )

    assert parametros["tipo_busqueda"] == "zona_textual"
    assert parametros["referencia_ubicacion"] == "Leopoldo Ormaza y Agustín Cascante"


def test_plan_guayaquil_cristobal_colon_usa_cercania():
    parametros = _assert_plan_valido(
        {
            "entidad": "sitio",
            "tipo_busqueda": "cercania",
            "referencia_ubicacion": "Guayaquil y Cristobal Colón",
            "usar_ubicacion_usuario": False,
            "distancia": None,
            "unidad": "",
            "excluir_zonas": [],
        }
    )

    assert parametros["tipo_busqueda"] == "cercania"
    assert parametros["referencia_ubicacion"] == "Guayaquil y Cristobal Colón"


def test_wrapper_inyecta_ubicacion_central_riobamba():
    cliente = ClienteFake(
        {
            "ids_sitio": [10],
            "candidatos": [
                {
                    "id_sitio": 10,
                    "nombre": "Hotel Central",
                    "distancia_metros": 350.0,
                    "distancia_aproximada": "350 m",
                }
            ],
            "retroalimentacion": {"mensaje": "Cercano"},
        }
    )

    resultado, tipo_ids = asyncio.run(
        ejecutar_busqueda_ubicacion(
            orden=2,
            parametros={
                "entidad": "sitio",
                "tipo_busqueda": "cercania",
                "referencia_ubicacion": "",
                "usar_ubicacion_usuario": True,
                "distancia": 400,
                "unidad": "m",
                "excluir_zonas": [],
            },
            ids_consulta=[10, 11],
            tipo_ids="sitio",
            state={"ubicacion_usuario": {"lat": -1.6736, "lng": -78.6473}},
            cliente=cliente,
        )
    )

    assert resultado["status"] == "ok"
    assert tipo_ids == "sitio"
    assert cliente.llamadas[0]["endpoint"] == "/busqueda-ubicacion"
    assert cliente.llamadas[0]["payload"]["ubicacion_usuario"] == {
        "lat": -1.6736,
        "lon": -78.6473,
    }
    assert cliente.llamadas[0]["payload"]["ids_consulta"] == [10, 11]
