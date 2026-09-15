import asyncio
from unittest.mock import patch

from application.nodes.chatboot_exploracion.herramientas.precio_consulta import (
    _validar_contrato_precio,
    ejecutar as ejecutar_precio,
)
from application.nodes.chatboot_exploracion.herramientas.tarifa_acceso_consulta import (
    _validar_contrato_tarifa,
    ejecutar as ejecutar_tarifa,
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


def _plan_con_refinador(nombre, parametros):
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
                                "keywords": [],
                                "excluir_terminos": [],
                            },
                        },
                    },
                    {
                        "orden": 2,
                        "herramienta": {
                            "nombre": nombre,
                            "parametros": parametros,
                        },
                    },
                ]
            }
        ]
    }


def test_plan_hotel_maximo_80_conserva_precio():
    plan, errores = sanitizar_plan_exploracion(
        _plan_con_refinador(
            "precio",
            {
                "es_gratuito": None,
                "precio_numero": 80,
                "operador": "<=",
                "etiqueta": "",
                "excluir_etiquetas": [],
            },
        )
    )

    parametros = plan["consultas"][0]["ejecucion_herramienta"][1]["herramienta"][
        "parametros"
    ]
    assert errores == []
    assert parametros["precio_numero"] == 80
    assert parametros["operador"] == "<="


def test_plan_comida_barata_conserva_precio_economico():
    plan, errores = sanitizar_plan_exploracion(
        _plan_con_refinador(
            "precio",
            {
                "es_gratuito": None,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "economico",
                "excluir_etiquetas": [],
            },
        )
    )

    parametros = plan["consultas"][0]["ejecucion_herramienta"][1]["herramienta"][
        "parametros"
    ]
    assert errores == []
    assert parametros["etiqueta"] == "economico"


def test_plan_museo_entradas_baratas_conserva_tarifa_economica():
    plan, errores = sanitizar_plan_exploracion(
        _plan_con_refinador(
            "tarifa_acceso",
            {
                "entrada_gratuita": None,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "economico",
                "condicion": "",
                "excluir_condiciones": [],
            },
        )
    )

    parametros = plan["consultas"][0]["ejecucion_herramienta"][1]["herramienta"][
        "parametros"
    ]
    assert errores == []
    assert parametros["etiqueta"] == "economico"


def test_plan_museo_un_dolar_estudiantes_conserva_tarifa():
    plan, errores = sanitizar_plan_exploracion(
        _plan_con_refinador(
            "tarifa_acceso",
            {
                "entrada_gratuita": None,
                "precio_numero": 1,
                "operador": "=",
                "etiqueta": "",
                "condicion": "estudiante",
                "excluir_condiciones": [],
            },
        )
    )

    parametros = plan["consultas"][0]["ejecucion_herramienta"][1]["herramienta"][
        "parametros"
    ]
    assert errores == []
    assert parametros["precio_numero"] == 1
    assert parametros["operador"] == "="
    assert parametros["condicion"] == "estudiante"


def test_validadores_aceptan_moderado_y_todo_publico():
    assert _validar_contrato_precio(
        {"es_gratuito": None, "precio_numero": None, "operador": "", "etiqueta": "moderado"}
    ) == ""
    assert _validar_contrato_tarifa(
        {
            "entrada_gratuita": None,
            "precio_numero": None,
            "operador": "",
            "etiqueta": "moderado",
            "condicion": "todo publico",
        }
    ) == ""
    assert _validar_contrato_tarifa(
        {
            "entrada_gratuita": None,
            "precio_numero": 1,
            "operador": "<=",
            "etiqueta": "economico",
            "condicion": "todo el público",
        }
    ) == ""


def test_precio_llama_endpoint_con_payload():
    cliente = ClienteFake({"ids_sitio": [8, 9]})

    estado, tipo_ids = asyncio.run(
        ejecutar_precio(
            orden=2,
            parametros={
                "es_gratuito": None,
                "precio_numero": 80,
                "operador": "<=",
                "etiqueta": "",
                "excluir_etiquetas": [],
            },
            ids_consulta=[8, 6, 7, 9],
            tipo_ids="sitio",
            state={},
            cliente=cliente,
        )
    )

    assert tipo_ids == "sitio"
    assert estado["status"] == "ok"
    assert cliente.llamadas[0]["endpoint"] == "/precio-consulta"
    assert cliente.llamadas[0]["payload"]["ids_consulta"] == [8, 6, 7, 9]
    assert cliente.llamadas[0]["payload"]["operador"] == "<="


