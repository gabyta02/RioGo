import pytest

from core.chatboot_evaluacion.precio_compacto import construir_texto_precio_resumen
from core.embeddings.embeddings import generar_embeddings
from core.embeddings.cache_embedding import limpiar_cache_embedding
from types import SimpleNamespace


def test_construir_texto_precio_gratuito():
    sitio = SimpleNamespace(es_gratuito=True, precio=None, tarifas=[])
    assert construir_texto_precio_resumen(sitio) == "Gratuita"


def test_construir_texto_precio_rango():
    sitio = SimpleNamespace(
        es_gratuito=False,
        precio=SimpleNamespace(precio_min=2.5, precio_max=5.0, etiqueta_precio=None),
        tarifas=[],
    )
    assert construir_texto_precio_resumen(sitio) == "$2.50 - $5.00"


def test_generar_embeddings_batch(monkeypatch):
    limpiar_cache_embedding()
    llamadas: list[dict] = []

    def _fake_voyage(textos, *, input_type, api_key, modelo):
        llamadas.append({"textos": textos, "input_type": input_type})
        return [[0.1, 0.2] * 512 for _ in textos]

    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    monkeypatch.setattr(
        "core.embeddings.embeddings._solicitar_embeddings_voyage",
        _fake_voyage,
    )

    salida = generar_embeddings(["consulta uno", "consulta dos"], input_type="query")

    assert len(salida) == 2
    assert salida[0].startswith("[")
    assert llamadas[0]["textos"] == ["consulta uno", "consulta dos"]
    assert llamadas[0]["input_type"] == "query"
