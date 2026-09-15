from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from servicios.panel_administrativo.cuentas_admin import (
    _datos_cuenta_afectados,
    _generar_username_disponible,
    _validar_sitios_existen,
)
from servicios.panel_administrativo import dashboard as dashboard_service
from servicios.panel_administrativo.dashboard import (
    _SEMANTICA_CACHE,
    _semantica_alcance_sql,
    _semantica_vacia,
    obtener_semantica,
)
from servicios.panel_administrativo.registro_acciones import MODULO_POR_TABLA, _sql_filtro_accion_visual


def test_semantica_alcance_super_admin_sin_filtro():
    ex, dt, params = _semantica_alcance_sql(None)
    assert ex == ""
    assert dt == ""
    assert params == {}


def test_semantica_alcance_admin_sin_sitios_bloquea_todo():
    ex, dt, params = _semantica_alcance_sql([])
    assert "1=0" in ex
    assert "1=0" in dt
    assert params == {}


def test_semantica_alcance_admin_con_sitios_filtra_detalle():
    ex, dt, params = _semantica_alcance_sql([1, 2])
    assert "1=0" in ex
    assert "sitios_permitidos" in dt
    assert params == {"sitios_permitidos": [1, 2]}


def test_semantica_vacia_estructura():
    respuesta = _semantica_vacia("month")
    assert respuesta.total_grupos == 0
    assert respuesta.total_consultas_agrupadas == 0
    assert respuesta.resumen.consultas_totales == 0
    assert respuesta.grupos == []


def _usar_cache_local(monkeypatch):
    monkeypatch.setattr(
        dashboard_service,
        "ejecutar_redis",
        lambda _callback, *, fallback: fallback(),
    )


def test_obtener_semantica_sin_sitios_no_consulta_db(monkeypatch):
    _usar_cache_local(monkeypatch)
    _SEMANTICA_CACHE.clear()
    db = MagicMock()
    resultado = obtener_semantica(db, sitios_permitidos=[])
    assert resultado.total_grupos == 0
    db.execute.assert_not_called()


def test_obtener_semantica_normaliza_arrays_de_categoria(monkeypatch):
    _usar_cache_local(monkeypatch)
    _SEMANTICA_CACHE.clear()
    db = MagicMock()
    conteos = MagicMock()
    conteos.mappings.return_value.one.return_value = {
        "total_preguntas_usuario": 0,
        "total_mensajes_historial": 0,
        "preguntas_con_embedding": 0,
    }
    mensajes = MagicMock()
    mensajes.mappings.return_value.all.return_value = []
    db.execute.side_effect = [conteos, mensajes]

    obtener_semantica(db, categoria="Hotel", subcategoria="Hostal")

    sql = "\n".join(str(call.args[0]) for call in db.execute.call_args_list)
    params = db.execute.call_args_list[-1].args[1]
    assert "array_to_string(categoria" in sql
    assert "array_to_string(subcategoria" in sql
    assert ":categoria = ANY(categoria)" in sql
    assert ":subcategoria = ANY(subcategoria)" in sql
    assert "pregunta_directa" in sql
    assert params["categoria"] == "Hotel"
    assert params["subcategoria"] == "Hostal"


