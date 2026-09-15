from __future__ import annotations

import os
import asyncio
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
import json

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - fallback para entornos mínimos
    httpx = None


class ClienteHerramientasHTTP:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("APIS_BASE_URL") or "http://localhost").rstrip("/")
        self.timeout_seconds = float(
            timeout_seconds or os.getenv("APIS_TIMEOUT_SECONDS") or 15
        )
        self.retry_attempts = max(1, int(os.getenv("APIS_RETRY_ATTEMPTS") or 2))
        self.retry_delay_seconds = max(
            0.0,
            float(os.getenv("APIS_RETRY_DELAY_SECONDS") or 0.25),
        )
        self._httpx_client: httpx.AsyncClient | None = None

    def _client(self, timeout: float) -> httpx.AsyncClient:
        if self._httpx_client is None or self._httpx_client.is_closed:
            self._httpx_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=timeout,
                limits=httpx.Limits(
                    max_connections=int(os.getenv("APIS_HTTP_MAX_CONNECTIONS", "100")),
                    max_keepalive_connections=int(
                        os.getenv("APIS_HTTP_MAX_KEEPALIVE_CONNECTIONS", "20")
                    ),
                ),
            )
        return self._httpx_client

    def _path_herramienta(self, endpoint: str) -> str:
        endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        return f"/api/v1/chatboot/herramientas{endpoint}"

    async def post_herramienta(
        self,
        endpoint: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        path = self._path_herramienta(endpoint)
        timeout = float(timeout_seconds or self.timeout_seconds)
        if httpx is not None:
            return await self._request_httpx_con_reintentos(
                metodo="POST",
                path=path,
                timeout=timeout,
                json_payload=payload,
                esperado=dict,
            )

        return await _request_json_thread(
            url=f"{self.base_url}{path}",
            metodo="POST",
            headers={},
            payload=payload,
            timeout_seconds=timeout,
            esperado=dict,
        )

    async def listar_sitios(self) -> list[dict[str, Any]]:
        path = "/api/v1/sitios/"
        if httpx is not None:
            data = await self._request_httpx_con_reintentos(
                metodo="GET",
                path=path,
                timeout=self.timeout_seconds,
                json_payload=None,
                esperado=list,
            )
            return [item for item in data if isinstance(item, dict)]

        data = await _request_json_thread(
            url=f"{self.base_url}{path}",
            metodo="GET",
            headers={},
            payload=None,
            timeout_seconds=self.timeout_seconds,
            esperado=list,
        )
        return [item for item in data if isinstance(item, dict)]

    async def obtener_ficha_sitio(self, id_sitio: int) -> dict[str, Any] | None:
        path = f"/api/v1/ficha_sitio/{int(id_sitio)}"
        if httpx is not None:
            try:
                return await self._request_httpx_con_reintentos(
                    metodo="GET",
                    path=path,
                    timeout=self.timeout_seconds,
                    json_payload=None,
                    esperado=dict,
                    permitir_404=True,
                )
            except _RecursoNoEncontrado:
                return None

        try:
            data = await _request_json_thread(
                url=f"{self.base_url}{path}",
                metodo="GET",
                headers={},
                payload=None,
                timeout_seconds=self.timeout_seconds,
                esperado=dict,
            )
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise
        return data

    async def obtener_opciones_fallback_exploracion(self) -> list[dict[str, Any]]:
        path = "/api/v1/chatboot/fallback/opciones-exploracion"
        if httpx is not None:
            data = await self._request_httpx_con_reintentos(
                metodo="GET",
                path=path,
                timeout=self.timeout_seconds,
                json_payload=None,
                esperado=dict,
            )
        else:
            data = await _request_json_thread(
                url=f"{self.base_url}{path}",
                metodo="GET",
                headers={},
                payload=None,
                timeout_seconds=self.timeout_seconds,
                esperado=dict,
            )
        opciones = data.get("opciones") if isinstance(data, dict) else []
        return [item for item in opciones if isinstance(item, dict)]

    async def _request_httpx_con_reintentos(
        self,
        *,
        metodo: str,
        path: str,
        timeout: float,
        json_payload: dict[str, Any] | None,
        esperado: type,
        permitir_404: bool = False,
    ) -> Any:
        ultimo_error: Exception | None = None
        for intento in range(1, self.retry_attempts + 1):
            try:
                client = self._client(timeout)
                response = await client.request(
                    metodo,
                    path,
                    json=json_payload,
                )
                if permitir_404 and response.status_code == 404:
                    raise _RecursoNoEncontrado()
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, esperado):
                    raise ValueError("La API devolvió una respuesta con forma inesperada.")
                return data
            except Exception as exc:
                if isinstance(exc, _RecursoNoEncontrado):
                    raise
                ultimo_error = exc
                if intento >= self.retry_attempts or not _es_error_transitorio_httpx(exc):
                    raise
                await asyncio.sleep(self.retry_delay_seconds * intento)
        if ultimo_error is not None:
            raise ultimo_error
        raise RuntimeError("No se pudo completar la llamada a la API.")


class _RecursoNoEncontrado(Exception):
    pass


async def _request_json_thread(
    *,
    url: str,
    metodo: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None,
    timeout_seconds: float,
    esperado: type,
) -> Any:
    import asyncio

    return await asyncio.to_thread(
        _request_json_sync,
        url=url,
        metodo=metodo,
        headers=headers,
        payload=payload,
        timeout_seconds=timeout_seconds,
        esperado=esperado,
    )


def _request_json_sync(
    *,
    url: str,
    metodo: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None,
    timeout_seconds: float,
    esperado: type,
) -> Any:
    body = None
    request_headers = dict(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["content-type"] = "application/json"

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
    except (TimeoutError, URLError) as exc:
        raise RuntimeError(_describir_error_urlopen(exc)) from exc

    data = json.loads(raw)
    if not isinstance(data, esperado):
        raise ValueError("La API devolvió una respuesta con forma inesperada.")
    return data


def _es_error_transitorio_httpx(exc: Exception) -> bool:
    if httpx is None:
        return False
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600
    return False


def _describir_error_urlopen(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "La llamada a la API excedió el tiempo de espera."
    motivo = getattr(exc, "reason", None)
    if isinstance(motivo, TimeoutError):
        return "La llamada a la API excedió el tiempo de espera."
    return str(exc) or type(exc).__name__
