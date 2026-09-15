import smtplib
import uuid
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from core.correo.configuracion import (
    CORREO_FROM_EMAIL,
    CORREO_FROM_NOMBRE,
    CORREO_REPLY_TO,
    GMAIL_CLAVE_APLICATION,
    GMAIL_USUARIO,
    SMTP_HOST,
    SMTP_PORT,
)


class EnviarCorreoError(Exception):
    pass


def _remitente_formateado() -> str:
    email = (CORREO_FROM_EMAIL or GMAIL_USUARIO or "").strip()
    if not email:
        return ""
    nombre = (CORREO_FROM_NOMBRE or "").strip()
    if nombre:
        return formataddr((nombre, email))
    return email


def enviar_correo_multipart(
    destinatario: str,
    asunto: str,
    cuerpo_texto: str,
    cuerpo_html: str,
) -> None:
    destino = destinatario.strip()
    if not destino:
        raise EnviarCorreoError("El destinatario del correo es obligatorio")

    if not GMAIL_USUARIO or not GMAIL_CLAVE_APLICATION:
        raise EnviarCorreoError(
            "No estan configuradas las credenciales SMTP para enviar correos"
        )

    remitente = _remitente_formateado()
    if not remitente:
        raise EnviarCorreoError("No esta configurado el remitente del correo")

    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destino
    mensaje["Subject"] = asunto
    mensaje["Date"] = formatdate(localtime=True)
    mensaje["Message-ID"] = f"<{uuid.uuid4().hex}@riobambatour>"
    mensaje["Reply-To"] = (CORREO_REPLY_TO or CORREO_FROM_EMAIL or GMAIL_USUARIO).strip()
    mensaje.set_content(cuerpo_texto, charset="utf-8")
    mensaje.add_alternative(cuerpo_html, subtype="html", charset="utf-8")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(GMAIL_USUARIO, GMAIL_CLAVE_APLICATION)
            smtp.send_message(mensaje)
    except smtplib.SMTPException as exc:
        raise EnviarCorreoError("No se pudo enviar el correo") from exc


def enviar_correo_texto(destinatario: str, asunto: str, cuerpo: str) -> None:
    enviar_correo_multipart(
        destinatario=destinatario,
        asunto=asunto,
        cuerpo_texto=cuerpo,
        cuerpo_html=f"<pre style='font-family:sans-serif'>{cuerpo}</pre>",
    )
