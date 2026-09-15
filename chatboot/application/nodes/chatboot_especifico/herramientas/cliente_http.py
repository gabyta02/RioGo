from __future__ import annotations

import json
import os
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - fallback para entornos mínimos
    httpx = None


class ClientePreguntaDirectaHTTP:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("APIS_BASE_URL") or "http://localhost"
        ).rstrip("/")
        self.timeout_seconds = float(
            timeout_seconds or os.getenv("APIS_TIMEOUT_SECONDS") or 15
        )
        self._httpx_client: httpx.AsyncClient | None = None

    def _client(self) -> httpx.AsyncClient:
        if self._httpx_client is None or self._httpx_client.is_closed:
            self._httpx_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                limits=httpx.Limits(
                    max_connections=int(os.getenv("APIS_HTTP_MAX_CONNECTIONS", "100")),
                    max_keepalive_connections=int(
                        os.getenv("APIS_HTTP_MAX_KEEPALIVE_CONNECTIONS", "20")
                    ),
                ),
            )
        return self._httpx_client

    def _path(self, endpoint: str) -> str:
        endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        return f"/api/v1/chatboot/pregunta-directa{endpoint}"

    async def post(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        path = self._path(endpoint)
        if httpx is not None:
            client = self._client()
            response = await client.post(
                path,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("La API devolvió una respuesta no JSON objeto.")
            return data

        return await _request_json_thread(
            url=f"{self.base_url}{path}",
            metodo="POST",
            headers={},
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )


async def _request_json_thread(
    *,
    url: str,
    metodo: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    import asyncio

    return await asyncio.to_thread(
        _request_json_sync,
        url=url,
        metodo=metodo,
        headers=headers,
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def _request_json_sync(
    *,
    url: str,
    metodo: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    request_headers = {**headers, "content-type": "application/json"}
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=body,
        headers=request_headers,
        method=metodo.upper(),
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detalle}") from exc

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("La API devolvió una respuesta con forma inesperada.")
    return data
