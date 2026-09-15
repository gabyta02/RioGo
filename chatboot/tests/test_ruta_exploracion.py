from application.shared.sanitizar_plan import sanitizar_plan_exploracion


def _plan_ruta(tipo_ruta):
    return {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {
                            "nombre": "ruta",
                            "parametros": {
                                "tipo_ruta": tipo_ruta,
                                "excluir_tipos": [],
                            },
                        },
                    }
                ]
            }
        ]
    }


def _plan_semantica(texto):
    return {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {
                            "nombre": "busqueda_semantica",
                            "parametros": {
                                "texto_embeddings": texto,
                                "keywords": [],
                                "excluir_terminos": [],
                            },
                        },
                    }
                ]
            }
        ]
    }


def _plan_fallback_bus():
    return {
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


def test_ruta_senderismo_es_plan_valido():
    plan, errores = sanitizar_plan_exploracion(_plan_ruta("senderismo"))
    herramienta = plan["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]

    assert errores == []
    assert herramienta["nombre"] == "ruta"
    assert herramienta["parametros"]["tipo_ruta"] == "senderismo"


def test_ruta_ciclismo_es_plan_valido():
    plan, errores = sanitizar_plan_exploracion(_plan_ruta("ciclismo"))
    herramienta = plan["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]

    assert errores == []
    assert herramienta["parametros"]["tipo_ruta"] == "ciclismo"


def test_ruta_caminata_urbana_es_plan_valido():
    plan, errores = sanitizar_plan_exploracion(_plan_ruta("caminata urbana"))
    herramienta = plan["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]

    assert errores == []
    assert herramienta["parametros"]["tipo_ruta"] == "caminata urbana"


def test_ruta_bus_debe_ser_fallback_sin_motivo_desde_planificador():
    plan, errores = sanitizar_plan_exploracion(_plan_fallback_bus())
    herramienta = plan["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]

    assert errores == []
    assert herramienta["nombre"] == "fallback"
    assert herramienta["parametros"] == {}


def test_ruta_otro_por_nombre_debe_ser_semantica():
    plan, errores = sanitizar_plan_exploracion(
        _plan_semantica("ruta turistica por nombre o tema especifico")
    )
    herramienta = plan["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]

    assert errores == []
    assert herramienta["nombre"] == "busqueda_semantica"
