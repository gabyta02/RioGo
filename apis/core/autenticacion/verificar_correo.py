import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from core.correo import EnviarCorreoError, enviar_correo
from core.autenticacion.encriptacion import ALGORITHM, SECRET_KEY, encriptar_texto, verificar_texto
from core.infra.redis_cliente import ejecutar_redis

CODIGO_EXPIRA_MINUTOS = int(os.getenv("CODIGO_CORREO_EXPIRA_MINUTOS", "10"))
_codigos_memoria: dict[str, str] = {}


class ErrorVerificacionCorreo(Exception):
    pass


def generar_codigo_verificacion() -> str:
    return f"{random.SystemRandom().randint(100000, 999999)}"


def _guardar_codigo_activo(email: str, proposito: str, identificador: str) -> None:
    clave = _clave_codigo(email, proposito)
    expiracion = CODIGO_EXPIRA_MINUTOS * 60

    def _en_redis(redis):
        redis.setex(clave, expiracion, identificador)

    def _en_memoria():
        _codigos_memoria[clave] = identificador

    ejecutar_redis(_en_redis, fallback=_en_memoria)


def _obtener_codigo_activo(email: str, proposito: str) -> str | None:
    clave = _clave_codigo(email, proposito)

    def _en_redis(redis):
        return redis.get(clave)

    def _en_memoria():
        return _codigos_memoria.get(clave)

    return ejecutar_redis(_en_redis, fallback=_en_memoria)


def _clave_codigo(email: str, proposito: str) -> str:
    return f"verificacion_correo:{proposito}:{email}"


def _crear_token_verificacion(email: str, proposito: str, codigo: str) -> str:
    identificador = uuid.uuid4().hex
    expiracion = datetime.now(timezone.utc) + timedelta(
        minutes=CODIGO_EXPIRA_MINUTOS
    )
    payload = {
        "email": email,
        "proposito": proposito,
        "codigo_hash": encriptar_texto(codigo),
        "jti": identificador,
        "exp": expiracion,
    }
    _guardar_codigo_activo(email, proposito, identificador)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def crear_token_verificacion_ficticio(email: str, proposito: str) -> str:
    expiracion = datetime.now(timezone.utc) + timedelta(
        minutes=CODIGO_EXPIRA_MINUTOS
    )
    payload = {
        "email": email,
        "proposito": proposito,
        "codigo_hash": encriptar_texto(generar_codigo_verificacion()),
        "jti": uuid.uuid4().hex,
        "exp": expiracion,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def enviar_codigo_verificacion(email: str, proposito: str) -> dict[str, Any]:
    codigo = generar_codigo_verificacion()
    token = _crear_token_verificacion(email, proposito, codigo)
    try:
        enviar_correo(
            "codigo_verificacion",
            email,
            {
                "codigo": codigo,
                "proposito": proposito,
                "expira_minutos": CODIGO_EXPIRA_MINUTOS,
            },
        )
    except EnviarCorreoError as exc:
        raise ErrorVerificacionCorreo(str(exc)) from exc
    return {
        "token_verificacion": token,
        "expira_en_minutos": CODIGO_EXPIRA_MINUTOS,
    }


def verificar_codigo_correo(
    *,
    email: str,
    proposito: str,
    codigo: str,
    token_verificacion: str,
) -> bool:
    try:
        payload = jwt.decode(token_verificacion, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ErrorVerificacionCorreo("Codigo de verificacion invalido o expirado") from exc

    if payload.get("email") != email or payload.get("proposito") != proposito:
        raise ErrorVerificacionCorreo("El codigo no corresponde a esta operacion")

    identificador_activo = _obtener_codigo_activo(email, proposito)
    if not identificador_activo or payload.get("jti") != identificador_activo:
        raise ErrorVerificacionCorreo("Este codigo ya no esta vigente")

    codigo_hash = payload.get("codigo_hash")
    if not codigo_hash or not verificar_texto(codigo, codigo_hash):
        raise ErrorVerificacionCorreo("Codigo de verificacion incorrecto")

    return True
