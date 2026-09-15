import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from jose import JWTError

from fastapi import HTTPException

from core import actividad_sesion, redis_cliente, reglas_seguridad, tokens
from core.encriptacion import (
    encriptar_texto,
    hash_token_almacenado,
    verificar_token_almacenado,
)
from core.roles import es_rol_panel
from esquemas.autenticacion.autentificar import (
    RecuperacionPasswordConfirmar,
    RecuperacionPasswordSolicitar,
    RecuperacionUsuarioSolicitar,
    UsuarioActualizar,
)
from servicios.autenticacion import autentificar as auth_service


def _usar_solo_memoria(monkeypatch):
    def _ejecutar_redis(_callback, *, fallback):
        return fallback()

    monkeypatch.setattr(redis_cliente, "ejecutar_redis", _ejecutar_redis)


def test_access_token_no_incluye_session_started():
    usuario = {
        "id_usuario": 1,
        "username": "admin",
        "rol": "admin",
        "id_cargo": 2,
    }
    token = tokens.crear_access_token(usuario, ["dashboard"])
    payload = tokens.decodificar_token_tipo(token, "access")

    assert payload["sub"] == "1"
    assert payload["rol"] == "admin"
    assert "session_started" not in payload


def test_sesion_admin_registro_y_renovacion(monkeypatch):
    _usar_solo_memoria(monkeypatch)
    actividad_sesion._actividad_memoria.clear()

    admin_sesion_id = actividad_sesion.crear_sesion_admin(42, "00000000-0000-0000-0000-000000000123")
    assert actividad_sesion.renovar_sesion_admin(
        admin_sesion_id,
        42,
        "00000000-0000-0000-0000-000000000123",
    ) is True

    actividad_sesion.limpiar_sesion_admin(admin_sesion_id)
    assert actividad_sesion.renovar_sesion_admin(
        admin_sesion_id,
        42,
        "00000000-0000-0000-0000-000000000123",
    ) is False


def test_actividad_admin_expira_por_tiempo(monkeypatch):
    _usar_solo_memoria(monkeypatch)
    monkeypatch.setattr(actividad_sesion, "ADMIN_INACTIVIDAD_MINUTOS", 30)
    actividad_sesion._actividad_memoria.clear()

    admin_sesion_id = "admin-test"
    clave = actividad_sesion._clave_admin_sesion(admin_sesion_id)
    actividad_sesion._actividad_memoria[clave] = (
        time.time() - 1,
        {"id_usuario": 7, "id_sesion": "00000000-0000-0000-0000-000000000777"},
    )

    assert actividad_sesion.validar_sesion_admin(
        admin_sesion_id,
        7,
        "00000000-0000-0000-0000-000000000777",
    ) is False
    assert actividad_sesion.renovar_sesion_admin(
        admin_sesion_id,
        7,
        "00000000-0000-0000-0000-000000000777",
    ) is False


def test_es_rol_panel():
    assert es_rol_panel("admin") is True
    assert es_rol_panel("super-admin") is True
    assert es_rol_panel("usuario") is False


def test_hash_token_almacenado_y_compatibilidad_bcrypt():
    token = "refresh-token-ejemplo"
    hash_nuevo = hash_token_almacenado(token)

    assert hash_nuevo.startswith("hmac-sha256:")
    assert verificar_token_almacenado(token, hash_nuevo) is True
    assert verificar_token_almacenado("otro-token", hash_nuevo) is False

    hash_bcrypt = encriptar_texto(token)
    assert verificar_token_almacenado(token, hash_bcrypt) is True


def test_refresh_token_payload():
    token = tokens.crear_refresh_token(99)
    payload = tokens.decodificar_token_tipo(token, "refresh")

    assert payload["sub"] == "99"
    assert payload["typ"] == "refresh"
    assert "jti" in payload
    assert "session_started" not in payload


def test_decodificar_token_tipo_incorrecto():
    usuario = {"id_usuario": 1, "username": "u", "rol": "usuario", "id_cargo": None}
    access = tokens.crear_access_token(usuario, [])

    with pytest.raises(JWTError):
        tokens.decodificar_token_tipo(access, "refresh")


