from pydantic import ValidationError

from esquemas.chatboot_exploracion.precio_consulta import PrecioConsultaEntrada
from esquemas.chatboot_exploracion.tarifa_acceso_consulta import (
    TarifaAccesoConsultaEntrada,
)
from core.chatboot_evaluacion.tarifa_evaluacion import (
    condicion_coincide,
    filtrar_sitios_por_tarifa,
    normalizar_condicion,
)
from servicios.chatboot_exploracion import precio_consulta, tarifa_acceso_consulta


def test_precio_normaliza_moderado_a_medio():
    payload = PrecioConsultaEntrada(etiqueta="moderado")

    assert payload.etiqueta == "medio"


def test_precio_acepta_operador_maximo():
    payload = PrecioConsultaEntrada(precio_numero=80, operador="<=")

    assert payload.precio_numero == 80
    assert payload.operador == "<="


def test_tarifa_normaliza_moderado_a_medio():
    payload = TarifaAccesoConsultaEntrada(etiqueta="moderado")

    assert payload.etiqueta == "medio"


def test_tarifa_acepta_un_dolar_estudiante():
    payload = TarifaAccesoConsultaEntrada(
        precio_numero=1,
        operador="=",
        condicion="estudiante",
    )

    assert payload.precio_numero == 1
    assert payload.operador == "="
    assert payload.condicion == "estudiante"


def test_tarifa_rechaza_condicion_no_catalogada():
    try:
        TarifaAccesoConsultaEntrada(condicion="vip")
    except ValidationError:
        return
    raise AssertionError("Se esperaba ValidationError para condicion no catalogada.")


def test_tarifa_todo_el_publico_equivale_a_general():
    assert normalizar_condicion("Todo el público") == "general"
    assert condicion_coincide("Todo el público", "general") is True
    assert condicion_coincide("general", "Todo el público") is True


def test_tarifa_un_dolar_general_incluye_todo_el_publico():
    ids = filtrar_sitios_por_tarifa(
        db=None,
        tarifas_por_sitio={
            73: [{"precio": 1.0, "condicion": "Todo el público"}],
            71: [{"precio": 1.5, "condicion": "Estudiantes"}],
        },
        entrada_gratuita=None,
        etiqueta="economico",
        precio_numero=1.0,
        operador="min",
        condicion="general",
        condiciones_excluidas=[],
    )

    assert ids == [73]


def test_precio_respuesta_incluye_candidatos_con_evidencia(monkeypatch):
    monkeypatch.setattr(
        precio_consulta,
        "obtener_datos_precio_sitios",
        lambda db, ids: {
            10: {
                "es_gratuito": False,
                "rangos": [
                    {
                        "precio_min": 40.0,
                        "precio_max": 80.0,
                        "etiqueta_precio": "medio",
                    }
                ],
            }
        },
    )

    salida = precio_consulta.consultar_sitios_por_precio(
        object(),
        PrecioConsultaEntrada(precio_numero=80, operador="<=", ids_consulta=[10]),
    )

    assert salida.ids_sitio == [10]
    assert salida.candidatos[0].id_sitio == 10
    assert salida.candidatos[0].precio_max == 80.0
    assert salida.candidatos[0].criterio_cumplido is True


def test_tarifa_respuesta_incluye_candidatos_con_evidencia(monkeypatch):
    monkeypatch.setattr(
        tarifa_acceso_consulta,
        "obtener_datos_tarifa_sitios",
        lambda db, ids: {
            73: [{"precio": 1.0, "condicion": "Todo el público"}],
        },
    )

    salida = tarifa_acceso_consulta.consultar_sitios_por_tarifa_acceso(
        object(),
        TarifaAccesoConsultaEntrada(
            precio_numero=1,
            operador="<=",
            condicion="general",
            ids_consulta=[73],
        ),
    )

    assert salida.ids_sitio == [73]
    assert salida.candidatos[0].id_sitio == 73
    assert salida.candidatos[0].precio == 1.0
    assert salida.candidatos[0].condicion == "Todo el público"
    assert salida.candidatos[0].criterio_cumplido is True
