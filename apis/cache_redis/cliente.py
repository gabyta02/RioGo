import json
from typing import Any

from redis import ConnectionPool, Redis

from cache_redis.config import REDIS_MAX_CONNECTIONS, REDIS_SOCKET_TIMEOUT, REDIS_URL


class RedisCliente:
    def __init__(
        self,
        url: str = REDIS_URL,
        timeout: float = REDIS_SOCKET_TIMEOUT,
        max_connections: int = REDIS_MAX_CONNECTIONS,
    ):
        self.pool = ConnectionPool.from_url(
            url,
            decode_responses=True,
            max_connections=max_connections,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
        )
        self.cliente = Redis(connection_pool=self.pool)

    def ping(self) -> bool:
        return bool(self.cliente.ping())

    def get_json(self, clave: str) -> Any | None:
        valor = self.cliente.get(clave)
        if valor is None:
            return None
        return json.loads(valor)

    def set_json(self, clave: str, valor: Any) -> None:
        payload = json.dumps(valor, ensure_ascii=False, default=str)
        self.cliente.set(clave, payload)

    def get(self, clave: str) -> str | None:
        return self.cliente.get(clave)

    def set(self, clave: str, valor: Any) -> None:
        self.cliente.set(clave, valor)

    def set_if_absent(self, clave: str, valor: Any, ex: int | None = None) -> bool:
        return bool(self.cliente.set(clave, valor, nx=True, ex=ex))

    def delete(self, clave: str) -> int:
        return int(self.cliente.delete(clave))

    def incr(self, clave: str) -> int:
        return int(self.cliente.incr(clave))

    def delete_pattern(self, patron: str) -> int:
        total = 0
        for clave in self.cliente.scan_iter(match=patron):
            total += self.cliente.delete(clave)
        return total

    def hset_json(self, clave: str, campo: str, valor: Any) -> int:
        payload = json.dumps(valor, ensure_ascii=False, default=str)
        return int(self.cliente.hset(clave, campo, payload))

    def hdel(self, clave: str, campo: str) -> int:
        return int(self.cliente.hdel(clave, campo))

    def hgetall_json(self, clave: str) -> dict[str, Any]:
        valores = self.cliente.hgetall(clave)
        return {
            campo: json.loads(valor)
            for campo, valor in valores.items()
        }

    def hlen(self, clave: str) -> int:
        return int(self.cliente.hlen(clave))
