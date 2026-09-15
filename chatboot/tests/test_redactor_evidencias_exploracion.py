from application.nodes.chatboot_exploracion.utilidades.ejecutar_plan_tools import (
    _candidatos_compactos_llm,
    _construir_resumen_busqueda,
    _estados_herramientas_redactor,
)


def test_candidato_compacto_incluye_evidencias_precio_tarifa_horario():
    cards = [
        {
            "tipo": "card",
            "mensaje": {
                "id_sitio": 73,
                "nombre_sitio": "Museo Paleontológico de Punín",
                "categoria": "Manifestaciones Culturales",
                "subcategoria": "Museo",
            },
        }
    ]
    estados = [
        {
            "herramienta": "busqueda_semantica",
            "orden": 1,
            "status": "ok",
            "ids": [73],
            "payload": {
                "candidatos": [
                    {
                        "id_sitio": 73,
                        "nombre": "Museo Paleontológico de Punín",
                        "score_final": 0.91,
                        "supera_umbral": True,
                        "contenido_chunk": "Museo con piezas paleontológicas.",
                    }
                ]
            },
            "nota": "",
            "estado_busqueda": {"estado": "cumplido"},
        },
        {
            "herramienta": "tarifa_acceso",
            "orden": 2,
            "status": "ok",
            "ids": [73],
            "payload": {
                "ids_sitio": [73],
                "candidatos": [
                    {
                        "id_sitio": 73,
                        "precio": 1.0,
                        "condicion": "Todo el público",
                        "entrada_gratuita": False,
                        "criterio_cumplido": True,
                    }
                ],
            },
            "nota": "Se filtraron sitios por tarifa de acceso.",
            "estado_busqueda": {"estado": "cumplido"},
        },
        {
            "herramienta": "horario",
            "orden": 3,
            "status": "ok",
            "ids": [73],
            "payload": {
                "ids_sitio": [73],
                "candidatos": [
                    {
                        "id_sitio": 73,
                        "abierto_24h": False,
                        "horario_texto": "Lun-Vie: 09:00-17:00",
                        "dias_semana_resueltos": [1],
                        "hora_consultada": "15:00",
                        "criterio_cumplido": True,
                    }
                ],
            },
            "nota": "Se filtraron sitios por disponibilidad horaria.",
            "estado_busqueda": {"estado": "cumplido"},
        },
        {
            "herramienta": "precio",
            "orden": 4,
            "status": "sin_resultados",
            "ids": [],
            "payload": {"sin_sitios": "Ningún sitio cumple."},
            "nota": "Ningún sitio cumple.",
            "estado_busqueda": {"estado": "no_cumplido"},
        },
    ]

    candidatos = _candidatos_compactos_llm(cards, estados)

    assert candidatos[0]["id"] == 73
    assert candidatos[0]["tarifa_evidencia"]["precio"] == 1.0
    assert candidatos[0]["horario_evidencia"]["hora_consultada"] == "15:00"
    assert "tarifa_acceso" in candidatos[0]["filtros_cumplidos"]
    assert "horario" in candidatos[0]["filtros_cumplidos"]
    assert "precio" in candidatos[0]["filtros_no_confirmados"]


def test_candidato_semantico_sobrevive_si_refinador_no_confirma():
    estados = [
        {
            "herramienta": "busqueda_semantica",
            "orden": 1,
            "status": "ok",
            "ids": [2, 1],
            "payload": {
                "candidatos": [
                    {
                        "id_sitio": 2,
                        "nombre": "Hostal Torre Azul",
                        "score_final": 0.65,
                        "supera_umbral": True,
                        "contenido_chunk": "Hostal con habitaciones cómodas.",
                    },
                    {
                        "id_sitio": 1,
                        "nombre": "Hostal Oasis Río",
                        "score_final": 0.59,
                        "supera_umbral": True,
                        "contenido_chunk": "Alojamiento en Riobamba.",
                    },
                ]
            },
            "nota": "",
            "estado_busqueda": {"estado": "cumplido"},
        },
        {
            "herramienta": "precio",
            "orden": 2,
            "status": "sin_resultados",
            "ids": [],
            "payload": {"sin_sitios": "Ningún sitio cumple con el filtro de precio indicado."},
            "nota": "Ningún sitio cumple con el filtro de precio indicado.",
            "estado_busqueda": {"estado": "no_cumplido"},
        },
    ]

    candidatos = _candidatos_compactos_llm([], estados)

    assert [candidato["id"] for candidato in candidatos[:2]] == [2, 1]
    assert "precio" in candidatos[0]["filtros_no_confirmados"]


