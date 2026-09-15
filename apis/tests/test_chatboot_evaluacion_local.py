from core.chatboot_evaluacion.gis_evaluacion import _esta_excluido_por_zona
from core.chatboot_evaluacion.tarifa_evaluacion import condicion_coincide


def test_exclusion_zona_en_memoria():
    assert _esta_excluido_por_zona("Parque La Concepción", ["concepcion"]) is True
    assert _esta_excluido_por_zona("Museo Central", ["concepcion"]) is False


def test_condicion_coincide_sin_db():
    assert condicion_coincide("adulto mayor", "adulto") is True
    assert condicion_coincide("ninos", "adulto") is False
