from datetime import time
from types import SimpleNamespace

import pytest

from core.horario_compacto import construir_horario_compacto
from esquemas.chatboot_pregunta_directa import (
    ChunksDocumentoEntrada,
    FichaSitioFallo,
    IdSitioEntrada,
)
from servicios.chatboot_pregunta_directa import (
    _seleccionar_documento_principal,
    buscar_chunks_documento,
    obtener_como_llegar,
    obtener_ficha_sitio_compacta,
    obtener_multimedia_sitio,
    obtener_ruta_documento,
)


class ResultadoFake:
    def __init__(self, rows):
        self.rows = rows if isinstance(rows, list) else [rows]

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


class QueryFake:
    def __init__(self, sitio=None):
        self.sitio = sitio

    def options(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.sitio


class SesionFake:
    def __init__(self, *, sitio=None, execute_rows=None):
        self.sitio = sitio
        self.execute_rows = execute_rows or []
        self.execute_calls = 0

    def query(self, model):
        return QueryFake(self.sitio)

    def execute(self, query, params=None):
        self.execute_calls += 1
        if self.execute_rows:
            indice = min(self.execute_calls - 1, len(self.execute_rows) - 1)
            return ResultadoFake(self.execute_rows[indice])
        return ResultadoFake(None)


def _detalle(dia: int, inicio: str, fin: str):
    return SimpleNamespace(
        dia_semana=dia,
        hora_inicio=time.fromisoformat(inicio),
        hora_fin=time.fromisoformat(fin),
        activo=True,
    )


def test_horario_compacto_todos_los_dias_iguales():
    horario = SimpleNamespace(
        activo=True,
        abierto_24h=False,
        comentario="Feriados cerrado",
        detalles=[
            _detalle(dia, "08:00", "17:00")
            for dia in range(1, 8)
        ],
    )

    salida = construir_horario_compacto(horario)

    assert salida["abierto_24h"] is False
    assert salida["texto"] == "Todos los días: 08:00-17:00"
    assert salida["comentario"] == "Feriados cerrado"


def test_horario_compacto_abierto_24h():
    horario = SimpleNamespace(
        activo=True,
        abierto_24h=True,
        comentario=None,
        detalles=[],
    )

    salida = construir_horario_compacto(horario)

    assert salida["abierto_24h"] is True
    assert salida["texto"] == "Abierto 24 horas"


def test_ficha_sitio_inexistente_devuelve_fallo():
    db = SesionFake(sitio=None)

    salida = obtener_ficha_sitio_compacta(db, IdSitioEntrada(id_sitio=999))

    assert isinstance(salida, FichaSitioFallo)
    assert salida.fallo == "Sitio no encontrado."


def test_ficha_sitio_incluye_atributos_booleanos():
    sitio = SimpleNamespace(
        id_sitio=69,
        nombre="Casa Museo",
        id_parroquia=1,
        id_plataforma=2,
        es_gratuito=True,
        parqueadero=False,
        tiene_wifi=True,
        accesibilidad=None,
        permite_mascotas=False,
        categoria=SimpleNamespace(nombre="Cultura"),
        subcategoria=SimpleNamespace(nombre="Museo"),
        parroquia=SimpleNamespace(nombre="RIOBAMBA", activo=True),
        plataforma=SimpleNamespace(nombre="Centro", activo=True),
        horario=None,
        precio=None,
        tarifas=[],
        contactos=[],
    )
    db = SesionFake(sitio=sitio)

    salida = obtener_ficha_sitio_compacta(db, IdSitioEntrada(id_sitio=69))

    assert salida.atributos.es_gratuito is True
    assert salida.atributos.parqueadero is False
    assert salida.atributos.tiene_wifi is True
    assert salida.atributos.accesibilidad is None
    assert salida.atributos.permite_mascotas is False
    assert salida.parroquia == "RIOBAMBA"
    assert salida.plataforma == "Centro"


def test_multimedia_devuelve_imagenes_activas(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://www.riobambatour.org")
    sitio = SimpleNamespace(id_sitio=69)
    db = SesionFake(
        sitio=sitio,
        execute_rows=[
            [
                {"url": "/api/v1/imagenes/a.jpg", "es_principal": True},
                {"url": "/api/v1/imagenes/b.jpg", "es_principal": False},
            ]
        ],
    )

    salida = obtener_multimedia_sitio(db, IdSitioEntrada(id_sitio=69))

    assert salida.id_sitio == 69
    assert len(salida.imagenes) == 2
    assert salida.imagenes[0].es_principal is True
    assert salida.imagenes[0].url == "https://www.riobambatour.org/api/v1/imagenes/a.jpg"


def test_chunks_documento_mensaje_vacio_devuelve_fallo():
    sitio = SimpleNamespace(id_sitio=69)
    db = SesionFake(sitio=sitio)

    salida = buscar_chunks_documento(
        db,
        ChunksDocumentoEntrada(id_sitio=69, mensaje_chunk="  "),
    )

    assert isinstance(salida, FichaSitioFallo)
    assert salida.fallo == "mensaje_chunk vacío."


def test_como_llegar_sin_ubicacion_devuelve_fallo():
    sitio = SimpleNamespace(id_sitio=69, activo=True)
    db = SesionFake(sitio=sitio, execute_rows=[None])

    salida = obtener_como_llegar(db, IdSitioEntrada(id_sitio=69))

    assert isinstance(salida, FichaSitioFallo)
    assert salida.fallo == "El sitio no tiene ubicación registrada."


def test_como_llegar_devuelve_coordenadas():
    db = SesionFake(
        execute_rows=[
            {
                "id_sitio": 69,
                "nombre": "Casa Museo",
                "lat": -1.67,
                "lon": -78.64,
            }
        ]
    )

    salida = obtener_como_llegar(db, IdSitioEntrada(id_sitio=69))

    assert salida.id_sitio == 69
    assert salida.ubicacion.lat == -1.67
    assert salida.ubicacion.lon == -78.64


@pytest.mark.parametrize(
    "mensaje_chunk",
    ["pregunta unica", ["pregunta uno", "pregunta dos"]],
)
def test_chunks_documento_acepta_string_y_lista(mensaje_chunk, monkeypatch):
    sitio = SimpleNamespace(id_sitio=69)
    db = SesionFake(sitio=sitio)

    monkeypatch.setattr(
        "servicios.chatboot_pregunta_directa.generar_embeddings",
        lambda textos, **kwargs: [f"emb:{texto}" for texto in textos],
    )
    monkeypatch.setattr(
        "servicios.chatboot_pregunta_directa.buscar_chunks_en_sitio",
        lambda *args, **kwargs: [],
    )

    salida = buscar_chunks_documento(
        db,
        ChunksDocumentoEntrada(id_sitio=69, mensaje_chunk=mensaje_chunk),
    )

    assert salida.estado == "chunk_baja_precision"
    assert salida.score_maximo == 0.0


def test_seleccionar_documento_unico():
    docs = [{"id_documento": 1, "ruta_archivo": "a.md", "total_secciones": 2}]
    elegido, criterio = _seleccionar_documento_principal(docs)
    assert elegido["id_documento"] == 1
    assert criterio == "unico"


def test_seleccionar_documento_archivo_mayor(tmp_path, monkeypatch):
    grande = tmp_path / "grande.md"
    chico = tmp_path / "chico.md"
    grande.write_text("contenido largo del documento", encoding="utf-8")
    chico.write_text("x", encoding="utf-8")

    docs = [
        {"id_documento": 1, "ruta_archivo": str(chico), "total_secciones": 10},
        {"id_documento": 2, "ruta_archivo": str(grande), "total_secciones": 1},
    ]
    elegido, criterio = _seleccionar_documento_principal(docs)
    assert elegido["id_documento"] == 2
    assert criterio == "archivo_mayor"


def test_ruta_documento_sin_documentos_devuelve_fallo():
    sitio = SimpleNamespace(id_sitio=68)
    db = SesionFake(sitio=sitio, execute_rows=[[]])

    salida = obtener_ruta_documento(db, IdSitioEntrada(id_sitio=68))

    assert isinstance(salida, FichaSitioFallo)
    assert salida.fallo == "No hay documento activo para este sitio."


def test_ruta_documento_devuelve_ruta():
    sitio = SimpleNamespace(id_sitio=68)
    db = SesionFake(
        sitio=sitio,
        execute_rows=[
            [
                {
                    "id_documento": 1,
                    "titulo": "Mercado de La Merced",
                    "ruta_archivo": "fuente_datos/mardowks/sitios/68-mercado.md",
                    "total_secciones": 3,
                }
            ]
        ],
    )

    salida = obtener_ruta_documento(db, IdSitioEntrada(id_sitio=68))

    assert salida.id_sitio == 68
    assert salida.id_documento == 1
    assert salida.ruta_archivo.endswith("68-mercado.md")
    assert salida.criterio_seleccion == "unico"
    assert salida.total_documentos == 1
