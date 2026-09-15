import pytest
from fastapi import HTTPException

from esquemas.panel_administrativo.rutas_turisticas import RutaGeometriaUpdate
from servicios.panel_administrativo.rutas_turisticas import _validar_geometria_ruta


class _Result:
    def __init__(self, row=None):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class _Db:
    def __init__(self, site=None):
        self.site = site

    def execute(self, *_args, **_kwargs):
        return _Result(self.site)


def _geometry(points, line=None):
    return RutaGeometriaUpdate(
        linea=line or [
            {"latitud": -1.66, "longitud": -78.65},
            {"latitud": -1.65, "longitud": -78.64},
        ],
        puntos=points,
    )


def test_accepts_a_continuous_route_with_ordered_endpoints():
    geometry = _geometry([
        {"orden": 1, "tipo": "inicio", "latitud": -1.66, "longitud": -78.65},
        {"orden": 2, "tipo": "fin", "latitud": -1.65, "longitud": -78.64},
    ])

    _validar_geometria_ruta(_Db(), geometry)


def test_rejects_repeated_consecutive_vertices_before_persisting():
    geometry = _geometry(
        [
            {"orden": 1, "tipo": "inicio", "latitud": -1.66, "longitud": -78.65},
            {"orden": 2, "tipo": "fin", "latitud": -1.65, "longitud": -78.64},
        ],
        [
            {"latitud": -1.66, "longitud": -78.65},
            {"latitud": -1.66, "longitud": -78.65},
        ],
    )

    with pytest.raises(HTTPException, match="repetidos"):
        _validar_geometria_ruta(_Db(), geometry)


def test_site_is_resolved_to_its_official_coordinate_and_must_be_intermediate():
    geometry = _geometry(
        [
            {"orden": 1, "tipo": "inicio", "latitud": -1.66, "longitud": -78.65},
            {"orden": 2, "tipo": "sitio", "id_sitio": 9},
            {"orden": 3, "tipo": "fin", "latitud": -1.65, "longitud": -78.64},
        ],
        [
            {"latitud": -1.66, "longitud": -78.65},
            {"latitud": -1.655, "longitud": -78.645},
            {"latitud": -1.65, "longitud": -78.64},
        ],
    )

    _validar_geometria_ruta(_Db({"latitud": -1.655, "longitud": -78.645}), geometry)
    assert geometry.puntos[1].latitud == -1.655
    assert geometry.puntos[1].longitud == -78.645


def test_rejects_a_site_as_route_endpoint():
    geometry = _geometry([
        {"orden": 1, "tipo": "sitio", "id_sitio": 9},
        {"orden": 2, "tipo": "fin", "latitud": -1.65, "longitud": -78.64},
    ])

    with pytest.raises(HTTPException, match="primer punto"):
        _validar_geometria_ruta(_Db(), geometry)