def test_obtener_semantica_limit_no_recorta_universo_analizado(monkeypatch):
    _usar_cache_local(monkeypatch)
    _SEMANTICA_CACHE.clear()
    db = MagicMock()
    conteos = MagicMock()
    conteos.mappings.return_value.one.return_value = {
        "total_preguntas_usuario": 3,
        "total_mensajes_historial": 6,
        "preguntas_con_embedding": 3,
    }
    mensajes = MagicMock()
    mensajes.mappings.return_value.all.return_value = [
        {
            "id_mensaje": 1,
            "pregunta": "museos",
            "categoria": "Cultura",
            "subcategoria": "Museos",
            "entidad": None,
            "tipo_chatbot": "general",
            "canal": "exploracion",
            "fecha": "2026-07-01T00:00:00Z",
            "embedding": "[1,0]",
        },
        {
            "id_mensaje": 2,
            "pregunta": "museos cerca",
            "categoria": "Cultura",
            "subcategoria": "Museos",
            "entidad": None,
            "tipo_chatbot": "general",
            "canal": "exploracion",
            "fecha": "2026-07-01T00:00:00Z",
            "embedding": "[0.99,0.01]",
        },
        {
            "id_mensaje": 3,
            "pregunta": "parques",
            "categoria": "Naturaleza",
            "subcategoria": "Parques",
            "entidad": None,
            "tipo_chatbot": "general",
            "canal": "exploracion",
            "fecha": "2026-07-01T00:00:00Z",
            "embedding": "[0,1]",
        },
    ]
    db.execute.side_effect = [conteos, mensajes]

    resultado = obtener_semantica(
        db,
        limit=1,
        max_consultas_analisis=10000,
        min_total_consultas=1,
    )

    params = db.execute.call_args_list[-1].args[1]
    assert params["max_consultas"] == 10000
    assert "LIMIT :max_consultas" in str(db.execute.call_args_list[-1].args[0])
    assert resultado.total_grupos == 1
    assert resultado.resumen.preguntas_analizadas == 3
    assert resultado.resumen.total_preguntas_usuario == 3
    assert resultado.resumen.total_mensajes_historial == 6


def test_obtener_semantica_expone_canal_pregunta_directa(monkeypatch):
    _usar_cache_local(monkeypatch)
    _SEMANTICA_CACHE.clear()
    db = MagicMock()
    conteos = MagicMock()
    conteos.mappings.return_value.one.return_value = {
        "total_preguntas_usuario": 1,
        "total_mensajes_historial": 2,
        "preguntas_con_embedding": 1,
    }
    mensajes = MagicMock()
    mensajes.mappings.return_value.all.return_value = [
        {
            "id_mensaje": 9,
            "pregunta": "horario del museo",
            "categoria": None,
            "subcategoria": None,
            "entidad": "Museo",
            "tipo_chatbot": "sitio",
            "canal": "pregunta_directa",
            "fecha": "2026-07-01T00:00:00Z",
            "embedding": "[1,0]",
        }
    ]
    db.execute.side_effect = [conteos, mensajes]

    resultado = obtener_semantica(
        db,
        canal="pregunta_directa",
        min_total_consultas=1,
    )

    assert resultado.grupos[0].canal == "pregunta_directa"
    assert resultado.grupos[0].consultas[0].canal == "pregunta_directa"
    assert resultado.grupos[0].tipo_chatbot == "sitio"
    assert resultado.grupos[0].preguntas_relacionadas[0].total_consultas == 1


def test_obtener_semantica_filtra_minimo_y_expone_preguntas_relacionadas(monkeypatch):
    _usar_cache_local(monkeypatch)
    _SEMANTICA_CACHE.clear()
    db = MagicMock()
    conteos = MagicMock()
    conteos.mappings.return_value.one.return_value = {
        "total_preguntas_usuario": 4,
        "total_mensajes_historial": 8,
        "preguntas_con_embedding": 4,
    }
    mensajes = MagicMock()
    mensajes.mappings.return_value.all.return_value = [
        {
            "id_mensaje": 1,
            "pregunta": "Museos cerca",
            "categoria": "Cultura",
            "subcategoria": "Museos",
            "entidad": None,
            "tipo_chatbot": "general",
            "canal": "exploracion",
            "fecha": "2026-07-03T00:00:00Z",
            "embedding": "[1,0]",
        },
        {
            "id_mensaje": 2,
            "pregunta": "museos cerca",
            "categoria": "Cultura",
            "subcategoria": "Museos",
            "entidad": None,
            "tipo_chatbot": "general",
            "canal": "exploracion",
            "fecha": "2026-07-02T00:00:00Z",
            "embedding": "[0.99,0.01]",
        },
        {
            "id_mensaje": 3,
            "pregunta": "quiero visitar museos",
            "categoria": "Cultura",
            "subcategoria": "Museos",
            "entidad": None,
            "tipo_chatbot": "general",
            "canal": "exploracion",
            "fecha": "2026-07-01T00:00:00Z",
            "embedding": "[0.98,0.02]",
        },
        {
            "id_mensaje": 4,
            "pregunta": "parques",
            "categoria": "Naturaleza",
            "subcategoria": "Parques",
            "entidad": None,
            "tipo_chatbot": "general",
            "canal": "exploracion",
            "fecha": "2026-07-01T00:00:00Z",
            "embedding": "[0,1]",
        },
    ]
    db.execute.side_effect = [conteos, mensajes]

    resultado = obtener_semantica(db, min_total_consultas=2)

    assert resultado.total_grupos == 1
    assert resultado.total_consultas_agrupadas == 3
    assert resultado.grupos[0].consulta_representativa == "Museos cerca"
    assert resultado.grupos[0].total_consultas == 3
    assert resultado.grupos[0].preguntas_relacionadas[0].pregunta == "Museos cerca"
    assert resultado.grupos[0].preguntas_relacionadas[0].total_consultas == 2
    assert resultado.grupos[0].preguntas_relacionadas[1].pregunta == "quiero visitar museos"
    assert resultado.grupos[0].preguntas_relacionadas[1].total_consultas == 1
    assert len(resultado.grupos[0].consultas) == 3


