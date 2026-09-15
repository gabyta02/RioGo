from types import SimpleNamespace

from core.chatboot_evaluacion.atributos_evaluacion import filtrar_sitios_por_atributos
from esquemas.chatboot_exploracion.atributos_booleanos_consulta import (
    AtributosBooleanosConsultaEntrada,
)
from servicios.chatboot_exploracion.atributos_booleanos_consulta import (
    consultar_sitios_por_atributos,
)


class ResultadoFake:
    def __init__(self, ids):
        self._ids = ids

    def scalars(self):
        return self

    def all(self):
        return self._ids


class DbFake:
    def __init__(self, ids):
        self.ids = ids
        self.llamadas = []

    def execute(self, query, params):
        self.llamadas.append({"query": str(query), "params": params})
        return ResultadoFake(self.ids)


def test_core_filtra_es_gratuito_con_ids_consulta():
    db = DbFake([69, 70])

    ids = filtrar_sitios_por_atributos(
        db,
        ids_consulta=[70, 69, 73],
        tiene_wifi=None,
        permite_mascotas=None,
        accesibilidad=None,
        parqueadero=None,
        es_gratuito=True,
        excluir=[],
    )

    assert ids == [69, 70]
    assert db.llamadas[0]["params"]["es_gratuito"] is True
    assert db.llamadas[0]["params"]["ids_consulta"] == [69, 70, 73]


def test_servicio_rechaza_payload_sin_filtros_booleanos():
    payload = AtributosBooleanosConsultaEntrada(
        ids_consulta=[1, 2],
        tiene_wifi=None,
        permite_mascotas=None,
        accesibilidad=None,
        parqueadero=None,
        es_gratuito=None,
        excluir=[],
    )

    salida = consultar_sitios_por_atributos(SimpleNamespace(), payload)

    assert salida.fallo == "Debe indicar al menos un atributo booleano o una exclusión."
    assert salida.estado_busqueda.estado == "error"


def test_servicio_devuelve_sin_sitios_si_no_hay_coincidencias():
    db = DbFake([])
    payload = AtributosBooleanosConsultaEntrada(
        ids_consulta=[1, 2],
        tiene_wifi=True,
        permite_mascotas=None,
        accesibilidad=None,
        parqueadero=None,
        es_gratuito=None,
        excluir=[],
    )

    salida = consultar_sitios_por_atributos(db, payload)

    assert salida.sin_sitios == "Ningún sitio cumple con los atributos booleanos indicados."
    assert salida.estado_busqueda.estado == "no_cumplido"