def test_tarifa_llama_endpoint_con_payload():
    cliente = ClienteFake({"ids_sitio": [73]})

    estado, tipo_ids = asyncio.run(
        ejecutar_tarifa(
            orden=2,
            parametros={
                "entrada_gratuita": None,
                "precio_numero": 1,
                "operador": "=",
                "etiqueta": "",
                "condicion": "estudiante",
                "excluir_condiciones": [],
            },
            ids_consulta=[73, 70, 69],
            tipo_ids="sitio",
            state={},
            cliente=cliente,
        )
    )

    assert tipo_ids == "sitio"
    assert estado["status"] == "ok"
    assert cliente.llamadas[0]["endpoint"] == "/tarifa-acceso-consulta"
    assert cliente.llamadas[0]["payload"]["condicion"] == "estudiante"


def test_semantica_debil_con_candidatos_continua_hacia_precio():
    llamadas = []

    async def ejecutar_herramienta_fake(**kwargs):
        llamadas.append(kwargs)
        if kwargs["nombre"] == "busqueda_semantica":
            return (
                {
                    "herramienta": "busqueda_semantica",
                    "orden": 1,
                    "status": "sin_resultados",
                    "ids": [],
                    "payload": {
                        "candidatos": [
                            {"id_sitio": 21},
                            {"id_sitio": 27},
                        ]
                    },
                    "nota": "Candidatos aproximados.",
                    "estado_busqueda": {},
                },
                "sitio",
            )
        return (
            {
                "herramienta": "precio",
                "orden": 2,
                "status": "ok",
                "ids": [21],
                "payload": {"ids_sitio": [21]},
                "nota": "",
                "estado_busqueda": {},
            },
            "sitio",
        )

    consulta = _plan_con_refinador(
        "precio",
        {
            "es_gratuito": None,
            "precio_numero": None,
            "operador": "",
            "etiqueta": "economico",
            "excluir_etiquetas": [],
        },
    )["consultas"][0]

    with patch.object(
        ejecutar_plan_tools,
        "ejecutar_herramienta",
        ejecutar_herramienta_fake,
    ):
        resultado = asyncio.run(
            ejecutar_plan_tools._ejecutar_consulta(consulta, {}, ClienteFake({}))
        )

    assert [llamada["nombre"] for llamada in llamadas] == [
        "busqueda_semantica",
        "precio",
    ]
    assert llamadas[1]["ids_consulta"] == [21, 27]
    assert resultado["ids"] == [21]


def test_tarifa_sin_resultados_no_conserva_ids_semanticos_previos():
    async def ejecutar_herramienta_fake(**kwargs):
        if kwargs["nombre"] == "busqueda_semantica":
            return (
                {
                    "herramienta": "busqueda_semantica",
                    "orden": 1,
                    "status": "ok",
                    "ids": [73, 70, 69],
                    "payload": {"ids_sitio": [73, 70, 69]},
                    "nota": "",
                    "estado_busqueda": {},
                },
                "sitio",
            )
        return (
            {
                "herramienta": "tarifa_acceso",
                "orden": 2,
                "status": "sin_resultados",
                "ids": [],
                "payload": {"sin_sitios": "Ningún sitio cumple."},
                "nota": "Ningún sitio cumple.",
                "estado_busqueda": {"estado": "no_cumplido"},
            },
            None,
        )

    consulta = _plan_con_refinador(
        "tarifa_acceso",
        {
            "entrada_gratuita": True,
            "precio_numero": None,
            "operador": "",
            "etiqueta": "",
            "condicion": "nino",
            "excluir_condiciones": [],
        },
    )["consultas"][0]

    with patch.object(
        ejecutar_plan_tools,
        "ejecutar_herramienta",
        ejecutar_herramienta_fake,
    ):
        resultado = asyncio.run(
            ejecutar_plan_tools._ejecutar_consulta(consulta, {}, ClienteFake({}))
        )

    assert resultado["ids"] == []


def test_gis_automatico_no_usa_semanticos_si_refinador_no_cumplio():
    llamadas = []
    estados = [
        {
            "herramienta": "busqueda_semantica",
            "orden": 1,
            "status": "ok",
            "ids": [73, 70],
            "payload": {"candidatos": [{"id_sitio": 73}, {"id_sitio": 70}]},
            "nota": "",
            "estado_busqueda": {},
        },
        {
            "herramienta": "tarifa_acceso",
            "orden": 2,
            "status": "sin_resultados",
            "ids": [],
            "payload": {"sin_sitios": "Ningún sitio cumple."},
            "nota": "Ningún sitio cumple.",
            "estado_busqueda": {"estado": "no_cumplido"},
        },
    ]

    async def ejecutar_herramienta_fake(**kwargs):
        llamadas.append(kwargs)
        return ({}, None)

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
                ids_sitio=[],
            )
        )

    assert llamadas == []
