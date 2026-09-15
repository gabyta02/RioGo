from datetime import time

from core.horario_evaluacion import filtrar_sitios_por_horario
from esquemas.horario_consulta import HorarioConsultaEntrada
from servicios.horario_consulta import consultar_sitios_por_horario


def _sitios_map():
    return {
        1: {
            "id_sitio": 1,
            "abierto_24h": False,
            "comentario": "Atención bajo reservación",
            "detalles": [
                {"dia_semana": 6, "hora_inicio": time(13, 0), "hora_fin": time(16, 0)}
            ],
        },
        2: {
            "id_sitio": 2,
            "abierto_24h": False,
            "comentario": None,
            "detalles": [
                {"dia_semana": 1, "hora_inicio": time(13, 0), "hora_fin": time(16, 0)}
            ],
        },
        3: {
            "id_sitio": 3,
            "abierto_24h": False,
            "comentario": None,
            "detalles": [
                {"dia_semana": 7, "hora_inicio": time(9, 0), "hora_fin": time(11, 0)}
            ],
        },
        4: {"id_sitio": 4, "abierto_24h": True, "comentario": None, "detalles": []},
    }


def test_bloque_tiempo_con_dias_semana_filtra_fin_de_semana_tarde():
    ids = filtrar_sitios_por_horario(
        _sitios_map(),
        "bloque_tiempo",
        None,
        None,
        time(12, 0),
        time(17, 59),
        "dentro_de",
        [],
        dias_semana=[6, 7],
    )

    assert ids == [1, 4]


def test_dias_solamente_con_dias_semana_filtra_sabado_o_domingo():
    ids = filtrar_sitios_por_horario(
        _sitios_map(),
        "dias_solamente",
        None,
        None,
        None,
        None,
        "",
        [],
        dias_semana=[6, 7],
    )

    assert ids == [1, 3, 4]


def test_dias_solamente_sin_dia_ni_dias_devuelve_fallo():
    salida = consultar_sitios_por_horario(
        object(),
        HorarioConsultaEntrada(tipo="dias_solamente"),
    )

    assert salida.fallo == "El tipo 'dias_solamente' requiere dia_semana (1-7) o dias_semana."
    assert salida.estado_busqueda.estado == "error"
    assert salida.estado_busqueda.filtros[0].nombre == "horario"


def test_bloque_tiempo_sin_rango_hora_sigue_fallando():
    salida = consultar_sitios_por_horario(
        object(),
        HorarioConsultaEntrada(tipo="bloque_tiempo", dias_semana=[6, 7]),
    )

    assert salida.fallo == "El tipo 'bloque_tiempo' requiere rango_hora con dos valores HH:MM."
    assert salida.estado_busqueda.estado == "error"


def test_excluir_dias_se_mantiene_como_exclusion_real():
    ids = filtrar_sitios_por_horario(
        _sitios_map(),
        "dias_solamente",
        None,
        None,
        None,
        None,
        "",
        [6],
        dias_semana=[6, 7],
    )

    assert ids == [3]


def test_horario_respuesta_incluye_estado_busqueda_ok(monkeypatch):
    monkeypatch.setattr(
        "servicios.horario_consulta.obtener_horarios_sitios",
        lambda db, ids: _sitios_map(),
    )

    salida = consultar_sitios_por_horario(
        object(),
        HorarioConsultaEntrada(
            tipo="dias_solamente",
            dias_semana=[6, 7],
            ids_consulta=[1, 2, 3, 4],
        ),
    )

    assert salida.ids_sitio == [1, 3, 4]
    assert salida.estado_busqueda.estado == "cumplido"
    assert salida.estado_busqueda.ids_entrada == [1, 2, 3, 4]
    assert salida.estado_busqueda.ids_salida == [1, 3, 4]
    assert [candidato.id_sitio for candidato in salida.candidatos] == [1, 3, 4]
    assert salida.candidatos[0].horario_texto == "Sáb: 13:00-16:00"
    assert salida.candidatos[0].comentario == "Atención bajo reservación"
    assert salida.candidatos[0].dias_semana_resueltos == [6, 7]
    assert salida.candidatos[0].criterio_cumplido is True


def test_horario_con_comentario_reservacion_cumple_condicionalmente(monkeypatch):
    monkeypatch.setattr(
        "servicios.horario_consulta.obtener_horarios_sitios",
        lambda db, ids: {
            10: {
                "id_sitio": 10,
                "abierto_24h": False,
                "comentario": "Atención bajo reservación",
                "detalles": [],
            }
        },
    )

    salida = consultar_sitios_por_horario(
        object(),
        HorarioConsultaEntrada(
            tipo="dias_solamente",
            dia_semana=2,
            ids_consulta=[10],
        ),
    )

    assert salida.ids_sitio == [10]
    assert salida.candidatos[0].comentario == "Atención bajo reservación"
    assert salida.candidatos[0].cumplimiento_condicional is True
    assert salida.candidatos[0].criterio_cumplido is True
