import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

GMAIL_USUARIO = (
    os.getenv("GMAIL_USUARIO")
    or os.getenv("GMAIL_USER")
    or os.getenv("GMAIL_EMAIL")
)
GMAIL_CLAVE_APLICATION = os.getenv("GMAIL_CLAVE_APLICATION")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

CORREO_FROM_EMAIL = os.getenv("CORREO_FROM_EMAIL") or GMAIL_USUARIO
CORREO_FROM_NOMBRE = os.getenv("CORREO_FROM_NOMBRE", "RiobambaTour")
CORREO_REPLY_TO = os.getenv("CORREO_REPLY_TO") or CORREO_FROM_EMAIL
CORREO_URL_PANEL = os.getenv("CORREO_URL_PANEL", "https://www.riobambatour.org/admin/")
CORREO_MARCA_COLOR_PRIMARIO = os.getenv("CORREO_MARCA_COLOR_PRIMARIO", "#0D5A38")
CORREO_MARCA_COLOR_ACENTO = os.getenv("CORREO_MARCA_COLOR_ACENTO", "#FF7A00")

PLANTILLAS_DIR = Path(__file__).resolve().parent / "plantillas"
