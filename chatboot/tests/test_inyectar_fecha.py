from datetime import datetime, timezone

from application.shared.inyectar_fecha import construir_contexto_temporal


def test_construir_contexto_temporal_inyecta_dia_actual_y_proximos_dias():
    ahora = datetime(2026, 7, 13, 15, 30, tzinfo=timezone.utc)

    contexto = construir_contexto_temporal(ahora, dias_adelante=7)

    assert contexto["fecha_actual"] == "2026-07-13"
    assert contexto["dia_actual"] == "lunes"
    assert contexto["dias"][0]["relativo"] == "hoy"
    assert contexto["dias"][1]["relativo"] == "mañana"
    assert contexto["dias"][1]["dia_semana"] == "martes"
    assert contexto["proxima_ocurrencia"]["lunes"] == "2026-07-13"
    assert contexto["proxima_ocurrencia"]["domingo"] == "2026-07-19"
