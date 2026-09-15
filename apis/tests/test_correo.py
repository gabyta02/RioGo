import pytest

from core.correo.enrutador import enviar_correo
from core.correo.renderizado import renderizar_correo
from core.correo.tipos import METADATA_CODIGO_VERIFICACION, contexto_codigo_verificacion


def test_render_codigo_verificacion_login_2fa():
    contexto = contexto_codigo_verificacion(
        codigo="123456",
        proposito="login_2fa",
        expira_minutos=10,
    )
    contexto.update(
        {
            "marca": "RiobambaTour",
            "color_primario": "#0D5A38",
            "color_acento": "#FF7A00",
        }
    )

    html, texto = renderizar_correo("codigo_verificacion", contexto)

    assert "123456" in html
    assert "123456" in texto
    assert "Verificacion de acceso" in html
    assert METADATA_CODIGO_VERIFICACION["login_2fa"]["asunto"]


def test_render_cuenta_admin_creada():
    contexto = {
        "marca": "RiobambaTour",
        "color_primario": "#0D5A38",
        "color_acento": "#FF7A00",
        "nombre_completo": "Maria Yanez",
        "username": "admin.maria",
        "password_temporal": "RbGo-abc123",
        "url_panel": "https://example.com/admin/",
        "asunto": "Tu cuenta administrativa en RiobambaTour",
    }

    html, texto = renderizar_correo("cuenta_admin_creada", contexto)

    assert "Maria Yanez" in html
    assert "admin.maria" in texto
    assert "RbGo-abc123" in html
    assert "https://example.com/admin/" in html


def test_render_recordatorio_username():
    contexto = {
        "marca": "RiobambaTour",
        "color_primario": "#0D5A38",
        "color_acento": "#FF7A00",
        "nombre_completo": "Maria Yanez",
        "username": "admin.maria",
        "asunto": "Tu nombre de usuario RiobambaTour",
    }

    html, texto = renderizar_correo("recordatorio_username", contexto)

    assert "Maria Yanez" in html
    assert "admin.maria" in html
    assert "admin.maria" in texto


def test_enrutador_codigo_verificacion(monkeypatch):
    enviados: list[dict] = []

    def _capturar(**kwargs):
        enviados.append(kwargs)

    monkeypatch.setattr("core.correo.enrutador.enviar_correo_multipart", _capturar)

    enviar_correo(
        "codigo_verificacion",
        "usuario@example.com",
        {
            "codigo": "654321",
            "proposito": "registro_usuario",
            "expira_minutos": 10,
        },
    )

    assert len(enviados) == 1
    assert enviados[0]["destinatario"] == "usuario@example.com"
    assert enviados[0]["asunto"] == METADATA_CODIGO_VERIFICACION["registro_usuario"]["asunto"]
    assert "654321" in enviados[0]["cuerpo_html"]
    assert "654321" in enviados[0]["cuerpo_texto"]


def test_enrutador_recordatorio_username(monkeypatch):
    enviados: list[dict] = []

    def _capturar(**kwargs):
        enviados.append(kwargs)

    monkeypatch.setattr("core.correo.enrutador.enviar_correo_multipart", _capturar)

    enviar_correo(
        "recordatorio_username",
        "usuario@example.com",
        {
            "nombre_completo": "Maria Yanez",
            "username": "admin.maria",
        },
    )

    assert len(enviados) == 1
    assert enviados[0]["destinatario"] == "usuario@example.com"
    assert enviados[0]["asunto"] == "Tu nombre de usuario RiobambaTour"
    assert "admin.maria" in enviados[0]["cuerpo_html"]
    assert "admin.maria" in enviados[0]["cuerpo_texto"]


def test_enrutador_accion_invalida():
    with pytest.raises(ValueError, match="no soportada"):
        enviar_correo("accion_inexistente", "a@b.com", {})
