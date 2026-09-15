from __future__ import annotations

import asyncio

from application.nodes.chatboot_exploracion.herramientas.cliente_http import (
    ClienteHerramientasHTTP,
)
from application.nodes.chatboot_exploracion.herramientas.registry import (
    ejecutar_herramienta,
)
from application.nodes.chatboot_exploracion.herramientas.pensamiento_fake import (
    construir_guion,
    construir_mensaje_stream,
)
from application.nodes.chatboot_exploracion.utilidades import ejecutar_plan_tools
from application.nodes.chatboot_exploracion.utilidades.ejecutar_plan_tools import (
    _anexar_bloque_ids_asociados,
    _ajustar_auditoria_por_estado_herramientas,
    _construir_contexto_redaccion,
    _construir_cards,
    _extraer_ids_auditados,
    _filtrar_bloques_por_ids,
    _ids_cards_visibles_ordenados,
    _limitar_cards_visibles,
    _seleccionar_resultados_visibles,
    _limpiar_texto_redactor,
)


class ClienteFake:
    def __init__(self, respuestas=None, sitios=None, fichas=None):
        self.respuestas = respuestas or {}
        self.sitios = sitios or []
        self.fichas = fichas or {}
        self.llamadas = []

    async def post_herramienta(self, endpoint, payload, timeout_seconds=None):
        self.llamadas.append((endpoint, payload))
        respuesta = self.respuestas.get(endpoint)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta or {"ids_sitio": [1]}

    async def listar_sitios(self):
        return self.sitios

    async def obtener_ficha_sitio(self, id_sitio):
        return self.fichas.get(id_sitio)


class ClienteFakeSecuencial(ClienteFake):
    async def post_herramienta(self, endpoint, payload, timeout_seconds=None):
        self.llamadas.append((endpoint, payload))
        respuesta = self.respuestas.get(endpoint)
        if isinstance(respuesta, list):
            if not respuesta:
                return {"ids_sitio": []}
            respuesta = respuesta.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta or {"ids_sitio": [1]}


def test_gis_sin_candidatos_no_llama_api():
    cliente = ClienteFake()

    resultado, tipo_ids = asyncio.run(
        ejecutar_herramienta(
            nombre="gis",
            orden=1,
            parametros={"usar_ubicacion_usuario": True},
            ids_consulta=[],
            tipo_ids="sitio",
            state={"ubicacion_usuario": {"lat": -1.0, "lng": -78.0}},
            cliente=cliente,
        )
    )

    assert resultado["status"] == "sin_resultados"
    assert resultado["ids"] == []
    assert tipo_ids == "sitio"
    assert cliente.llamadas == []


def test_ruta_gis_fuerza_entidad_ruta_y_normaliza_ubicacion():
    cliente = ClienteFake(
        {
            "/gis-consulta": {
                "ids_ruta": [4],
                "retroalimentacion": {"mensaje": "Ruta cercana encontrada."},
            }
        }
    )

    resultado, tipo_ids = asyncio.run(
        ejecutar_herramienta(
            nombre="gis",
            orden=2,
            parametros={"usar_ubicacion_usuario": True, "entidad": "sitio"},
            ids_consulta=[4, 5],
            tipo_ids="ruta",
            state={"ubicacion_usuario": {"lat": -1.67, "lng": -78.64}},
            cliente=cliente,
        )
    )

    assert resultado["status"] == "ok"
    assert resultado["ids"] == [4]
    assert tipo_ids == "ruta"
    assert cliente.llamadas[0][1]["entidad"] == "ruta"
    assert cliente.llamadas[0][1]["ubicacion_usuario"] == {
        "lat": -1.67,
        "lon": -78.64,
    }


def test_semantica_timeout_devuelve_mensaje_claro():
    class ClienteTimeout:
        async def post_herramienta(self, endpoint, payload, timeout_seconds=None):
            import httpx

            raise httpx.ReadTimeout("")

    resultado, tipo_ids = asyncio.run(
        ejecutar_herramienta(
            nombre="busqueda_semantica",
            orden=2,
            parametros={"texto_embeddings": "yahuarlocro"},
            ids_consulta=[68],
            tipo_ids="sitio",
            state={},
            cliente=ClienteTimeout(),
        )
    )

    assert resultado["status"] == "error"
    assert tipo_ids is None
    assert resultado["payload"]["fallo"]
    assert "tiempo de espera" in resultado["payload"]["fallo"].lower()
    assert resultado["payload"]["diagnostico_http"]["endpoint"] == "/busqueda-semantica-consulta"
    assert (
        resultado["payload"]["diagnostico_http"]["path"]
        == "/api/v1/chatboot/herramientas/busqueda-semantica-consulta"
    )
    assert resultado["payload"]["diagnostico_http"]["timeout_seconds"] == 90.0
    assert resultado["estado_busqueda"]["filtros"][0]["detalle"]
    assert "diagnostico_http" in resultado["estado_busqueda"]["retroalimentacion"]


