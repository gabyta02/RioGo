from types import SimpleNamespace

import pytest

from core.imagenes import normalizar_url_imagen
from servicios import sitios_turismo
from servicios.favoritos_user import _obtener_imagen_principal
from servicios.sitio_ficha import transformar_sitio_para_app


PUBLIC_BASE_URL = "https://www.riobambatour.org"
DEFAULT_PUBLIC_URL = f"{PUBLIC_BASE_URL}/api/v1/imagenes/default/site.jpg"


@pytest.fixture(autouse=True)
def configurar_urls(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", PUBLIC_BASE_URL)
    monkeypatch.setenv("DEFAULT_SITE_IMAGE_URL", "/api/v1/imagenes/default/site.jpg")


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("https://lh3.googleusercontent.com/imagen.jpg", "https://lh3.googleusercontent.com/imagen.jpg"),
        ("http://example.com/imagen.jpg", "http://example.com/imagen.jpg"),
        (f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"),
        ("/api/v1/imagenes/antartida/a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"),
        ("api/v1/imagenes/antartida/a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"),
        ("fuente_datos/imagenes/antartida/a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"),
        ("/fuente_datos/imagenes/antartida/a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"),
        ("imagenes/antartida/a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"),
        ("/imagenes/antartida/a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"),
        ("antartida/a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"),
        ("a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/a.jpg"),
        (None, DEFAULT_PUBLIC_URL),
        ("", DEFAULT_PUBLIC_URL),
        ("   ", DEFAULT_PUBLIC_URL),
        ("antartida//sub//a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/sub/a.jpg"),
        ("/api/v1/imagenes//antartida//a.jpg", f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"),
    ],
)
def test_normalizar_url_imagen(valor, esperado):
    assert normalizar_url_imagen(valor) == esperado


def test_normalizar_url_imagen_valida_public_base_url(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        normalizar_url_imagen("a.jpg")


def test_query_sitios_resumen_prioriza_principal_y_fallback_activa():
    sql = str(sitios_turismo.query_sitios_resumen())

    assert "WHERE m.id_sitio = s.id_sitio" in sql
    assert "AND m.activo = TRUE" in sql
    assert "ORDER BY m.es_principal DESC NULLS LAST, m.id_multimedia ASC" in sql
    assert "LIMIT 1" in sql


def test_transformar_sitio_resumen_normaliza_respuesta_postgresql():
    row = SimpleNamespace(
        _mapping={
            "id_sitio": 1,
            "id_categoria": 2,
            "id_subcategoria": 3,
            "nombre": "Antartida",
            "categoria": "Naturaleza",
            "subcategoria": "Parque",
            "descripcion": "Desc",
            "direccion": "Centro",
            "img_url": "fuente_datos/imagenes/antartida/a.jpg",
            "point": None,
            "longitud": None,
            "latitud": None,
        }
    )

    salida = sitios_turismo.transformar_sitio_resumen(row)

    assert salida["img_Url"] == f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"


def test_listar_sitios_resumen_normaliza_copia_desde_redis(monkeypatch):
    cacheado = {
        "id_sitio": 1,
        "id_categoria": 2,
        "id_subcategoria": 3,
        "nombre": "Antartida",
        "categoria": "Naturaleza",
        "subcategoria": "Parque",
        "descripcion": "Desc",
        "direccion": "Centro",
        "img_Url": "imagenes/antartida/a.jpg",
        "point": None,
    }
    monkeypatch.setattr(sitios_turismo, "obtener_sitios_cacheados", lambda db: [cacheado])

    salida = sitios_turismo.listar_sitios_resumen(db=object())

    assert salida == [
        {
            "id_sitio": 1,
            "nombre": "Antartida",
            "categoria": "Naturaleza",
            "subcategoria": "Parque",
            "descripcion": "Desc",
            "direccion": "Centro",
            "img_Url": f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg",
            "point": None,
        }
    ]
    assert cacheado["img_Url"] == "imagenes/antartida/a.jpg"


class ResultadoFake:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class DbFake:
    def __init__(self, row):
        self.row = row
        self.query = None

    def execute(self, query, params=None):
        self.query = str(query)
        return ResultadoFake(self.row)


def test_favoritos_imagen_principal_usa_primera_multimedia_activa_y_normaliza():
    db = DbFake({"url": "antartida/a.jpg"})

    salida = _obtener_imagen_principal(db, 1)

    assert salida == f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg"
    assert "AND activo = TRUE" in db.query
    assert "ORDER BY es_principal DESC NULLS LAST, id_multimedia ASC" in db.query


def test_favoritos_sin_multimedia_usa_default():
    assert _obtener_imagen_principal(DbFake(None), 1) == DEFAULT_PUBLIC_URL


def test_ficha_normaliza_imagenes_sin_cambiar_estructura():
    sitio = SimpleNamespace(
        id_sitio=1,
        nombre="Antartida",
        categoria=SimpleNamespace(nombre="Naturaleza"),
        subcategoria=SimpleNamespace(nombre="Parque"),
        direccion=None,
        horario=None,
        es_gratuito=None,
        precio=None,
        tarifas=[],
        tiene_wifi=None,
        parqueadero=None,
        permite_mascotas=None,
        accesibilidad=None,
        descripcion_corta="Desc",
        media=[
            SimpleNamespace(url="imagenes/antartida/b.jpg", es_principal=False),
            SimpleNamespace(url="imagenes/antartida/a.jpg", es_principal=True),
        ],
    )

    salida = transformar_sitio_para_app(sitio)

    assert salida["imagenes"] == [
        {"url": f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/a.jpg", "es_principal": True},
        {"url": f"{PUBLIC_BASE_URL}/api/v1/imagenes/antartida/b.jpg", "es_principal": False},
    ]
