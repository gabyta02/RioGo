import os
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

_redis_cliente: Redis | None = None
_memoria_fallback: dict[str, str] = {}


def _resolver_redis_url() -> str | None:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis_url

    redis_host = os.getenv("REDIS_HOST")
    redis_port = os.getenv("REDIS_PORT", "6379")
    if redis_host:
        return f"redis://{redis_host}:{redis_port}/0"

    return None


def obtener_cliente_redis() -> Redis | None:
    global _redis_cliente

    redis_url = _resolver_redis_url()
    if not redis_url:
        return None

    if _redis_cliente is None:
        _redis_cliente = Redis.from_url(redis_url, decode_responses=True)

    return _redis_cliente


def leer_valor(clave: str) -> str | None:
    redis = obtener_cliente_redis()
    if redis is not None:
        try:
            return redis.get(clave)
        except RedisError:
            pass

    return _memoria_fallback.get(clave)


def escribir_valor(clave: str, valor: str, ttl_seconds: int) -> bool:
    redis = obtener_cliente_redis()
    if redis is not None:
        try:
            redis.setex(clave, ttl_seconds, valor)
            return True
        except RedisError:
            pass

    _memoria_fallback[clave] = valor
    return False


def reiniciar_fallback() -> None:
    _memoria_fallback.clear()


def estado_fallback() -> dict[str, Any]:
    return {
        "redis_disponible": obtener_cliente_redis() is not None,
        "claves_fallback": list(_memoria_fallback.keys()),
    }