def test_semantica_fallback_global_conserva_ids_y_nota():
    cliente = ClienteFake(
        {
            "/busqueda-semantica-consulta": {
                "ids_sitio": [88, 102],
                "retroalimentacion": {
                    "fallback_global_aplicado": True,
                    "mensaje": "Se amplió la búsqueda a todo el catálogo.",
                },
            }
        }
    )

    resultado, tipo_ids = asyncio.run(
        ejecutar_herramienta(
            nombre="busqueda_semantica",
            orden=2,
            parametros={"texto_embeddings": "arte colonial"},
            ids_consulta=[1, 2],
            tipo_ids="sitio",
            state={},
            cliente=cliente,
        )
    )

    assert resultado["status"] == "ok"
    assert resultado["ids"] == [88, 102]
    assert "catálogo" in resultado["nota"]
    assert tipo_ids == "sitio"


def test_pregunta_directa_registrada_ejecuta_http():
    cliente = ClienteFake(
        {
            "/pregunta-directa": {
                "ids_sitio": [69],
                "id_sitio": 69,
                "nombre": "Casa Museo de Riobamba",
                "score": 0.95,
                "mensaje": "Sitio encontrado en la base de datos.",
            }
        }
    )

    resultado, tipo_ids = asyncio.run(
        ejecutar_herramienta(
            nombre="pregunta_directa",
            orden=1,
            parametros={"nombre_entidad": "Casa Museo de Riobamba"},
            ids_consulta=[],
            tipo_ids=None,
            state={},
            cliente=cliente,
        )
    )

    assert resultado["status"] == "ok"
    assert resultado["ids"] == [69]
    assert tipo_ids == "sitio"
    assert cliente.llamadas[0] == (
        "/pregunta-directa",
        {"nombre_entidad": "Casa Museo de Riobamba", "ids_consulta": []},
    )


def test_horario_plan_legacy_invalido_no_llama_api():
    cliente = ClienteFake({"/horario-consulta": {"ids_sitio": [15, 17]}})

    resultado, tipo_ids = asyncio.run(
        ejecutar_herramienta(
            nombre="horario",
            orden=4,
            parametros={
                "tipo": "dias_solamente",
                "dia_semana": None,
                "hora": None,
                "rango_hora": ["12:00", "17:59"],
                "comparador": "dentro_de",
                "excluir_dias": [1, 2, 3, 4, 5],
            },
            ids_consulta=[15, 16, 17, 19],
            tipo_ids="sitio",
            state={},
            cliente=cliente,
        )
    )

    assert resultado["status"] == "error"
    assert tipo_ids is None
    assert cliente.llamadas == []
    assert resultado["estado_busqueda"]["estado"] == "error"


def test_horario_relacional_sin_comparador_no_llama_api():
    cliente = ClienteFake({"/horario-consulta": {"ids_sitio": [15]}})

    resultado, _ = asyncio.run(
        ejecutar_herramienta(
            nombre="horario",
            orden=1,
            parametros={"tipo": "relacional", "hora": "08:00", "comparador": ""},
            ids_consulta=[15, 16],
            tipo_ids="sitio",
            state={"texto_usuario": "Hoteles que abran después de las 8"},
            cliente=cliente,
        )
    )

    assert resultado["status"] == "error"
    assert cliente.llamadas == []
    assert resultado["estado_busqueda"]["estado"] == "error"


def test_horario_relacional_ambiguo_no_degrada_a_punto_tiempo():
    cliente = ClienteFake({"/horario-consulta": {"ids_sitio": [15]}})

    resultado, _ = asyncio.run(
        ejecutar_herramienta(
            nombre="horario",
            orden=1,
            parametros={"tipo": "relacional", "hora": "08:00", "comparador": ""},
            ids_consulta=[15, 16],
            tipo_ids="sitio",
            state={"texto_usuario": "Hoteles a las 8"},
            cliente=cliente,
        )
    )

    assert resultado["status"] == "error"
    assert cliente.llamadas == []
    assert resultado["estado_busqueda"]["estado"] == "error"


def test_horario_relacional_sin_hora_no_llama_api():
    cliente = ClienteFake()

    resultado, _ = asyncio.run(
        ejecutar_herramienta(
            nombre="horario",
            orden=1,
            parametros={"tipo": "relacional", "comparador": ""},
            ids_consulta=[15, 16],
            tipo_ids="sitio",
            state={"texto_usuario": "Hoteles después"},
            cliente=cliente,
        )
    )

    assert resultado["status"] == "error"
    assert cliente.llamadas == []
    assert resultado["estado_busqueda"]["estado"] == "error"


def test_pensamiento_fake_genera_guion_y_mensaje_stream():
    plan = {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {"orden": 1, "herramienta": {"nombre": "categoria_subcategoria"}},
                    {"orden": 2, "herramienta": {"nombre": "gis"}},
                ]
            }
        ]
    }

    guion = construir_guion(plan)
    textos = [item["texto"] for item in guion]
    mensaje = construir_mensaje_stream(
        fase=guion[0]["fase"],
        texto=guion[0]["texto"],
        indice=1,
        total=len(guion),
    )

    assert any("tipo de lugar" in texto for texto in textos)
    assert any("cercanía" in texto for texto in textos)
    assert mensaje["tipo"] == "stream"
    assert mensaje["mensaje"]["origen"] == "pensamiento_fake"


def test_redactor_limpia_cierre_de_pregunta_directa_no_soportada():
    texto = (
        "Aquí tienes algunos museos.\n\n"
        "Si necesitas más detalles sobre alguno, ¡avísame!"
    )

    assert _limpiar_texto_redactor(texto) == "Aquí tienes algunos museos."


