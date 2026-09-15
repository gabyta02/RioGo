from servicios.chatboot_exploracion.fallback_opciones import (
    listar_opciones_fallback_exploracion,
)


class ResultadoFake:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class DbFake:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query):
        return ResultadoFake(self.rows)


def test_opciones_fallback_agrupa_y_ordena_segun_query():
    salida = listar_opciones_fallback_exploracion(
        DbFake(
            [
                {"categoria": "Alojamiento", "subcategoria": "Hotel"},
                {"categoria": "Alojamiento", "subcategoria": "Hostal"},
                {"categoria": "Manifestaciones Culturales", "subcategoria": "Museo"},
            ]
        )
    )

    assert [item.categoria for item in salida.opciones] == [
        "Alojamiento",
        "Manifestaciones Culturales",
    ]
    assert salida.opciones[0].subcategorias == ["Hotel", "Hostal"]


def test_opciones_fallback_bd_vacia():
    salida = listar_opciones_fallback_exploracion(DbFake([]))

    assert salida.opciones == []


def test_opciones_fallback_limita_subcategorias():
    salida = listar_opciones_fallback_exploracion(
        DbFake(
            [
                {"categoria": "Alojamiento", "subcategoria": f"Sub {indice}"}
                for indice in range(10)
            ]
        )
    )

    assert len(salida.opciones) == 1
    assert len(salida.opciones[0].subcategorias) == 6
