from typing import Any

from core.correo.configuracion import (
    CORREO_MARCA_COLOR_ACENTO,
    CORREO_MARCA_COLOR_PRIMARIO,
    CORREO_URL_PANEL,
)
from core.correo.renderizado import renderizar_correo
from core.correo.tipos import (
    AccionCorreo,
    contexto_codigo_verificacion,
    contexto_cuenta_admin_creada,
    contexto_recordatorio_username,
)
from core.correo.transporte import enviar_correo_multipart


def _contexto_base(extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "marca": "RiobambaTour",
        "color_primario": CORREO_MARCA_COLOR_PRIMARIO,
        "color_acento": CORREO_MARCA_COLOR_ACENTO,
        **extra,
    }


def enviar_correo(
    accion: AccionCorreo,
    destinatario: str,
    contexto: dict[str, Any],
) -> None:
    if accion == "codigo_verificacion":
        datos = contexto_codigo_verificacion(
            codigo=str(contexto["codigo"]),
            proposito=str(contexto["proposito"]),
            expira_minutos=int(contexto["expira_minutos"]),
        )
        render_ctx = _contexto_base(datos)
        html, texto = renderizar_correo("codigo_verificacion", render_ctx)
        asunto = datos["asunto"]
    elif accion == "cuenta_admin_creada":
        datos = contexto_cuenta_admin_creada(
            nombre_completo=str(contexto["nombre_completo"]),
            username=str(contexto["username"]),
            password_temporal=str(contexto["password_temporal"]),
            url_panel=str(contexto.get("url_panel") or CORREO_URL_PANEL),
        )
        render_ctx = _contexto_base(datos)
        html, texto = renderizar_correo("cuenta_admin_creada", render_ctx)
        asunto = datos["asunto"]
    elif accion == "recordatorio_username":
        datos = contexto_recordatorio_username(
            nombre_completo=contexto.get("nombre_completo"),
            username=str(contexto["username"]),
        )
        render_ctx = _contexto_base(datos)
        html, texto = renderizar_correo("recordatorio_username", render_ctx)
        asunto = datos["asunto"]
    else:
        raise ValueError(f"Accion de correo no soportada: {accion}")

    enviar_correo_multipart(
        destinatario=destinatario,
        asunto=asunto,
        cuerpo_texto=texto,
        cuerpo_html=html,
    )