def test_candidatos_para_auditor_incluye_todo_el_pipeline():
    from application.nodes.chatboot_exploracion.utilidades.ejecutar_plan_tools import (
        _candidatos_para_auditor,
    )

    estados = [
        {
            "herramienta": "categoria_subcategoria",
            "orden": 1,
            "status": "ok",
            "ids": [31, 32, 53],
            "payload": {},
            "nota": "",
            "estado_busqueda": {},
        },
        {
            "herramienta": "busqueda_semantica",
            "orden": 2,
            "status": "sin_resultados",
            "ids": [],
            "payload": {
                "candidatos": [
                    {
                        "id_sitio": 53,
                        "nombre": "Chimborazo Tours",
                        "score_final": 0.62,
                        "contenido_chunk": "cabalgatas y senderismo",
                        "supera_umbral": False,
                    },
                ]
            },
            "nota": "",
            "estado_busqueda": {},
        },
    ]
    cards = [
        {
            "tipo": "card",
            "mensaje": {
                "id_sitio": 31,
                "nombre_sitio": "La Moya",
                "categoria": "Comunitario",
            },
        },
        {
            "tipo": "card",
            "mensaje": {
                "id_sitio": 32,
                "nombre_sitio": "Palacio Real",
                "categoria": "Comunitario",
            },
        },
        {
            "tipo": "card",
            "mensaje": {
                "id_sitio": 53,
                "nombre_sitio": "Chimborazo Tours",
                "categoria": "Operación",
            },
        },
    ]

    candidatos = _candidatos_para_auditor(cards, estados)
    ids = {item["id_sitio"] for item in candidatos}

    assert ids == {31, 32, 53}
    chimborazo = next(item for item in candidatos if item["id_sitio"] == 53)
    assert "cabalgatas" in chimborazo["contenido_chunk"]


def test_fallback_auditoria_recomienda_ids_si_juez_vacio():
    from application.nodes.chatboot_exploracion.utilidades.ejecutar_plan_tools import (
        _fallback_auditoria,
    )

    candidatos = [
        {"id_sitio": 53, "nombre_sitio": "Chimborazo Tours"},
        {"id_sitio": 32, "nombre_sitio": "Palacio Real"},
    ]
    resultado = _fallback_auditoria(candidatos)

    assert resultado["modo_respuesta"] == "fallback_probable"
    assert resultado["ids_probables"] == [53, 32]


def test_auditoria_degrada_validos_si_semantica_falla():
    auditoria = {
        "ids_validos": [31, 32],
        "ids_probables": [],
        "modo_respuesta": "exacto",
        "motivo": "",
    }
    estados = [
        {
            "herramienta": "categoria_subcategoria",
            "orden": 1,
            "status": "ok",
            "ids": [31, 32],
            "payload": {},
            "nota": "",
        },
        {
            "herramienta": "busqueda_semantica",
            "orden": 2,
            "status": "error",
            "ids": [],
            "payload": {"fallo": "La llamada a la API excedió el tiempo de espera."},
            "nota": "La llamada a la API excedió el tiempo de espera.",
        },
    ]

    resultado = _ajustar_auditoria_por_estado_herramientas(auditoria, estados)

    assert resultado["ids_validos"] == []
    assert resultado["ids_probables"] == [31, 32]
    assert resultado["modo_respuesta"] == "fallback_probable"
    assert "comprobar" in resultado["motivo"].lower()


def test_auditoria_degrada_validos_si_semantica_no_cumple():
    auditoria = {
        "ids_validos": [88],
        "ids_probables": [],
        "modo_respuesta": "exacto",
        "motivo": "",
    }
    estados = [
        {
            "herramienta": "busqueda_semantica",
            "orden": 2,
            "status": "sin_resultados",
            "ids": [],
            "payload": {"sin_sitios": "Sin coincidencias claras."},
            "nota": "Sin coincidencias claras.",
            "estado_busqueda": {
                "estado": "no_cumplido",
                "ids_entrada": [31, 32],
                "ids_salida": [],
                "filtros": [],
                "retroalimentacion": {},
            },
        },
    ]

    resultado = _ajustar_auditoria_por_estado_herramientas(auditoria, estados)

    assert resultado["ids_validos"] == []
    assert resultado["ids_probables"] == [88]
    assert resultado["modo_respuesta"] == "fallback_probable"
    assert "coincidencia clara" in resultado["motivo"].lower()


def test_auditoria_degrada_validos_si_precio_falla():
    auditoria = {
        "ids_validos": [1, 2, 3],
        "ids_probables": [],
        "modo_respuesta": "exacto",
        "motivo": "",
    }
    estados = [
        {
            "herramienta": "categoria_subcategoria",
            "orden": 1,
            "status": "ok",
            "ids": [1, 2, 3],
            "payload": {},
            "nota": "",
        },
        {
            "herramienta": "precio",
            "orden": 2,
            "status": "error",
            "ids": [],
            "payload": {"fallo": "La llamada a la API excedió el tiempo de espera."},
            "nota": "La llamada a la API excedió el tiempo de espera.",
            "estado_busqueda": {
                "estado": "error",
                "ids_entrada": [1, 2, 3],
                "ids_salida": [],
                "filtros": [],
                "retroalimentacion": {},
            },
        },
    ]

    resultado = _ajustar_auditoria_por_estado_herramientas(auditoria, estados)

    assert resultado["ids_validos"] == []
    assert resultado["ids_probables"] == [1, 2, 3]
    assert resultado["modo_respuesta"] == "fallback_probable"
    assert "precio" in resultado["motivo"].lower()