def test_sql_filtro_accion_visual_por_tipo():
    assert _sql_filtro_accion_visual("all") == ""
    assert "INSERT" in _sql_filtro_accion_visual("creacion")
    assert "DELETE" in _sql_filtro_accion_visual("eliminacion")
    assert "login" in _sql_filtro_accion_visual("sesion")
    assert "creacion_cuenta" in _sql_filtro_accion_visual("creacion")
    assert "inactivacion_cuenta" in _sql_filtro_accion_visual("desactivacion")
    assert "inactivacion_cuenta_admin" in _sql_filtro_accion_visual("desactivacion")
    assert "actualizacion_cuenta" in _sql_filtro_accion_visual("actualizacion")
    assert "actualizacion_cuenta_admin" in _sql_filtro_accion_visual("actualizacion")
    assert "cambio_2fa" in _sql_filtro_accion_visual("actualizacion")
    assert "cambio_foto_perfil" in _sql_filtro_accion_visual("actualizacion")
    assert "geometria" in _sql_filtro_accion_visual("edicion")


def test_usuario_permiso_pertenece_a_cuentas_administrativas():
    assert MODULO_POR_TABLA["usuario_permiso"] == "admin_accounts"


def test_validar_sitios_existen_rechaza_ids_invalidos():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [1]
    with pytest.raises(HTTPException) as exc:
        _validar_sitios_existen(db, [1, 99])
    assert exc.value.status_code == 400
    assert "99" in exc.value.detail


def test_validar_sitios_existen_lista_vacia_ok():
    db = MagicMock()
    _validar_sitios_existen(db, [])
    db.execute.assert_not_called()


def test_generar_username_disponible_agrega_sufijo_si_local_email_existe():
    db = MagicMock()
    db.execute.side_effect = [
        MagicMock(first=lambda: (1,)),
        MagicMock(first=lambda: None),
    ]

    username = _generar_username_disponible(db, "manzanojuan101")

    assert username == "manzanojuan101-1"


def test_generar_username_disponible_usa_local_email_si_esta_libre():
    db = MagicMock()
    db.execute.return_value.first.return_value = None

    username = _generar_username_disponible(db, "manzanojuan101")

    assert username == "manzanojuan101"


def test_datos_cuenta_afectados_solo_compara_campos_modificados():
    anteriores, nuevos = _datos_cuenta_afectados(
        {
            "id_usuario": 4,
            "username": "admin",
            "email": "actual@example.com",
            "nombre_completo": "Nombre Actual",
            "ultimo_acceso_en": "2026-07-03T00:00:00Z",
            "permisos": ["dashboard"],
        },
        {
            "email": "nuevo@example.com",
            "nombre_completo": "Nombre Nuevo",
            "permisos": ["dashboard", "routes"],
        },
    )

    assert anteriores == {
        "email": "actual@example.com",
        "nombre_completo": "Nombre Actual",
        "permisos": ["dashboard"],
    }
    assert nuevos == {
        "email": "nuevo@example.com",
        "nombre_completo": "Nombre Nuevo",
        "permisos": ["dashboard", "routes"],
    }
