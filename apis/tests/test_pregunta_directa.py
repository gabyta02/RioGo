from esquemas.pregunta_directa import (
    PreguntaDirectaEntrada,
    PreguntaDirectaExito,
    PreguntaDirectaFallo,
    PreguntaDirectaSinSitios,
)
from servicios.pregunta_directa import resolver_sitio_pregunta_directa


class ResultadoFake:
    def __init__(self, rows):
        if rows is None:
            self.rows = []
        elif isinstance(rows, list):
            self.rows = rows
        else:
            self.rows = [rows]

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class SesionFake:
    def __init__(self, row=None):
        self.row = row
        self.query = ""
        self.params = {}

    def execute(self, query, params):
        self.query = str(query)
        self.params = params
        return ResultadoFake(self.row)


def test_pregunta_directa_exacta_devuelve_sitio():
    db = SesionFake(
        {"id_sitio": 69, "nombre": "Casa Museo de Riobamba", "score": 0.96}
    )

    salida = resolver_sitio_pregunta_directa(
        db,
        PreguntaDirectaEntrada(nombre_entidad="Casa Museo de Riobamba"),
    )

    assert isinstance(salida, PreguntaDirectaExito)
    assert salida.ids_sitio == [69]
    assert salida.id_sitio == 69
    assert salida.nombre == "Casa Museo de Riobamba"
    assert salida.score == 0.96
    assert db.params["umbral"] == 0.50
    assert "s.activo = TRUE" in db.query


def test_pregunta_directa_normaliza_mayusculas_y_tildes():
    db = SesionFake({"id_sitio": 15, "nombre": "Basílica", "score": 0.93})

    salida = resolver_sitio_pregunta_directa(
        db,
        PreguntaDirectaEntrada(nombre_entidad="  BASÍLICA  "),
    )

    assert isinstance(salida, PreguntaDirectaExito)
    assert db.params["nombre_entidad"] == "basilica"


def test_pregunta_directa_bajo_umbral_devuelve_sin_sitios():
    db = SesionFake(None)

    salida = resolver_sitio_pregunta_directa(
        db,
        PreguntaDirectaEntrada(nombre_entidad="sitio inexistente"),
    )

    assert isinstance(salida, PreguntaDirectaSinSitios)
    assert "parecidos" in salida.sin_sitios
    assert salida.sugerencias == []


def test_pregunta_directa_confianza_media_devuelve_sugerencias():
    db = SesionFake(
        [
            {"id_sitio": 72, "nombre": "Museo y Centro Cultural de Riobamba", "score": 0.72},
            {"id_sitio": 73, "nombre": "Casa Museo de Riobamba", "score": 0.61},
        ]
    )

    salida = resolver_sitio_pregunta_directa(
        db,
        PreguntaDirectaEntrada(nombre_entidad="museo riobamba"),
    )

    assert isinstance(salida, PreguntaDirectaSinSitios)
    assert "confirmes" in salida.sin_sitios
    assert [item.id_sitio for item in salida.sugerencias] == [72, 73]
    assert salida.estado_busqueda is not None
    assert salida.estado_busqueda.ids_salida == [72, 73]


def test_pregunta_directa_ids_consulta_limita_universo():
    db = SesionFake({"id_sitio": 2, "nombre": "Museo", "score": 1.0})

    resolver_sitio_pregunta_directa(
        db,
        PreguntaDirectaEntrada(nombre_entidad="Museo", ids_consulta=[3, 2, 2]),
    )

    assert "s.id_sitio = ANY(:ids_consulta)" in db.query
    assert db.params["ids_consulta"] == [2, 3]


def test_pregunta_directa_nombre_vacio_devuelve_fallo():
    db = SesionFake()

    salida = resolver_sitio_pregunta_directa(
        db,
        PreguntaDirectaEntrada(nombre_entidad="  "),
    )

    assert isinstance(salida, PreguntaDirectaFallo)
    assert salida.fallo == "Debe enviar nombre_entidad."
    assert db.query == ""