def test_auditor_extrae_ids_validos_y_descarta_inventados():
    respuesta = {"ids_validos": [2, "3", 999, "x"]}

    assert _extraer_ids_auditados(respuesta, [1, 2, 3]) == [2, 3]


def test_auditor_extrae_json_en_bloque_markdown():
    respuesta = '```json\n{"ids_validos":[4,5]}\n```'

    assert _extraer_ids_auditados(respuesta, [4, 5, 6]) == [4, 5]


def test_auditor_usa_probables_si_no_hay_validos():
    respuesta = {
        "ids_validos": [],
        "ids_probables": [7, "8", 999],
        "modo_respuesta": "fallback_probable",
    }

    assert _extraer_ids_auditados(respuesta, [7, 8, 9]) == [7, 8]


def test_filtro_bloques_descarta_cards_no_aprobadas():
    mensajes = [
        {"tipo": "card", "mensaje": {"id_sitio": 1, "nombre_sitio": "Museo"}},
        {"tipo": "ids_asociados", "mensaje": {"ids_asociados": [1]}},
        {"tipo": "card", "mensaje": {"id_sitio": 2, "nombre_sitio": "Parque"}},
        {"tipo": "ids_asociados", "mensaje": {"ids_asociados": [2]}},
    ]

    filtrados = _filtrar_bloques_por_ids(mensajes, [1])

    assert filtrados == [
        {"tipo": "card", "mensaje": {"id_sitio": 1, "nombre_sitio": "Museo"}},
        {"tipo": "ids_asociados", "mensaje": {"ids_asociados": [1]}},
    ]


def test_construir_cards_conserva_todos_los_ids_sin_muestreo():
    cliente = ClienteFake(
        sitios=[
            {"id_sitio": 1, "nombre": "Museo Uno", "categoria": "Cultura"},
            {"id_sitio": 2, "nombre": "Museo Dos", "categoria": "Cultura"},
            {"id_sitio": 3, "nombre": "Museo Tres", "categoria": "Cultura"},
            {"id_sitio": 4, "nombre": "Museo Cuatro", "categoria": "Cultura"},
            {"id_sitio": 5, "nombre": "Museo Cinco", "categoria": "Cultura"},
            {"id_sitio": 6, "nombre": "Museo Seis", "categoria": "Cultura"},
        ]
    )

    cards = asyncio.run(_construir_cards([1, 2, 3, 4, 5, 6], cliente))

    assert [card["mensaje"]["id_sitio"] for card in cards] == [1, 2, 3, 4, 5, 6]


def test_limitar_cards_visibles_conserva_ids_auditados():
    mensajes = [
        {"tipo": "card", "mensaje": {"id_sitio": 1}},
        {"tipo": "card", "mensaje": {"id_sitio": 2}},
        {"tipo": "card", "mensaje": {"id_sitio": 3}},
        {"tipo": "card", "mensaje": {"id_sitio": 4}},
        {"tipo": "card", "mensaje": {"id_sitio": 5}},
        {"tipo": "card", "mensaje": {"id_sitio": 6}},
        {"tipo": "ids_asociados", "mensaje": {"ids_asociados": [1, 2, 3, 4, 5, 6]}},
    ]

    visibles = _limitar_cards_visibles(mensajes, 5)

    assert [m["mensaje"].get("id_sitio") for m in visibles if m["tipo"] == "card"] == [1, 2, 3, 4, 5]
    assert visibles[-1] == {
        "tipo": "ids_asociados",
        "mensaje": {"ids_asociados": [1, 2, 3, 4, 5, 6]},
    }


def test_anexar_bloque_ids_asociados_consolida():
    mensajes = [
        {"tipo": "card", "mensaje": {"id_sitio": 1}},
        {"tipo": "ids_asociados", "mensaje": {"ids_asociados": [1, 2, 3]}},
        {"tipo": "card", "mensaje": {"id_sitio": 4}},
        {"tipo": "ids_asociados", "mensaje": {"ids_asociados": [4, 5]}},
    ]
    ids_juez = list(range(1, 16))

    consolidado = _anexar_bloque_ids_asociados(mensajes, ids_juez)

    bloques_ids = [
        mensaje for mensaje in consolidado if mensaje["tipo"] == "ids_asociados"
    ]
    assert len(bloques_ids) == 1
    assert bloques_ids[0]["mensaje"]["ids_asociados"] == ids_juez
    assert len([m for m in consolidado if m["tipo"] == "card"]) == 2


def test_ids_cards_visibles_ordenados_respeta_orden_juez():
    cards = [
        {"tipo": "card", "mensaje": {"id_sitio": 10}},
        {"tipo": "card", "mensaje": {"id_sitio": 20}},
        {"tipo": "card", "mensaje": {"id_sitio": 30}},
        {"tipo": "card", "mensaje": {"id_sitio": 40}},
        {"tipo": "card", "mensaje": {"id_sitio": 50}},
        {"tipo": "card", "mensaje": {"id_sitio": 60}},
    ]
    ids_juez = [10, 20, 30, 40, 50, 60]

    assert _ids_cards_visibles_ordenados(cards, ids_juez) == [10, 20, 30, 40, 50]