def test_candidato_compacto_incluye_evidencia_atributos_gratuito():
    cards = [
        {
            "tipo": "card",
            "mensaje": {
                "id_sitio": 69,
                "nombre_sitio": "Casa Museo de Riobamba",
                "categoria": "Manifestaciones Culturales",
                "subcategoria": "Museo",
            },
        }
    ]
    estados = [
        {
            "herramienta": "busqueda_semantica",
            "orden": 1,
            "status": "ok",
            "ids": [69],
            "payload": {
                "candidatos": [
                    {
                        "id_sitio": 69,
                        "nombre": "Casa Museo de Riobamba",
                        "score_final": 0.9,
                        "supera_umbral": True,
                        "contenido_chunk": "Casa museo de valor cultural.",
                    }
                ]
            },
            "nota": "",
            "estado_busqueda": {"estado": "cumplido"},
        },
        {
            "herramienta": "atributos_booleanos",
            "orden": 2,
            "status": "ok",
            "ids": [69],
            "payload": {"ids_sitio": [69]},
            "nota": "Se filtraron sitios por atributos solicitados.",
            "estado_busqueda": {
                "estado": "cumplido",
                "ids_entrada": [69, 70],
                "ids_salida": [69],
                "filtros": [
                    {
                        "nombre": "atributos_booleanos",
                        "valor": {"es_gratuito": True},
                        "estado": "cumplido",
                        "detalle": "Se filtraron sitios por atributos solicitados.",
                    }
                ],
                "retroalimentacion": {},
            },
        },
    ]

    candidatos = _candidatos_compactos_llm(cards, estados)

    assert candidatos[0]["atributos_evidencia"]["es_gratuito"] is True
    assert candidatos[0]["atributos_evidencia"]["criterio_cumplido"] is True
    assert "atributos_booleanos" in candidatos[0]["filtros_cumplidos"]


def test_estados_herramientas_redactor_incluye_contexto_compacto():
    estados = [
        {
            "herramienta": "busqueda_ubicacion",
            "orden": 2,
            "status": "ok",
            "ids": [1],
            "payload": {"ids_sitio": [1]},
            "nota": "Se encontraron resultados dentro del radio indicado.",
            "estado_busqueda": {
                "estado": "cumplido",
                "ids_entrada": [1, 2],
                "ids_salida": [1],
                "filtros": [
                    {
                        "nombre": "busqueda_ubicacion",
                        "valor": {"distancia": 500, "unidad": "m"},
                        "estado": "cumplido",
                        "detalle": "Radio aplicado.",
                    }
                ],
                "retroalimentacion": {"radio_aplicado_metros": 500},
            },
        }
    ]

    compactos = _estados_herramientas_redactor(estados)

    assert compactos[0]["herramienta"] == "busqueda_ubicacion"
    assert compactos[0]["status"] == "ok"
    assert compactos[0]["estado_busqueda"]["ids_entrada"] == [1, 2]
    assert compactos[0]["estado_busqueda"]["ids_salida"] == [1]
    assert compactos[0]["estado_busqueda"]["filtros"][0]["valor"]["distancia"] == 500


def test_gis_automatico_no_entra_al_contexto_del_redactor():
    estados = [
        {
            "herramienta": "busqueda_semantica",
            "orden": 1,
            "status": "ok",
            "ids": [69],
            "payload": {
                "candidatos": [
                    {
                        "id_sitio": 69,
                        "nombre": "Casa Museo de Riobamba",
                        "score_final": 0.9,
                        "supera_umbral": True,
                        "contenido_chunk": "Museo gratuito en Riobamba.",
                    }
                ]
            },
            "nota": "",
            "estado_busqueda": {"estado": "cumplido"},
        },
        {
            "herramienta": "busqueda_ubicacion",
            "orden": 3,
            "status": "ok",
            "ids": [69],
            "payload": {
                "ids_sitio": [69],
                "_origen": "gis_automatico",
                "candidatos": [
                    {
                        "id_sitio": 69,
                        "nombre": "Casa Museo de Riobamba",
                        "distancia_metros": 320,
                        "distancia_aproximada": "320 m",
                    }
                ],
            },
            "nota": "Se encontraron resultados dentro de aproximadamente 400 m.",
            "estado_busqueda": {
                "estado": "cumplido",
                "ids_entrada": [69],
                "ids_salida": [69],
                "filtros": [
                    {
                        "nombre": "busqueda_ubicacion",
                        "valor": {"usar_ubicacion_usuario": True},
                        "estado": "cumplido",
                        "detalle": "GIS automático.",
                    }
                ],
                "retroalimentacion": {"origen": "gis_automatico"},
            },
        },
    ]
    cards = [
        {
            "tipo": "card",
            "mensaje": {
                "id_sitio": 69,
                "nombre_sitio": "Casa Museo de Riobamba",
                "categoria": "Manifestaciones Culturales",
                "subcategoria": "Museo",
            },
        }
    ]

    candidatos = _candidatos_compactos_llm(cards, estados)
    compactos = _estados_herramientas_redactor(estados)
    resumen = _construir_resumen_busqueda(estados)

    assert candidatos[0]["distancia_metros"] is None
    assert candidatos[0]["distancia_aproximada"] == ""
    assert [estado["herramienta"] for estado in compactos] == ["busqueda_semantica"]
    assert all(
        item["herramienta"] != "busqueda_ubicacion"
        for grupo in resumen.values()
        for item in grupo
    )
