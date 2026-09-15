from pydantic import ValidationError

from esquemas.chatboot_exploracion.horario_consulta import HorarioConsultaEntrada


def test_horario_instantaneo_abierto_ahora():
    payload = HorarioConsultaEntrada(
        tipo="instantaneo",
        dia_semana=None,
        dias_semana=None,
        hora=None,
        rango_hora=None,
        comparador="",
        excluir_dias=[],
    )

    assert payload.tipo == "instantaneo"


def test_horario_punto_tiempo_normaliza_hora():
    payload = HorarioConsultaEntrada(
        tipo="punto_tiempo",
        hora="15:00",
        comparador="dentro_de",
    )

    assert payload.hora == "15:00"


def test_horario_bloque_lunes_3pm_acepta_rango_puntual():
    payload = HorarioConsultaEntrada(
        tipo="bloque_tiempo",
        dia_semana=1,
        rango_hora=["15:00", "15:00"],
        comparador="dentro_de",
    )

    assert payload.dia_semana == 1
    assert payload.rango_hora == ["15:00", "15:00"]


def test_horario_relacional_hasta_medianoche():
    payload = HorarioConsultaEntrada(
        tipo="relacional",
        hora="23:59",
        comparador="mayor_que",
    )

    assert payload.hora == "23:59"
    assert payload.comparador == "mayor_que"


def test_horario_rechaza_hora_invalida():
    try:
        HorarioConsultaEntrada(tipo="punto_tiempo", hora="25:00")
    except ValidationError:
        return
    raise AssertionError("Se esperaba ValidationError para hora inválida.")