def test_orquestador_juez_15_ids_muestra_5_cards_y_bloque_completo(monkeypatch):
    ids_juez = list(range(1, 16))
    sitios = [
        {"id_sitio": id_sitio, "nombre": f"Museo {id_sitio}", "categoria": "Cultura"}
        for id_sitio in ids_juez
    ]
    cliente = ClienteFake(
        {"/categoria-subcategoria": {"ids_sitio": list(range(1, 21))}},
        sitios=sitios,
    )
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    async def auditor_fake(**_kwargs):
        return {
            "ids_validos": ids_juez,
            "ids_probables": [],
            "modo_respuesta": "exacto",
            "motivo": "",
        }

    async def globo_fake(**kwargs):
        from application.shared.empaquetar_mensaje import construir_globo

        return (
            construir_globo("Texto de prueba", origen="test"),
            kwargs.get("ids_cards_visibles"),
        )

    monkeypatch.setattr(ejecutar_plan_tools, "_auditar_ids_resultados", auditor_fake)
    monkeypatch.setattr(ejecutar_plan_tools, "_construir_globo_final", globo_fake)

    state = {
        "sesion_id": "s1",
        "client_message_id": "c1",
        "ubicacion_usuario": None,
        "texto_usuario": "museos",
        "score_prompt_inyection": 0.0,
        "palabras_inyectadas": [],
        "memoria": {"turnos": [], "entidades": []},
        "prompt_clasificacion": "",
        "respuesta_llm_cruda": "",
        "plan": {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "categoria_subcategoria",
                                "parametros": {"subcategorias_sugeridas": ["Museo"]},
                            },
                        },
                    ]
                }
            ]
        },
        "plan_valido": True,
        "errores_formato": [],
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_exploracion": None,
    }

    salida = asyncio.run(ejecutar_plan_tools.ejecutar_plan_exploracion(state))
    cards = [mensaje for mensaje in salida["mensajes_app"] if mensaje["tipo"] == "card"]
    bloques_ids = [
        mensaje for mensaje in salida["mensajes_app"] if mensaje["tipo"] == "ids_asociados"
    ]

    assert salida["ids_asociados"] == ids_juez
    assert salida["resultado_exploracion"]["ids_asociados"] == ids_juez
    assert len(cards) == 5
    assert [card["mensaje"]["id_sitio"] for card in cards] == [1, 2, 3, 4, 5]
    assert len(bloques_ids) == 1
    assert bloques_ids[0]["mensaje"]["ids_asociados"] == ids_juez


def test_orquestador_conserva_fallback_de_intencion_independiente(monkeypatch):
    cliente = ClienteFake(
        {
            "/busqueda-semantica-consulta": {
                "ids_sitio": [53],
                "candidatos": [
                    {
                        "id_sitio": 53,
                        "nombre": "Chimborazo Tours",
                        "keywords_match": ["cabalgata"],
                        "supera_umbral": True,
                    }
                ],
            }
        },
        sitios=[
            {
                "id_sitio": 53,
                "nombre": "Chimborazo Tours",
                "categoria": "Operación e intermediación",
            }
        ],
    )
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    async def auditor_fake(**_kwargs):
        return {
            "ids_validos": [53],
            "ids_probables": [],
            "modo_respuesta": "exacto",
            "motivo": "",
        }

    async def globo_fake(**kwargs):
        from application.shared.empaquetar_mensaje import construir_globo

        return construir_globo("Resultado listo", origen="test"), kwargs.get("ids_cards_visibles")

    monkeypatch.setattr(ejecutar_plan_tools, "_auditar_ids_resultados", auditor_fake)
    monkeypatch.setattr(ejecutar_plan_tools, "_construir_globo_final", globo_fake)

    state = {
        "sesion_id": "s1",
        "client_message_id": "c1",
        "ubicacion_usuario": None,
        "texto_usuario": "quiero un hotel barato y algo para hacer",
        "score_prompt_inyection": 0.0,
        "palabras_inyectadas": [],
        "memoria": {"turnos": [], "entidades": []},
        "prompt_clasificacion": "",
        "respuesta_llm_cruda": "",
        "plan": {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "busqueda_semantica",
                                "parametros": {
                                    "texto_embeddings": "montar a caballo cabalgata",
                                    "keywords": ["cabalgata"],
                                },
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
                                "parametros": {
                                    "motivo": "sin_intencion_clara",
                                    "pregunta_sugerida": "¿Qué tipo de actividad te interesa?",
                                    "subcategorias_sugeridas": [
                                        "Centro de turismo comunitario",
                                        "Operadora de Turismo",
                                    ],
                                },
                            },
                        }
                    ]
                },
            ]
        },
        "plan_valido": True,
        "errores_formato": [],
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_exploracion": None,
    }

    salida = asyncio.run(ejecutar_plan_tools.ejecutar_plan_exploracion(state))

    tipos = [mensaje["tipo"] for mensaje in salida["mensajes_app"]]
    textos = [
        mensaje.get("mensaje", {}).get("texto", "")
        for mensaje in salida["mensajes_app"]
        if isinstance(mensaje, dict)
    ]
    assert "opciones" in tipos
    assert any("actividad" in texto for texto in textos)
    assert salida["ids_asociados"] == [53]


def test_seleccionar_resultados_visibles_usa_primeros_en_orden():
    resultados = [{"id_sitio": item, "nombre_sitio": f"Sitio {item}"} for item in range(1, 8)]

    visibles = _seleccionar_resultados_visibles(resultados, 5)

    assert [item["id_sitio"] for item in visibles] == [1, 2, 3, 4, 5]


