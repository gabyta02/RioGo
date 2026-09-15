import pytest

from core.embeddings.cache_embedding import (
    guardar_embedding_cache,
    leer_embedding_cache,
    limpiar_cache_embedding,
)
from core.embeddings.semantica_evaluacion import (
    UMBRAL_ALTO,
    _boost_por_keyword,
    _calcular_boosts,
    _evaluar_candidato,
)
from core.infra.busqueda_texto import score_keyword_en_texto, score_trigram_local


def test_score_trigram_local_coincidencia_exacta():
    assert score_trigram_local("Museo de la Ciudad", "museo") >= 0.4


def test_score_keyword_en_texto_por_palabra():
    assert score_keyword_en_texto("Museo de Riobamba", "museo") >= 0.95
    assert score_keyword_en_texto("cabalgatas en la ruta", "cabalgata") >= 0.95


def test_score_keyword_en_texto_tolera_typo_largo_de_una_palabra():
    assert score_keyword_en_texto("salchipapa", "slachipapa") >= 0.90
    assert score_keyword_en_texto("salchipapa", "sachipapa") >= 0.90


def test_score_keyword_en_texto_sin_falsos_positivos():
    assert score_keyword_en_texto("Comuna Palacio Real", "cabalgata") < 0.70
    assert score_keyword_en_texto("Comuna Palacio Real", "montar a caballo") == 0.0
    assert score_keyword_en_texto("hostal", "hotel") == 0.0
    chunk = (
        "El Centro de Turismo Comunitario Palacio Real, te invita a disfrutar "
        "de senderos interpretativos llenos de fauna y flora nativa."
    )
    assert score_keyword_en_texto(chunk, "cabalgata") < 0.70
    assert score_keyword_en_texto(chunk, "paseo ecuestre") == 0.0
    assert score_keyword_en_texto(chunk, "montar a caballo") == 0.0
    assert score_keyword_en_texto("un espacio recreativo con piscina", "pesca") == 0.0
    assert score_keyword_en_texto("práctica deportiva", "pesca deportiva") == 0.0


def test_boost_no_aplica_sin_coincidencia_real():
    boost, coincidencias = _calcular_boosts(
        nombre="Comuna Palacio Real",
        descripcion_corta=None,
        contenido_chunk=(
            "El Centro de Turismo Comunitario Palacio Real, te invita a disfrutar "
            "de senderos interpretativos llenos de fauna y flora nativa."
        ),
        keywords=["montar a caballo", "cabalgata", "paseo ecuestre"],
    )
    assert boost == 0.0
    assert coincidencias == []


def test_boost_pesca_no_aplica_por_complejo_deportivo():
    boost, coincidencias = _calcular_boosts(
        nombre="Complejo Deportivo El Rey",
        descripcion_corta="Canchas y espacios para actividad deportiva.",
        contenido_chunk="Cuenta con canchas deportivas para entrenamiento y recreacion.",
        keywords=["pesca deportiva", "pesca"],
    )

    assert boost == 0.0
    assert coincidencias == []


def test_boost_cabalgata_en_chunk_legitimo():
    boost, coincidencias = _calcular_boosts(
        nombre="Chimborazo Tours",
        descripcion_corta=None,
        contenido_chunk=(
            "Ofrece actividades como senderismo, caminatas, campamentos, "
            "cabalgatas, ciclismo y escalada."
        ),
        keywords=["cabalgata", "paseo ecuestre"],
    )
    assert "cabalgata" in coincidencias
    assert "paseo ecuestre" not in coincidencias
    assert boost >= 0.25


def test_boost_titulo_por_subcadena():
    boost = _boost_por_keyword(
        nombre="Museo de Riobamba",
        descripcion_corta=None,
        contenido_chunk=None,
        keyword="museo",
    )
    assert boost > 0


def test_calcular_boosts_acumula_keywords():
    total, coincidencias = _calcular_boosts(
        nombre="Parque Sucre",
        descripcion_corta="Área verde en el centro",
        contenido_chunk="ideal para familias",
        keywords=["parque", "familias"],
    )
    assert total > 0
    assert len(coincidencias) >= 1


def test_evaluar_candidato_umbral_alto():
    supera, motivo, final = _evaluar_candidato(
        score_semantico=UMBRAL_ALTO,
        boost_keywords=0.0,
    )
    assert supera is True
    assert motivo == "alto"
    assert final == UMBRAL_ALTO


def test_evaluar_candidato_hibrido_keyword():
    supera, motivo, _ = _evaluar_candidato(
        score_semantico=0.76,
        boost_keywords=0.20,
    )
    assert supera is True
    assert motivo == "alto"


def test_evaluar_candidato_medio_con_keyword():
    supera, motivo, _ = _evaluar_candidato(
        score_semantico=0.62,
        boost_keywords=0.05,
    )
    assert supera is False
    assert motivo == "descartado"


def test_evaluar_candidato_rechaza_hibrido_sin_keyword_real():
    supera, motivo, _ = _evaluar_candidato(
        score_semantico=0.3583,
        boost_keywords=0.0,
    )
    assert supera is False
    assert motivo == "descartado"


def test_evaluar_candidato_acepta_keyword_explicita_aunque_score_bajo():
    supera, motivo, final = _evaluar_candidato(
        score_semantico=0.2877,
        boost_keywords=0.25,
        keywords_match=["cabalgata"],
    )

    assert supera is True
    assert motivo == "keyword"
    assert final == pytest.approx(0.2877)




def test_cache_embedding_memoria():
    limpiar_cache_embedding()
    guardar_embedding_cache("texto prueba", "query", "voyage-4-lite", "[0.1,0.2]")
    assert leer_embedding_cache("texto prueba", "query", "voyage-4-lite") == "[0.1,0.2]"
    assert leer_embedding_cache("otro texto", "query", "voyage-4-lite") is None
