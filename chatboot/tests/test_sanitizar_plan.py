from application.shared.sanitizar_plan import (
    sanitizar_plan_exploracion,
    sanitizar_plan_pregunta,
)


def test_exploracion_descarta_categoria_vacia_y_conserva_semantica():
    plan = {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {
                            "nombre": "categoria_subcategoria",
                            "parametros": {
                                "categorias_sugeridas": [],
                                "subcategorias_sugeridas": [],
                                "excluir_categorias": [],
                            },
                        },
                    },
                    {
                        "orden": 2,
                        "herramienta": {
                            "nombre": "busqueda_semantica",
                            "parametros": {
                                "texto_embeddings": "lugares para pesca deportiva",
                                "keywords": ["pesca"],
                                "excluir_terminos": [],
                            },
                        },
                    },
                ]
            }
        ]
    }

    sanitizado, errores = sanitizar_plan_exploracion(plan)

    pasos = sanitizado["consultas"][0]["ejecucion_herramienta"]
    assert [paso["herramienta"]["nombre"] for paso in pasos] == ["busqueda_semantica"]
    assert pasos[0]["orden"] == 1
    assert any(error["tipo"] == "herramienta_invalida" for error in errores)


def test_exploracion_plan_vacio_usa_fallback_amable():
    plan = {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {
                            "nombre": "categoria_subcategoria",
                            "parametros": {
                                "categorias_sugeridas": [],
                                "subcategorias_sugeridas": [],
                            },
                        },
                    }
                ]
            }
        ]
    }

    sanitizado, errores = sanitizar_plan_exploracion(plan)

    herramienta = sanitizado["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]
    assert herramienta["nombre"] == "fallback"
    assert herramienta["parametros"] == {}
    assert any(error["tipo"] == "herramienta_invalida" for error in errores)
    assert any(error["tipo"] == "consulta_sin_herramientas" for error in errores)


def test_exploracion_descarta_herramienta_desconocida():
    plan = {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {
                            "nombre": "herramienta_rara",
                            "parametros": {"x": "y"},
                        },
                    }
                ]
            }
        ]
    }

    sanitizado, errores = sanitizar_plan_exploracion(plan)

    herramienta = sanitizado["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]
    assert herramienta["nombre"] == "fallback"
    assert any(error["tipo"] == "herramienta_invalida" for error in errores)


def test_pregunta_directa_permite_documento_sitio_vacio():
    plan = {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {
                            "nombre": "documento_sitio",
                            "parametros": {},
                        },
                    }
                ]
            }
        ]
    }

    sanitizado, errores = sanitizar_plan_pregunta(plan)

    herramienta = sanitizado["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]
    assert herramienta["nombre"] == "documento_sitio"
    assert errores == []


def test_pregunta_directa_descarta_chuck_documento_vacio():
    plan = {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {
                            "nombre": "chuck_documento",
                            "parametros": {"texto_embeddings": [], "keywords": []},
                        },
                    }
                ]
            }
        ]
    }

    sanitizado, errores = sanitizar_plan_pregunta(plan)

    herramienta = sanitizado["consultas"][0]["ejecucion_herramienta"][0]["herramienta"]
    assert herramienta["nombre"] == "fallback"
    assert any(error["tipo"] == "herramienta_sin_valor" for error in errores)


def test_pregunta_directa_ficha_sin_chuck_sigue_siendo_invalida():
    plan = {
        "consultas": [
            {
                "ejecucion_herramienta": [
                    {
                        "orden": 1,
                        "herramienta": {"nombre": "ficha_sitio", "parametros": {}},
                    }
                ]
            }
        ]
    }

    sanitizado, errores = sanitizar_plan_pregunta(plan)

    assert sanitizado is None
    assert any(error["tipo"] == "regla_prompt_invalida" for error in errores)