def test_seleccionar_resultados_visibles_conserva_bloques():
    resultados = [
        {"id_sitio": 69, "nombre_sitio": "Casa Museo"},
        {"id_sitio": 70, "nombre_sitio": "Museo Centro"},
        {"id_sitio": 71, "nombre_sitio": "Museo Madres"},
        {"id_sitio": 72, "nombre_sitio": "Museo Militar"},
        {"id_sitio": 73, "nombre_sitio": "Museo Paleontologico"},
        {"id_sitio": 74, "nombre_sitio": "Parque Ricpamba"},
        {"id_sitio": 75, "nombre_sitio": "Parque Ecologico"},
    ]
    bloques_app = [
        *[{"tipo": "card", "mensaje": {"id_sitio": item}} for item in [69, 70, 71, 72, 73]],
        {"tipo": "ids_asociados", "mensaje": {"ids_asociados": [69, 70, 71, 72, 73]}},
        *[{"tipo": "card", "mensaje": {"id_sitio": item}} for item in [74, 75]],
        {"tipo": "ids_asociados", "mensaje": {"ids_asociados": [74, 75]}},
    ]

    visibles = _seleccionar_resultados_visibles(
        resultados,
        5,
        bloques_app=bloques_app,
    )

    ids_visibles = [item["id_sitio"] for item in visibles]
    assert len(ids_visibles) == 5
    assert any(id_sitio in ids_visibles for id_sitio in [69, 70, 71, 72, 73])
    assert any(id_sitio in ids_visibles for id_sitio in [74, 75])


def test_orquestador_propaga_ids_y_construye_cards(monkeypatch):
    cliente = ClienteFake(
        {
            "/categoria-subcategoria": {"ids_sitio": [1, 2, 3]},
            "/horario-consulta": {"ids_sitio": [2, 3]},
        },
        sitios=[
            {"id_sitio": 1, "nombre": "Uno", "categoria": "Museo"},
            {
                "id_sitio": 2,
                "nombre": "Dos",
                "categoria": "Museo",
                "direccion": "Av. Jose Veloz",
                "img_Url": "/api/v1/imagenes/dos.jpg",
            },
            {"id_sitio": 3, "nombre": "Tres", "categoria": "Museo"},
        ],
    )
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    state = {
        "sesion_id": "s1",
        "client_message_id": "c1",
        "ubicacion_usuario": {"lat": -1, "lng": -78},
        "texto_usuario": "museos abiertos",
        "score_prompt_inyection": 0.0,
        "palabras_inyectadas": [],
        "memoria": {"turnos": [], "entidades": []},
        "prompt_clasificacion": "",
        "respuesta_llm_cruda": "",
        "plan": {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "categoria_subcategoria",
                                "parametros": {"subcategorias_sugeridas": ["Museo"]},
                            },
                        },
                        {
                            "orden": 2,
                            "herramienta": {
                                "nombre": "horario",
                                "parametros": {"tipo": "instantaneo"},
                            },
                        },
                    ]
                }
            ]
        },
        "plan_valido": True,
        "errores_formato": [],
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_exploracion": None,
    }

    salida = asyncio.run(ejecutar_plan_tools.ejecutar_plan_exploracion(state))

    assert cliente.llamadas[1][1]["ids_consulta"] == [1, 2, 3]
    assert salida["ids_asociados"] == [2, 3]
    assert salida["resultado_exploracion"]["ids_asociados"] == [2, 3]
    assert any(mensaje["tipo"] == "card" for mensaje in salida["mensajes_app"])
    card_dos = next(
        mensaje
        for mensaje in salida["mensajes_app"]
        if mensaje["tipo"] == "card" and mensaje["mensaje"]["nombre_sitio"] == "Dos"
    )
    assert card_dos["mensaje"]["direccion"] == "Av. Jose Veloz"
    assert card_dos["mensaje"]["imagen_url"] == "/api/v1/imagenes/dos.jpg"


def test_orquestador_usa_un_globo_y_separa_cards_por_consulta(monkeypatch):
    cliente = ClienteFakeSecuencial(
        {
            "/categoria-subcategoria": [
                {"ids_sitio": [1]},
                {"ids_sitio": [2]},
            ],
        },
        sitios=[
            {
                "id_sitio": 1,
                "nombre": "Museo Familiar",
                "categoria": "Manifestaciones Culturales",
                "direccion": "Centro historico",
            },
            {
                "id_sitio": 2,
                "nombre": "Parque Picnic",
                "categoria": "Sitios Naturales",
                "direccion": "Sector norte",
            },
        ],
    )
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    state = {
        "sesion_id": "s1",
        "client_message_id": "c1",
        "ubicacion_usuario": None,
        "texto_usuario": (
            "necesito un museo para visitar en familia, tambien necesito "
            "un parque para realizar un picnic familiar"
        ),
        "score_prompt_inyection": 0.0,
        "palabras_inyectadas": [],
        "memoria": {"turnos": [], "entidades": []},
        "prompt_clasificacion": "",
        "respuesta_llm_cruda": "",
        "plan": {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "categoria_subcategoria",
                                "parametros": {"subcategorias_sugeridas": ["Museo"]},
                            },
                        },
                    ]
                },
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "categoria_subcategoria",
                                "parametros": {"subcategorias_sugeridas": ["Parque"]},
                            },
                        },
                    ]
                },
            ]
        },
        "plan_valido": True,
        "errores_formato": [],
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_exploracion": None,
    }

    salida = asyncio.run(ejecutar_plan_tools.ejecutar_plan_exploracion(state))
    mensajes = salida["mensajes_app"]
    indices_globo = [
        indice for indice, mensaje in enumerate(mensajes) if mensaje["tipo"] == "globo"
    ]
    indice_museo = next(
        indice
        for indice, mensaje in enumerate(mensajes)
        if mensaje["tipo"] == "card"
        and mensaje["mensaje"]["nombre_sitio"] == "Museo Familiar"
    )
    indice_parque = next(
        indice
        for indice, mensaje in enumerate(mensajes)
        if mensaje["tipo"] == "card"
        and mensaje["mensaje"]["nombre_sitio"] == "Parque Picnic"
    )
    indices_ids = [
        indice
        for indice, mensaje in enumerate(mensajes)
        if mensaje["tipo"] == "ids_asociados"
    ]

    assert salida["ids_asociados"] == [1, 2]
    assert len(indices_globo) == 1
    assert len(indices_ids) == 1
    assert mensajes[indices_ids[0]]["mensaje"]["ids_asociados"] == [1, 2]
    assert indices_globo[0] < indice_museo < indice_parque < indices_ids[0]


