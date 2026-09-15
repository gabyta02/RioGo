import os
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from jose import JWTError, jwt

from core.autenticacion.encriptacion import ALGORITHM, SECRET_KEY

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
TOKEN_REFRESH_MINUTES = int(os.getenv("TOKEN_REFRESH_MINUTES", "30"))


def _ahora_utc():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _crear_token(
    datos: dict[str, Any],
    *,
    tipo: str,
    expira_en: timedelta,
) -> str:
    emitido_en = _ahora_utc()
    payload = datos.copy()
    payload.update(
        {
            "typ": tipo,
            "iat": int(emitido_en.timestamp()),
            "exp": emitido_en + expira_en,
        }
    )
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def crear_access_token(
    usuario: dict[str, Any],
    permisos: list[str],
    id_sesion: str | None = None,
) -> str:
    payload = {
        "sub": str(usuario["id_usuario"]),
        "username": usuario["username"],
        "rol": usuario["rol"],
        "id_cargo": usuario.get("id_cargo"),
        "permisos": permisos,
    }
    if id_sesion:
        payload["sid"] = str(id_sesion)

    return _crear_token(
        payload,
        tipo="access",
        expira_en=timedelta(minutes=ACCESS_TOKEN_MINUTES),
    )


def crear_refresh_token(id_usuario: int) -> str:
    return _crear_token(
        {
            "sub": str(id_usuario),
            "jti": uuid.uuid4().hex,
        },
        tipo="refresh",
        expira_en=timedelta(days=REFRESH_TOKEN_DAYS),
    )


def decodificar_token_tipo(token: str, tipo_esperado: str) -> dict[str, Any]:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("typ") != tipo_esperado:
        raise JWTError("Tipo de token invalido")
    return payload


def segundos_access_token() -> int:
    return ACCESS_TOKEN_MINUTES * 60


def segundos_token_refresh() -> int:
    return TOKEN_REFRESH_MINUTES * 60