def test_renovar_sesion_no_registra_refresh_como_actividad(monkeypatch):
    usuario = {
        "id_usuario": 8,
        "id_cargo": 2,
        "cargo_nombre": "Admin",
        "nombre_completo": "Admin Uno",
        "username": "admin",
        "email": "admin@example.com",
        "activo": True,
        "autentificacion_doble": False,
        "actualizado_en": "2026-07-03T00:00:00Z",
        "ultimo_acceso_en": None,
        "rol": "admin",
    }
    capturado = {}
    respuesta = object()
    db = MagicMock()

    monkeypatch.setattr(
        auth_service,
        "validar_refresh_token",
        lambda *_args: {
            "id_usuario": usuario["id_usuario"],
            "id_sesion": "00000000-0000-0000-0000-000000000008",
        },
    )
    monkeypatch.setattr(auth_service, "rotar_refresh_token", lambda *_args: "refresh-nuevo")
    monkeypatch.setattr(auth_service, "_buscar_usuario_por_id", lambda *_args: usuario)

    def login_respuesta_fake(_db, _usuario, _response, **kwargs):
        capturado.update(kwargs)
        return respuesta

    monkeypatch.setattr(auth_service, "_login_respuesta", login_respuesta_fake)

    assert auth_service.renovar_sesion(db, "refresh-token", MagicMock()) is respuesta
    assert capturado["crear_admin_sesion"] is False
    assert capturado["id_sesion"] == "00000000-0000-0000-0000-000000000008"
    assert capturado["refresh_token"] == "refresh-nuevo"
    db.commit.assert_called_once()