def test_orquestador_completa_card_desde_ficha_si_resumen_no_trae_direccion(monkeypatch):
    cliente = ClienteFake(
        {
            "/categoria-subcategoria": {"ids_sitio": [69]},
        },
        sitios=[
            {
                "id_sitio": 69,
                "nombre": "Casa Museo de Riobamba",
                "categoria": "Manifestaciones Culturales",
            },
        ],
        fichas={
            69: {
                "direccion": "Av. 11 de Noviembre Y Demetrio Aguilera Malta",
                "imagenes": [
                    {"url": "/api/v1/imagenes/secundaria.jpg", "es_principal": False},
                    {"url": "/api/v1/imagenes/principal.jpg", "es_principal": True},
                ],
            }
        },
    )
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    state = {
        "sesion_id": "s1",
        "client_message_id": "c1",
        "ubicacion_usuario": None,
        "texto_usuario": "museos",
        "score_prompt_inyection": 0.0,
        "palabras_inyectadas": [],
        "memoria": {"turnos": [], "entidades": []},
        "prompt_clasificacion": "",
        "respuesta_llm_cruda": "",
        "plan": {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "categoria_subcategoria",
                                "parametros": {"subcategorias_sugeridas": ["Museo"]},
                            },
                        },
                    ]
                }
            ]
        },
        "plan_valido": True,
        "errores_formato": [],
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_exploracion": None,
    }

    salida = asyncio.run(ejecutar_plan_tools.ejecutar_plan_exploracion(state))
    card = next(mensaje for mensaje in salida["mensajes_app"] if mensaje["tipo"] == "card")

    assert card["mensaje"]["direccion"] == "Av. 11 de Noviembre Y Demetrio Aguilera Malta"
    assert card["mensaje"]["imagen_url"] == "/api/v1/imagenes/principal.jpg"


def test_orquestador_pasa_distancias_gis_solo_al_contexto_redactor(monkeypatch):
    cliente = ClienteFake(
        {
            "/categoria-subcategoria": {"ids_sitio": [10, 20]},
            "/gis-consulta": {
                "ids_sitio": [20],
                "candidatos": [
                    {
                        "id_sitio": 20,
                        "nombre": "Hotel Cercano",
                        "distancia_metros": 320.4,
                        "distancia_aproximada": "320 m",
                    }
                ],
                "retroalimentacion": {
                    "codigo": "encontrado_en_radio_progresivo",
                    "modo_busqueda": "progresivo",
                    "radio_aplicado_metros": 500,
                    "radios_intentados_metros": [500],
                    "mensaje": "Se encontraron resultados dentro de aproximadamente 500 m.",
                },
            },
        },
        sitios=[
            {
                "id_sitio": 20,
                "nombre": "Hotel Cercano",
                "categoria": "Alojamiento",
                "direccion": "Av. Primera Constituyente",
            }
        ],
    )
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    state = {
        "sesion_id": "s1",
        "client_message_id": "c1",
        "ubicacion_usuario": {"lat": -1.67, "lng": -78.65},
        "texto_usuario": "hotel con wifi cerca de mi ubicación",
        "score_prompt_inyection": 0.0,
        "palabras_inyectadas": [],
        "memoria": {"turnos": [], "entidades": []},
        "prompt_clasificacion": "",
        "respuesta_llm_cruda": "",
        "plan": {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "categoria_subcategoria",
                                "parametros": {"subcategorias_sugeridas": ["Hotel"]},
                            },
                        },
                        {
                            "orden": 2,
                            "herramienta": {
                                "nombre": "gis",
                                "parametros": {"usar_ubicacion_usuario": True},
                            },
                        },
                    ]
                }
            ]
        },
        "plan_valido": True,
        "errores_formato": [],
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_exploracion": None,
    }

    salida = asyncio.run(ejecutar_plan_tools.ejecutar_plan_exploracion(state))
    card = next(mensaje for mensaje in salida["mensajes_app"] if mensaje["tipo"] == "card")
    contexto = _construir_contexto_redaccion(
        salida["estados_herramientas"],
        [card],
    )

    assert "distancia_aproximada" not in card["mensaje"]
    assert "distancia_metros" not in card["mensaje"]
    assert contexto["distancias_gis"][0]["distancia_aproximada"] == "320 m"
    estado_gis = next(
        item for item in contexto["estados_api"] if item["herramienta"] == "gis"
    )
    assert estado_gis["candidatos_con_distancia"][0]["distancia_metros"] == 320.4


