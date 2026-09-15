"""Regresión: todas las herramientas de exploración deben devolver estado_busqueda."""

from unittest.mock import MagicMock

import pytest

from core.embeddings.semantica_evaluacion import CandidatoSemanticoEvaluado
from esquemas.chatboot_exploracion.busqueda_semantica_consulta import BusquedaSemanticaConsultaEntrada
from esquemas.chatboot_exploracion.horario_consulta import HorarioConsultaEntrada
from servicios.chatboot_exploracion import busqueda_semantica_consulta as semantica_svc
from servicios.chatboot_exploracion import horario_consulta as horario_svc


def _assert_estado_busqueda_base(
    estado_busqueda: dict,
    *,
    nombre: str,
    estado: str,
) -> None:
    assert estado_busqueda["estado"] == estado
    assert isinstance(estado_busqueda["ids_entrada"], list)
    assert isinstance(estado_busqueda["ids_salida"], list)
    assert isinstance(estado_busqueda["filtros"], list)
    assert len(estado_busqueda["filtros"]) >= 1
    assert estado_busqueda["filtros"][0]["nombre"] == nombre
    assert estado_busqueda["filtros"][0]["estado"] == estado
    assert isinstance(estado_busqueda["retroalimentacion"], dict)


def test_semantica_exito_incluye_retroalimentacion_en_ambos_niveles(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(semantica_svc, "generar_embedding", lambda *a, **k: "[0.1]")

    candidato = CandidatoSemanticoEvaluado(
        id_sitio=53,
        nombre="Chimborazo Tours",
        score_semantico=0.8,
        score_final=0.8,
        boost_keywords=0.25,
        keywords_match=["cabalgata"],
        supera_umbral=True,
        motivo="alto",
    )
    monkeypatch.setattr(
        semantica_svc,
        "buscar_sitios_por_semantica",
        lambda *a, **k: ([53], [candidato]),
    )

    salida = semantica_svc.consultar_sitios_por_busqueda_semantica(
        db,
        BusquedaSemanticaConsultaEntrada(
            texto_embeddings="cabalgatas en chimborazo",
            keywords=["cabalgata"],
            ids_consulta=[1, 2],
        ),
    )
    data = salida.model_dump(mode="json")
    assert data["ids_sitio"] == [53]
    assert data["retroalimentacion"]["codigo"] == "encontrado_en_alcance_previo"
    _assert_estado_busqueda_base(
        data["estado_busqueda"],
        nombre="busqueda_semantica",
        estado="cumplido",
    )
    assert data["estado_busqueda"]["retroalimentacion"]["codigo"] == "encontrado_en_alcance_previo"
    assert data["estado_busqueda"]["ids_entrada"] == [1, 2]
    assert data["estado_busqueda"]["ids_salida"] == [53]
    assert data["candidatos"][0]["supera_umbral"] is True
    assert data["candidatos"][0]["motivo"] == "alto"


def test_semantica_aproximado_fallback_global(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(semantica_svc, "generar_embedding", lambda *a, **k: "[0.1]")

    candidato = CandidatoSemanticoEvaluado(
        id_sitio=88,
        nombre="Sitio global",
        score_semantico=0.8,
        score_final=0.8,
        boost_keywords=0.0,
        keywords_match=[],
        supera_umbral=True,
        motivo="alto",
    )
    llamadas: list[list[int]] = []

    def fake_buscar(_db, *, ids_consulta, **kwargs):
        llamadas.append(list(ids_consulta))
        if ids_consulta:
            return [], []
        return [88], [candidato]

    monkeypatch.setattr(semantica_svc, "buscar_sitios_por_semantica", fake_buscar)

    salida = semantica_svc.consultar_sitios_por_busqueda_semantica(
        db,
        BusquedaSemanticaConsultaEntrada(
            texto_embeddings="museos",
            keywords=[],
            ids_consulta=[1, 2],
        ),
    )
    data = salida.model_dump(mode="json")
    assert llamadas == [[1, 2], []]
    assert data["ids_sitio"] == [88]
    assert data["estado_busqueda"]["estado"] == "aproximado"
    assert data["retroalimentacion"]["fallback_global_aplicado"] is True
    assert data["retroalimentacion"]["codigo"] == "busqueda_global_por_sin_coincidencias_en_alcance"


def test_semantica_sin_coincidencias_mantiene_candidatos_debug(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(semantica_svc, "generar_embedding", lambda *a, **k: "[0.1]")
    candidato = CandidatoSemanticoEvaluado(
        id_sitio=32,
        nombre="Comuna Palacio Real",
        score_semantico=0.33,
        score_final=0.33,
        boost_keywords=0.0,
        keywords_match=[],
        supera_umbral=False,
        motivo="descartado",
    )
    monkeypatch.setattr(
        semantica_svc,
        "buscar_sitios_por_semantica",
        lambda *a, **k: ([], [candidato]),
    )

    salida = semantica_svc.consultar_sitios_por_busqueda_semantica(
        db,
        BusquedaSemanticaConsultaEntrada(
            texto_embeddings="cabalgatas",
            keywords=["cabalgata"],
            ids_consulta=[],
        ),
    )
    data = salida.model_dump(mode="json")
    assert "sin_sitios" in data
    assert "ids_sitio" not in data
    assert data["estado_busqueda"]["estado"] == "no_cumplido"
    assert len(data["candidatos"]) == 1
    assert data["candidatos"][0]["supera_umbral"] is False


def test_horario_error_incluye_estado_busqueda():
    salida = horario_svc.consultar_sitios_por_horario(
        object(),
        HorarioConsultaEntrada(tipo="dias_solamente"),
    )
    data = salida.model_dump(mode="json")
    assert "fallo" in data
    _assert_estado_busqueda_base(
        data["estado_busqueda"],
        nombre="horario",
        estado="error",
    )
