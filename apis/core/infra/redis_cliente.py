import os
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis
from redis.exceptions import RedisError

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

REDIS_URL = os.getenv("REDIS_URL")
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "0.25"))
REDIS_SOCKET_CONNECT_TIMEOUT = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "0.25"))

_redis_cliente: Redis | None = None


def obtener_redis() -> Redis | None:
    global _redis_cliente
    if not REDIS_URL:
        return None

    if _redis_cliente is None:
        _redis_cliente = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
        )

    return _redis_cliente


def ejecutar_redis(callback, *, fallback):
    redis = obtener_redis()
    if redis:
        try:
            return callback(redis)
        except RedisError:
            pass
    return fallback()
