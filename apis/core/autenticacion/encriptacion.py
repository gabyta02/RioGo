import hashlib
import hmac
import os
from pathlib import Path

from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256").strip().strip('"').strip("'")
_HASH_TOKEN_PREFIX = "hmac-sha256:"

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no esta configurada en el archivo .env")

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def encriptar_texto(texto: str) -> str:
    return bcrypt_context.hash(texto)


def verificar_texto(texto: str, texto_encriptado: str) -> bool:
    return bcrypt_context.verify(texto, texto_encriptado)


def hash_token_almacenado(token: str) -> str:
    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{_HASH_TOKEN_PREFIX}{digest}"


def verificar_token_almacenado(token: str, hash_guardado: str) -> bool:
    if not hash_guardado:
        return False
    if hash_guardado.startswith(_HASH_TOKEN_PREFIX):
        esperado = hash_token_almacenado(token)
        return hmac.compare_digest(esperado, hash_guardado)
    return verificar_texto(token, hash_guardado)
