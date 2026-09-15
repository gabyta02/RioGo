from __future__ import annotations

import hashlib
import os

from core.infra.redis_cliente import ejecutar_redis

_CACHE_MEMORIA: dict[str, str] = {}
_TTL_SEGUNDOS = int(os.getenv("EMBEDDING_CACHE_TTL", "86400"))
_PREFIJO_REDIS = "emb:v1:"


def _clave_cache(texto: str, input_type: str, modelo: str) -> str:
    digest = hashlib.sha256(
        f"{modelo}:{input_type}:{texto}".encode("utf-8"),
    ).hexdigest()
    return f"{_PREFIJO_REDIS}{digest}"


def leer_embedding_cache(texto: str, input_type: str, modelo: str) -> str | None:
    clave = _clave_cache(texto, input_type, modelo)

    def _desde_redis(redis):
        return redis.get(clave)

    resultado = ejecutar_redis(_desde_redis, fallback=lambda: _CACHE_MEMORIA.get(clave))
    return resultado if resultado else None


def guardar_embedding_cache(
    texto: str,
    input_type: str,
    modelo: str,
    embedding: str,
) -> None:
    clave = _clave_cache(texto, input_type, modelo)

    def _en_redis(redis):
        redis.setex(clave, _TTL_SEGUNDOS, embedding)
        return True

    ejecutar_redis(
        _en_redis,
        fallback=lambda: _CACHE_MEMORIA.update({clave: embedding}) or True,
    )


def limpiar_cache_embedding() -> None:
    _CACHE_MEMORIA.clear()
