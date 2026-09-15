import asyncio

from application.nodes.chatboot_exploracion.herramientas.horario_consulta import (
    _validar_contrato_horario,
    ejecutar as ejecutar_horario,
)
from application.nodes.chatboot_exploracion.utilidades.ejecutar_plan_tools import (
    _candidatos_compactos_llm,
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


def _plan_horario(parametros):
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
                            "nombre": "horario",
                            "parametros": parametros,
                        },
                    },
                ]
            }
        ]
    }


def test_plan_restaurante_abierto_ahora_conserva_instantaneo():
    plan, errores = sanitizar_plan_exploracion(
        _plan_horario(
            {
                "tipo": "instantaneo",
                "dia_semana": None,
                "dias_semana": None,
                "hora": None,
                "rango_hora": None,
                "comparador": "",
                "excluir_dias": [],
            }
        )
    )

    parametros = plan["consultas"][0]["ejecucion_herramienta"][1]["herramienta"][
        "parametros"
    ]
    assert errores == []
    assert parametros["tipo"] == "instantaneo"


def test_plan_parque_3_tarde_conserva_punto_tiempo():
    plan, errores = sanitizar_plan_exploracion(
        _plan_horario(
            {
                "tipo": "punto_tiempo",
                "dia_semana": None,
                "dias_semana": None,
                "hora": "15:00",
                "rango_hora": None,
                "comparador": "dentro_de",
                "excluir_dias": [],
            }
        )
    )

    parametros = plan["consultas"][0]["ejecucion_herramienta"][1]["herramienta"][
        "parametros"
    ]
    assert errores == []
    assert parametros["hora"] == "15:00"


def test_plan_museo_lunes_3pm_contrato_valido():
    assert (
        _validar_contrato_horario(
            {
                "tipo": "bloque_tiempo",
                "dia_semana": 1,
                "dias_semana": None,
                "hora": None,
                "rango_hora": ["15:00", "15:00"],
                "comparador": "dentro_de",
                "excluir_dias": [],
            }
        )
        == ""
    )


def test_plan_bar_hasta_medianoche_relacional_valido():
    assert (
        _validar_contrato_horario(
            {
                "tipo": "relacional",
                "dia_semana": None,
                "dias_semana": None,
                "hora": "23:59",
                "rango_hora": None,
                "comparador": "mayor_que",
                "excluir_dias": [],
            }
        )
        == ""
    )


def test_horario_llama_endpoint_con_payload():
    cliente = ClienteFake({"ids_sitio": [69, 70]})

    estado, tipo_ids = asyncio.run(
        ejecutar_horario(
            orden=2,
            parametros={
                "tipo": "punto_tiempo",
                "dia_semana": 1,
                "dias_semana": None,
                "hora": "15:00",
                "rango_hora": None,
                "comparador": "dentro_de",
                "excluir_dias": [],
            },
            ids_consulta=[70, 69, 73],
            tipo_ids="sitio",
            state={},
            cliente=cliente,
        )
    )

    assert tipo_ids == "sitio"
    assert estado["status"] == "ok"
    assert cliente.llamadas[0]["endpoint"] == "/horario-consulta"
    assert cliente.llamadas[0]["payload"]["ids_consulta"] == [70, 69, 73]
    assert cliente.llamadas[0]["payload"]["hora"] == "15:00"


def test_juez_solo_recibe_cards_filtradas_si_existen():
    cards = [
        {
            "tipo": "card",
            "mensaje": {
                "id_sitio": 69,
                "nombre_sitio": "Casa Museo de Riobamba",
                "categoria": "Manifestaciones Culturales",
                "subcategoria": "Museo",
            },
        },
        {
            "tipo": "card",
            "mensaje": {
                "id_sitio": 70,
                "nombre_sitio": "Museo y Centro Cultural de Riobamba",
                "categoria": "Manifestaciones Culturales",
                "subcategoria": "Museo",
            },
        },
    ]
    estados = [
        {
            "herramienta": "busqueda_semantica",
            "orden": 1,
            "status": "ok",
            "ids": [70, 69, 73, 17, 71, 72],
            "payload": {
                "candidatos": [
                    {"id_sitio": 70, "nombre": "Museo y Centro Cultural"},
                    {"id_sitio": 69, "nombre": "Casa Museo"},
                    {"id_sitio": 73, "nombre": "Museo Paleontológico"},
                ]
            },
            "nota": "",
            "estado_busqueda": {},
        },
        {
            "herramienta": "horario",
            "orden": 2,
            "status": "ok",
            "ids": [69, 70],
            "payload": {"ids_sitio": [69, 70]},
            "nota": "",
            "estado_busqueda": {},
        },
    ]

    candidatos = _candidatos_compactos_llm(cards, estados)

    assert {candidato["id"] for candidato in candidatos} == {69, 70}
    assert 73 not in {candidato["id"] for candidato in candidatos}
