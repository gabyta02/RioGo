import asyncio
from unittest.mock import patch

from application.nodes.chatboot_exploracion.herramientas import (
    busqueda_ubicacion,
    gis_consulta,
)
from application.nodes.chatboot_exploracion.utilidades import ejecutar_plan_tools


class ClienteFake:
    def __init__(self, sitios=None):
        self.llamadas = []
        self.sitios = sitios or []

    async def post_herramienta(self, endpoint, payload, timeout_seconds=None):
        self.llamadas.append((endpoint, payload))
        return {"ids_sitio": [1]}

    async def listar_sitios(self):
        return self.sitios

    async def obtener_ficha_sitio(self, id_sitio):
        return {}


def test_busqueda_ubicacion_sin_permiso_no_llama_api():
    cliente = ClienteFake()

    estado, tipo_ids = asyncio.run(
        busqueda_ubicacion.ejecutar(
            orden=2,
            parametros={"usar_ubicacion_usuario": True},
            ids_consulta=[1, 2],
            tipo_ids="sitio",
            state={"ubicacion_usuario": {}},
            cliente=cliente,
        )
    )

    assert estado["status"] == "sin_resultados"
    assert estado["payload"]["motivo"] == "ubicacion_usuario_requerida"
    assert "activa los permisos de ubicación" in estado["nota"]
    assert tipo_ids == "sitio"
    assert cliente.llamadas == []


def test_gis_sin_permiso_no_llama_api():
    cliente = ClienteFake()

    estado, tipo_ids = asyncio.run(
        gis_consulta.ejecutar(
            orden=2,
            parametros={"usar_ubicacion_usuario": True},
            ids_consulta=[1, 2],
            tipo_ids="sitio",
            state={"ubicacion_usuario": {"lat": -1.67}},
            cliente=cliente,
        )
    )

    assert estado["status"] == "sin_resultados"
    assert estado["payload"]["motivo"] == "ubicacion_usuario_requerida"
    assert "activa los permisos de ubicación" in estado["nota"]
    assert tipo_ids == "sitio"
    assert cliente.llamadas == []


def test_ejecutor_conserva_cards_y_agrega_globo_si_falta_ubicacion():
    async def ejecutar_herramienta_fake(**kwargs):
        if kwargs["nombre"] == "busqueda_semantica":
            return (
                {
                    "herramienta": "busqueda_semantica",
                    "orden": kwargs["orden"],
                    "status": "ok",
                    "ids": [1, 2],
                    "payload": {
                        "ids_sitio": [1, 2],
                        "candidatos": [
                            {
                                "id_sitio": 1,
                                "nombre": "Hostal Oasis Rio",
                                "score_final": 0.9,
                                "supera_umbral": True,
                                "contenido_chunk": "Hostal en Riobamba.",
                            },
                            {
                                "id_sitio": 2,
                                "nombre": "Hostal Puertas del Sol",
                                "score_final": 0.8,
                                "supera_umbral": True,
                                "contenido_chunk": "Alojamiento en Riobamba.",
                            },
                        ],
                    },
                    "nota": "",
                    "estado_busqueda": {"estado": "cumplido"},
                },
                "sitio",
            )
        return (
            {
                "herramienta": "busqueda_ubicacion",
                "orden": kwargs["orden"],
                "status": "sin_resultados",
                "ids": [],
                "payload": {
                    "sin_sitios": busqueda_ubicacion.MENSAJE_UBICACION_REQUERIDA,
                    "motivo": "ubicacion_usuario_requerida",
                },
                "nota": busqueda_ubicacion.MENSAJE_UBICACION_REQUERIDA,
                "estado_busqueda": {
                    "estado": "no_cumplido",
                    "retroalimentacion": {"motivo": "ubicacion_usuario_requerida"},
                },
            },
            "sitio",
        )

    state = {
        "plan_valido": True,
        "plan": {
            "consultas": [
                {
                    "ejecucion_herramienta": [
                        {
                            "orden": 1,
                            "herramienta": {
                                "nombre": "busqueda_semantica",
                                "parametros": {"texto_embeddings": "hostal"},
                            },
                        },
                        {
                            "orden": 2,
                            "herramienta": {
                                "nombre": "busqueda_ubicacion",
                                "parametros": {"usar_ubicacion_usuario": True},
                            },
                        },
                    ]
                }
            ]
        },
        "errores_formato": [],
        "ubicacion_usuario": {},
        "texto_usuario": "un hostal cerca de mi ubicacion",
    }

    async def construir_cards_fake(ids_asociados, cliente, estados, *, sitios_cache=None):
        return [
            {
                "tipo": "card",
                "mensaje": {
                    "id_sitio": id_sitio,
                    "nombre_sitio": (
                        "Hostal Oasis Rio"
                        if id_sitio == 1
                        else "Hostal Puertas del Sol"
                    ),
                    "categoria": "Alojamiento",
                    "subcategoria": "Hostal",
                    "direccion": "Centro",
                    "imagen_url": "",
                },
            }
            for id_sitio in ids_asociados
        ]

    async def rankear_fake(*, state, estados, cards, ids_ruta):
        return {
            "mensaje": "No pude ordenar por cercanía, pero estas opciones de hospedaje pueden servirte.",
            "ids_validos": [1, 2],
            "ids_posibles": [],
        }

    with patch.object(
        ejecutar_plan_tools,
        "ejecutar_herramienta",
        ejecutar_herramienta_fake,
    ), patch.object(
        ejecutar_plan_tools,
        "_construir_cards",
        construir_cards_fake,
    ), patch.object(
        ejecutar_plan_tools,
        "_rankear_y_redactar_resultados",
        rankear_fake,
    ):
        salida = asyncio.run(
            ejecutar_plan_tools.ejecutar_plan_exploracion(state)
        )

    assert salida["ids_asociados"][:2] == [1, 2]
    assert len(salida["mensajes_app"]) >= 3
    assert salida["mensajes_app"][0]["tipo"] == "globo"
    assert any(mensaje["tipo"] == "card" for mensaje in salida["mensajes_app"])
    assert "activa los permisos de ubicación" in salida["mensajes_app"][-1]["mensaje"]["texto"]
