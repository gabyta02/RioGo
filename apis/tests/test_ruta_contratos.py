from servicios.chatboot_exploracion import ruta_consulta as ruta_svc
from esquemas.chatboot_exploracion.ruta_consulta import RutaConsultaEntrada


class DbFake:
    def __init__(self, ids):
        self.ids = ids
        self.params = None

    def execute(self, _query, params):
        self.params = params
        return self

    def scalars(self):
        return self

    def all(self):
        return self.ids


def test_ruta_senderismo_devuelve_ids():
    salida = ruta_svc.consultar_rutas(
        DbFake([3, 1]),
        RutaConsultaEntrada(tipo_ruta="senderismo", excluir_tipos=[], ids_consulta=[]),
    )

    assert salida.ids_ruta == [3, 1]
    assert salida.estado_busqueda.filtros[0].nombre == "ruta"


def test_ruta_transporte_publico_falla():
    salida = ruta_svc.consultar_rutas(
        DbFake([1]),
        RutaConsultaEntrada(
            tipo_ruta="transporte publico",
            excluir_tipos=[],
            ids_consulta=[],
        ),
    )

    assert "No se pudo resolver" in salida.fallo
    assert salida.estado_busqueda.estado == "error"


def test_ruta_bus_falla():
    salida = ruta_svc.consultar_rutas(
        DbFake([1]),
        RutaConsultaEntrada(tipo_ruta="bus", excluir_tipos=[], ids_consulta=[]),
    )

    assert "No se pudo resolver" in salida.fallo
    assert salida.estado_busqueda.estado == "error"


def test_ruta_otro_falla_y_sugiere_semantica():
    salida = ruta_svc.consultar_rutas(
        DbFake([1]),
        RutaConsultaEntrada(tipo_ruta="otro", excluir_tipos=[], ids_consulta=[]),
    )

    assert "busqueda_semantica" in salida.fallo
    assert salida.estado_busqueda.estado == "error"


def test_ruta_montanismo_acepta_alias_montana():
    salida = ruta_svc.consultar_rutas(
        DbFake([9]),
        RutaConsultaEntrada(tipo_ruta="montaña", excluir_tipos=[], ids_consulta=[]),
    )

    assert salida.ids_ruta == [9]
