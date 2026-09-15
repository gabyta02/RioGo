from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from core.autenticacion import permisos as permisos_core
from core.infra.trazabilidad import _ACCIONES_COMPATIBLES
from rutas.panel_administrativo import dashboard as dashboard_router
from servicios.panel_administrativo.cuentas_admin import (
    _es_cargo_dueno,
    _filtrar_permisos_globales_dueno,
    _permisos_usuario,
    _validar_sitios_existen,
    _validar_sitios_para_asignacion,
    actualizar_sitios_cuenta,
    listar_sitios_catalogo_cuenta,
)


def test_accion_sitios_cuenta_mapea_trazabilidad():
    assert _ACCIONES_COMPATIBLES["actualizacion_sitios_cuenta_admin"] == "actualizacion_cuenta"


def test_es_cargo_dueno_normaliza_tilde():
    assert _es_cargo_dueno("Dueño") is True
    assert _es_cargo_dueno("Dueno") is True
    assert _es_cargo_dueno("Analista") is False


def test_filtrar_permisos_globales_dueno():
    permisos = ["dashboard", "analytics", "attractions", "chatbot_content", "noticias"]
    assert _filtrar_permisos_globales_dueno(permisos, True) == ["dashboard", "analytics"]
    assert _filtrar_permisos_globales_dueno(permisos, False) == permisos


def test_obtener_sitios_permitidos_dueno_ignora_permiso_global(monkeypatch):
    db = MagicMock()
    usuario = {"id_usuario": 10, "rol": "admin", "cargo_nombre": "Dueño"}
    monkeypatch.setattr(permisos_core, "cargar_sitios_asignados", lambda _db, _id_usuario: [16])

    sitios = permisos_core.obtener_sitios_permitidos(db, usuario, "analytics", "ver")

    assert sitios == [16]
    db.execute.assert_not_called()


def test_obtener_sitios_permitidos_admin_global_mantiene_todo():
    db = MagicMock()
    db.execute.return_value.first.return_value = (1,)
    usuario = {"id_usuario": 2, "rol": "admin", "cargo_nombre": "Admin"}

    sitios = permisos_core.obtener_sitios_permitidos(db, usuario, "analytics", "ver")

    assert sitios is None


def test_alcance_dashboard_dueno_usa_sitios_asignados(monkeypatch):
    db = MagicMock()
    usuario = {"id_usuario": 10, "rol": "admin", "cargo_nombre": "Dueño"}
    monkeypatch.setattr(permisos_core, "cargar_sitios_asignados", lambda _db, _id_usuario: [16])

    sitios = dashboard_router._sitios_alcance_dashboard(db, usuario)

    assert sitios == [16]


def test_validar_sitios_para_asignacion_rechaza_inactivo():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"id_sitio": 1, "activo": True},
        {"id_sitio": 2, "activo": False},
    ]
    with pytest.raises(HTTPException) as exc:
        _validar_sitios_para_asignacion(db, [1, 2])
    assert exc.value.status_code == 400
    assert "inactivos" in exc.value.detail.lower()


def test_validar_sitios_existen_rechaza_ids_invalidos():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"id_sitio": 1, "activo": True},
    ]
    with pytest.raises(HTTPException) as exc:
        _validar_sitios_existen(db, [1, 99])
    assert exc.value.status_code == 400
    assert "99" in exc.value.detail


def test_validar_sitios_existen_lista_vacia_ok():
    db = MagicMock()
    _validar_sitios_existen(db, [])
    db.execute.assert_not_called()


def test_actualizar_sitios_cuenta_dueno_sin_sitios_rechaza():
    db = MagicMock()
    with patch(
        "servicios.panel_administrativo.cuentas_admin._obtener_cuenta_admin",
        return_value={"cargo_nombre": "Dueño"},
    ):
        with pytest.raises(HTTPException) as exc:
            actualizar_sitios_cuenta(db, 1, [], MagicMock())
    assert exc.value.status_code == 400
    assert "al menos un sitio" in exc.value.detail.lower()


def test_permisos_usuario_solo_globales():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = ["dashboard"]

    permisos = _permisos_usuario(db, 7)

    assert permisos == ["dashboard"]
    sql = str(db.execute.call_args.args[0])
    assert "id_sitio IS NULL" in sql


@patch("servicios.panel_administrativo.cuentas_admin.listar_sitios")
def test_listar_sitios_catalogo_cuenta_usa_super_admin(mock_listar):
    db = MagicMock()
    mock_listar.return_value = MagicMock(total=2)

    listar_sitios_catalogo_cuenta(db, "parque", "activo", 1, 200)

    mock_listar.assert_called_once()
    assert mock_listar.call_args.args[9] == {"rol": "super-admin", "id_usuario": 0}
    assert mock_listar.call_args.args[8] == 200