def test_actualizar_email_verifica_correo_actual(monkeypatch):
    usuario = {
        "id_usuario": 8,
        "id_cargo": 2,
        "cargo_nombre": "Admin",
        "nombre_completo": "Admin Uno",
        "username": "admin",
        "password": "hash",
        "email": "actual@example.com",
        "activo": True,
        "autentificacion_doble": False,
        "actualizado_en": "2026-07-03T00:00:00Z",
        "ultimo_acceso_en": None,
        "rol": "admin",
    }
    verificacion = {}

    def verificar_fake(**kwargs):
        verificacion.update(kwargs)

    row = {
        "id_usuario": 8,
        "id_cargo": 2,
        "username": "admin",
        "email": "nuevo@example.com",
        "activo": True,
        "autentificacion_doble": False,
        "actualizado_en": "2026-07-03T00:00:00Z",
        "ultimo_acceso_en": None,
    }
    resultado = MagicMock()
    resultado.mappings.return_value.one.return_value = row
    db = MagicMock()
    db.execute.return_value = resultado

    monkeypatch.setattr(auth_service, "_validar_credenciales", lambda *_args, **_kwargs: usuario)
    monkeypatch.setattr(auth_service, "_verificar_correo", verificar_fake)
    monkeypatch.setattr(auth_service, "_existe_email", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(auth_service, "registrar_evento", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_service, "_usuario_respuesta", lambda data: data)

    auth_service.actualizar_cuenta(
        db,
        UsuarioActualizar(
            username="admin",
            password="secret",
            nuevo_email="nuevo@example.com",
            codigo_verificacion="123456",
            token_verificacion="token",
        ),
    )

    assert verificacion["email"] == "actual@example.com"
    assert verificacion["proposito"] == "actualizar_credenciales"


def test_solicitar_recuperacion_password_existente_envia_codigo(monkeypatch):
    usuario = {
        "id_usuario": 8,
        "username": "admin",
        "email": "actual@example.com",
        "activo": True,
    }
    monkeypatch.setattr(auth_service, "_buscar_usuario_activo_por_email", lambda *_args: usuario)
    monkeypatch.setattr(
        auth_service,
        "enviar_codigo_verificacion",
        lambda email, proposito: {
            "token_verificacion": f"token-{email}-{proposito}",
            "expira_en_minutos": 10,
        },
    )

    respuesta = auth_service.solicitar_recuperacion_password(
        MagicMock(),
        RecuperacionPasswordSolicitar(email="actual@example.com"),
    )

    assert respuesta.token_verificacion == "token-actual@example.com-recuperar_password"
    assert "cuenta activa" in respuesta.mensaje


def test_solicitar_recuperacion_password_inexistente_respuesta_generica(monkeypatch):
    monkeypatch.setattr(auth_service, "_buscar_usuario_activo_por_email", lambda *_args: None)
    monkeypatch.setattr(
        auth_service,
        "crear_token_verificacion_ficticio",
        lambda email, proposito: f"fake-{email}-{proposito}",
    )

    respuesta = auth_service.solicitar_recuperacion_password(
        MagicMock(),
        RecuperacionPasswordSolicitar(email="nadie@example.com"),
    )

    assert respuesta.token_verificacion == "fake-nadie@example.com-recuperar_password"
    assert "cuenta activa" in respuesta.mensaje


def test_confirmar_recuperacion_password_actualiza_y_revoca(monkeypatch):
    usuario = {
        "id_usuario": 8,
        "username": "admin",
        "email": "actual@example.com",
        "rol": "admin",
    }
    capturado = {}
    db = MagicMock()

    monkeypatch.setattr(auth_service, "_buscar_usuario_activo_por_email", lambda *_args: usuario)
    monkeypatch.setattr(auth_service, "_verificar_correo", lambda **kwargs: capturado.setdefault("verificacion", kwargs))
    monkeypatch.setattr(auth_service, "encriptar_texto", lambda valor: f"hash-{valor}")
    monkeypatch.setattr(auth_service, "revocar_sesiones_usuario", lambda _db, id_usuario: capturado.setdefault("revocado", id_usuario))
    monkeypatch.setattr(auth_service, "limpiar_sesiones_admin_usuario", lambda id_usuario: capturado.setdefault("actividad_limpiada", id_usuario))
    monkeypatch.setattr(auth_service, "registrar_evento", lambda *_args, **_kwargs: None)

    respuesta = auth_service.confirmar_recuperacion_password(
        db,
        RecuperacionPasswordConfirmar(
            email="actual@example.com",
            nuevo_password="Password456",
            codigo_verificacion="123456",
            token_verificacion="token",
        ),
    )

    assert respuesta["mensaje"] == "Contrasena actualizada correctamente"
    assert capturado["verificacion"]["proposito"] == "recuperar_password"
    assert capturado["revocado"] == 8
    assert capturado["actividad_limpiada"] == 8
    db.commit.assert_called_once()


def test_solicitar_recordatorio_usuario_no_devuelve_username(monkeypatch):
    usuario = {
        "nombre_completo": "Admin Uno",
        "username": "admin",
        "email": "actual@example.com",
    }
    enviados = []

    monkeypatch.setattr(auth_service, "_buscar_usuario_activo_por_email", lambda *_args: usuario)
    monkeypatch.setattr(auth_service, "enviar_correo", lambda *args, **kwargs: enviados.append((args, kwargs)))

    respuesta = auth_service.solicitar_recordatorio_usuario(
        MagicMock(),
        RecuperacionUsuarioSolicitar(email="actual@example.com"),
    )

    assert "admin" not in respuesta["mensaje"]
    assert enviados[0][0][0] == "recordatorio_username"
    assert enviados[0][0][2]["username"] == "admin"


def test_regla_correos_distintos_por_ip_bloquea_barrido():
    reglas_seguridad.limpiar_reglas_seguridad_memoria()

    reglas_seguridad.validar_correos_distintos_por_ip(
        regla="recordatorio_username",
        ip="127.0.0.1",
        email="uno@example.com",
        max_correos=2,
    )
    reglas_seguridad.validar_correos_distintos_por_ip(
        regla="recordatorio_username",
        ip="127.0.0.1",
        email="dos@example.com",
        max_correos=2,
    )

    with pytest.raises(HTTPException) as exc:
        reglas_seguridad.validar_correos_distintos_por_ip(
            regla="recordatorio_username",
            ip="127.0.0.1",
            email="tres@example.com",
            max_correos=2,
        )

    assert exc.value.status_code == 429
    reglas_seguridad.limpiar_reglas_seguridad_memoria()


def test_regla_correos_distintos_por_ip_permite_reintentos_mismo_correo():
    reglas_seguridad.limpiar_reglas_seguridad_memoria()

    for _ in range(4):
        reglas_seguridad.validar_correos_distintos_por_ip(
            regla="recordatorio_username",
            ip="127.0.0.2",
            email="mismo@example.com",
            max_correos=2,
        )

    reglas_seguridad.limpiar_reglas_seguridad_memoria()


def test_trazabilidad_enum_incluye_acciones_perfil():
    root = Path(__file__).resolve().parents[2]
    initdb = root / "base_datos/initdb/01-extensions.sql"
    migracion = root / "base_datos/migrations/009_trazabilidad_acciones_perfil.sql"

    initdb_text = initdb.read_text(encoding="utf-8")
    migracion_text = migracion.read_text(encoding="utf-8")

    assert "'cambio_2fa'" in initdb_text
    assert "'cambio_foto_perfil'" in initdb_text
    assert "ADD VALUE IF NOT EXISTS 'cambio_2fa'" in migracion_text
    assert "ADD VALUE IF NOT EXISTS 'cambio_foto_perfil'" in migracion_text
