from core.chatboot_evaluacion.gis_evaluacion import (
    _coordenadas_interseccion_aproximada,
    _referencia_catalogo_equivalente,
    radios_a_intentar,
    resolver_distancia_metros,
)
from esquemas.chatboot_exploracion.busqueda_ubicacion import BusquedaUbicacionEntrada
from esquemas.chatboot_exploracion.gis_consulta import GisConsultaEntrada


def test_referencia_catalogo_equivalente_no_confunde_mercados_distintos():
    assert (
        _referencia_catalogo_equivalente(
            "mercado la condamine",
            "Mercado de La Merced",
        )
        is False
    )
    assert (
        _referencia_catalogo_equivalente(
            "parque sucre",
            "Parque Sucre",
        )
        is True
    )
    assert (
        _referencia_catalogo_equivalente(
            "museo de las madres conceptas",
            "Museo de las Madres Conceptas de Riobamba",
        )
        is True
    )


def test_gis_schema_acepta_punto_referencia_osm():
    payload = GisConsultaEntrada(
        entidad="sitio",
        usar_ubicacion_usuario=False,
        distancia=None,
        unidad="",
        punto_referencia="mercado la condamine",
        excluir_zonas=[],
        ids_consulta=[1, 2, 3],
    )

    assert payload.punto_referencia == "mercado la condamine"
    assert payload.ubicacion_usuario is None


def test_gis_schema_acepta_ubicacion_usuario_central():
    payload = GisConsultaEntrada(
        entidad="sitio",
        usar_ubicacion_usuario=True,
        distancia=400,
        unidad="m",
        punto_referencia="",
        excluir_zonas=[],
        ubicacion_usuario={"lat": -1.6736, "lon": -78.6473},
        ids_consulta=[10, 11],
    )

    assert payload.ubicacion_usuario is not None
    assert payload.ubicacion_usuario.coordenadas() == {
        "lat": -1.6736,
        "lon": -78.6473,
    }


def test_gis_radio_fijo_y_progresivo():
    assert resolver_distancia_metros(1, "km") == 1000.0
    assert resolver_distancia_metros(400, "m") == 400
    assert radios_a_intentar(None, "") == [500.0, 1000.0, 1500.0]
    assert radios_a_intentar(5, "km") == [1500.0]


def test_busqueda_ubicacion_schema_acepta_zona_textual():
    payload = BusquedaUbicacionEntrada(
        entidad="sitio",
        tipo_busqueda="zona_textual",
        referencia_ubicacion="Leopoldo Ormaza y Agustín Cascante",
        ids_consulta=[1, 2],
    )

    assert payload.tipo_busqueda == "zona_textual"
    assert payload.referencia_ubicacion == "Leopoldo Ormaza y Agustín Cascante"


def test_busqueda_ubicacion_schema_acepta_cercania_osm():
    payload = BusquedaUbicacionEntrada(
        entidad="sitio",
        tipo_busqueda="cercania",
        referencia_ubicacion="Guayaquil y Cristobal Colón",
        usar_ubicacion_usuario=False,
        distancia=None,
        unidad="",
        ids_consulta=[1, 2],
    )

    assert payload.tipo_busqueda == "cercania"
    assert payload.referencia_ubicacion == "Guayaquil y Cristobal Colón"


def test_interseccion_aproximada_promedia_calles(monkeypatch):
    from core.chatboot_evaluacion import gis_evaluacion

    def fake_obtener(punto):
        datos = {
            "Av. Daniel León Borja": (-1.665, -78.658, "Daniel León Borja"),
            "Duchicela": (-1.667, -78.662, "Duchicela"),
        }
        return datos.get(punto, (None, None, None))

    monkeypatch.setattr(gis_evaluacion, "obtener_coordenadas_nominatim", fake_obtener)

    lat, lon, nombre = _coordenadas_interseccion_aproximada(
        "Av. Daniel León Borja y Duchicela"
    )

    assert round(lat, 3) == -1.666
    assert round(lon, 3) == -78.66
    assert "Daniel León Borja" in nombre
