from application.nodes.chatboot_exploracion.utilidades.ejecutar_plan_tools import (
    _candidatos_compactos_llm,
)


def test_candidatos_compactos_llm_incluye_comentario_de_horario():
    cards = [
        {
            "tipo": "card",
            "mensaje": {
                "id_sitio": 10,
                "nombre_sitio": "Museo Test",
                "categoria": "Cultura",
                "subcategoria": "Museo",
            },
        }
    ]
    estados = [
        {
            "herramienta": "horario",
            "orden": 2,
            "status": "ok",
            "ids": [10],
            "payload": {
                "ids_sitio": [10],
                "candidatos": [
                    {
                        "id_sitio": 10,
                        "abierto_24h": False,
                        "horario_texto": "Lun: 09:00-17:00",
                        "comentario": "Atención bajo reservación",
                        "cumplimiento_condicional": True,
                        "criterio_cumplido": True,
                    }
                ],
            },
            "nota": "",
            "estado_busqueda": {},
        }
    ]

    compactos = _candidatos_compactos_llm(cards, estados)

    assert compactos[0]["horario_evidencia"]["comentario"] == "Atención bajo reservación"
    assert compactos[0]["horario_evidencia"]["cumplimiento_condicional"] is True