def test_orquestador_pregunta_directa_genera_globo_accion_y_no_cards(monkeypatch):
    cliente = ClienteFake(
        {
            "/pregunta-directa": {
                "ids_sitio": [69],
                "id_sitio": 69,
                "nombre": "Casa Museo de Riobamba",
                "score": 0.96,
                "mensaje": "Sitio encontrado en la base de datos.",
            }
        },
        sitios=[
            {
                "id_sitio": 69,
                "nombre": "Casa Museo de Riobamba",
                "categoria": "Manifestaciones Culturales",
            }
        ],
    )
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    salida = asyncio.run(
        ejecutar_plan_tools.ejecutar_plan_exploracion(
            _state_pregunta_directa("Casa Museo de Riobamba")
        )
    )

    tipos = [mensaje["tipo"] for mensaje in salida["mensajes_app"]]
    assert tipos == ["globo", "accion"]
    assert salida["ids_asociados"] == [69]
    assert salida["entidades_resueltas"] == ["Casa Museo de Riobamba"]
    assert "chatbot específico" in salida["mensajes_app"][0]["mensaje"]["texto"]
    assert salida["mensajes_app"][1]["mensaje"] == {
        "accion": "abrir_chatbot_sitio",
        "label": "Abrir chatbot del sitio",
        "id_sitio": 69,
        "nombre_sitio": "Casa Museo de Riobamba",
    }
    assert "card" not in tipos


def test_orquestador_pregunta_directa_sin_sitio_genera_globo_sin_accion(monkeypatch):
    cliente = ClienteFake(
        {
            "/pregunta-directa": {
                "sin_sitios": "No encontré un sitio activo con suficiente coincidencia para esa entidad."
            }
        }
    )
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    salida = asyncio.run(
        ejecutar_plan_tools.ejecutar_plan_exploracion(_state_pregunta_directa("Museo raro"))
    )

    assert [mensaje["tipo"] for mensaje in salida["mensajes_app"]] == ["globo"]
    assert salida["ids_asociados"] == []
    assert "sitio registrado parecido" in salida["mensajes_app"][0]["mensaje"]["texto"]


def test_orquestador_pregunta_directa_confianza_media_muestra_sugerencias(monkeypatch):
    cliente = ClienteFake(
        {
            "/pregunta-directa": {
                "sin_sitios": "Encontré sitios parecidos, pero necesito que confirmes a cuál te refieres.",
                "sugerencias": [
                    {
                        "ids_sitio": [72],
                        "id_sitio": 72,
                        "nombre": "Museo y Centro Cultural de Riobamba",
                        "score": 0.72,
                        "mensaje": "Coincidencia aproximada registrada.",
                    },
                    {
                        "ids_sitio": [73],
                        "id_sitio": 73,
                        "nombre": "Casa Museo de Riobamba",
                        "score": 0.61,
                        "mensaje": "Coincidencia aproximada registrada.",
                    },
                ],
            }
        }
    )
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    salida = asyncio.run(
        ejecutar_plan_tools.ejecutar_plan_exploracion(_state_pregunta_directa("museo riobamba"))
    )

    assert [mensaje["tipo"] for mensaje in salida["mensajes_app"]] == ["globo", "opciones"]
    assert "Quizás te refieres" in salida["mensajes_app"][0]["mensaje"]["texto"]
    assert salida["mensajes_app"][1]["mensaje"]["opciones"] == [
        "Museo y Centro Cultural de Riobamba",
        "Casa Museo de Riobamba",
    ]
    assert salida["ids_asociados"] == [72, 73]


def test_orquestador_pregunta_directa_error_http_genera_fallback_suave(monkeypatch):
    cliente = ClienteFake({"/pregunta-directa": RuntimeError("HTTP 500")})
    monkeypatch.setattr(ejecutar_plan_tools, "ClienteHerramientasHTTP", lambda: cliente)

    salida = asyncio.run(
        ejecutar_plan_tools.ejecutar_plan_exploracion(_state_pregunta_directa("Casa Museo"))
    )

    assert [mensaje["tipo"] for mensaje in salida["mensajes_app"]] == ["globo"]
    assert salida["estados_herramientas"][0]["status"] == "error"
    assert "No pude consultar" in salida["mensajes_app"][0]["mensaje"]["texto"]


def _state_pregunta_directa(nombre_entidad):
    return {
        "sesion_id": "s1",
        "client_message_id": "c1",
        "ubicacion_usuario": None,
        "texto_usuario": f"Háblame de {nombre_entidad}",
        "score_prompt_inyection": 0.0,
        "palabras_inyectadas": [],
        "memoria": {"turnos": [], "entidades": []},
        "prompt_clasificacion": "",
        "respuesta_llm_cruda": "",
        "plan": {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "pregunta_directa",
                                "parametros": {"nombre_entidad": nombre_entidad},
                            },
                        },
                    ]
                }
            ]
        },
        "plan_valido": True,
        "errores_formato": [],
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_exploracion": None,
    }
