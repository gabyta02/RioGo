import asyncio
import logging
import os
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from infrastructure.config import get_settings

from .base import BaseLLMClient

logger = logging.getLogger(__name__)
_LLM_SEMAPHORE = threading.BoundedSemaphore(
    max(1, int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", "16")))
)


async def _adquirir_llm_slot() -> None:
    while True:
        if _LLM_SEMAPHORE.acquire(blocking=False):
            return
        await asyncio.sleep(0.01)


def _liberar_llm_slot() -> None:
    _LLM_SEMAPHORE.release()


def _retry_attempts() -> int:
    return max(1, int(os.getenv("LLM_RETRY_ATTEMPTS", "3")))


def _retry_base_seconds() -> float:
    return max(0.0, float(os.getenv("LLM_RETRY_BASE_SECONDS", "0.5")))


def _es_error_transitorio(exc: Exception) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


async def _esperar_reintento(intento: int) -> None:
    espera = _retry_base_seconds() * (2 ** max(0, intento - 1))
    if espera > 0:
        await asyncio.sleep(espera)


class DeepSeekLLMClient(BaseLLMClient):
    def __init__(self, provider_name: str, model_name: str) -> None:
        super().__init__(provider_name=provider_name, model_name=model_name)

        self._provider_settings = get_settings().llm.providers[provider_name]
        api_key = os.getenv(self._provider_settings.api_key_env)
        if not api_key:
            raise ValueError(
                f"Missing API key for provider '{provider_name}'. "
                f"Expected env var '{self._provider_settings.api_key_env}'."
            )

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=self._provider_settings.base_url,
            timeout=self._provider_settings.timeout_seconds,
        )

    def _resolver_thinking_enabled(self, thinking_enabled: bool | None) -> bool:
        if thinking_enabled is not None:
            return thinking_enabled
        return self._provider_settings.thinking_enabled

    def _construir_mensajes(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        user_content: str | None = None,
    ) -> list[dict[str, str]]:
        if system_prompt is not None and user_content is not None:
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]

        contenido = prompt or user_content or system_prompt or ""
        return [{"role": "user", "content": contenido}]

    def _openai_request_kwargs(
        self,
        prompt: str,
        *,
        thinking_enabled: bool | None = None,
        system_prompt: str | None = None,
        user_content: str | None = None,
        stream: bool = False,
        json_response: bool = False,
    ) -> dict[str, Any]:
        usar_thinking = self._resolver_thinking_enabled(thinking_enabled)
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._construir_mensajes(
                prompt,
                system_prompt=system_prompt,
                user_content=user_content,
            ),
            "stream": stream,
            "extra_body": {
                "thinking": {"type": "enabled" if usar_thinking else "disabled"}
            },
        }

        if self._provider_settings.max_tokens:
            kwargs["max_tokens"] = self._provider_settings.max_tokens

        reasoning_effort = self._provider_settings.reasoning_effort
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        if json_response:
            kwargs["response_format"] = {"type": "json_object"}

        return kwargs

    @staticmethod
    def _extraer_contenido(message: Any) -> str:
        return getattr(message, "content", None) or ""

    async def generate_response(
        self,
        prompt: str,
        *,
        thinking_enabled: bool | None = None,
        system_prompt: str | None = None,
        user_content: str | None = None,
        json_response: bool = False,
    ) -> str:
        inicio = time.perf_counter()
        kwargs = self._openai_request_kwargs(
            prompt,
            thinking_enabled=thinking_enabled,
            system_prompt=system_prompt,
            user_content=user_content,
            json_response=json_response,
        )
        ultimo_error: Exception | None = None
        for intento in range(1, _retry_attempts() + 1):
            try:
                await _adquirir_llm_slot()
                try:
                    completion = await self._client.chat.completions.create(**kwargs)
                finally:
                    _liberar_llm_slot()
                duracion = time.perf_counter() - inicio
                logger.info(
                    "llm_call provider=%s model=%s stream=false json=%s attempt=%s duration_seconds=%.3f",
                    self.provider_name,
                    self.model_name,
                    json_response,
                    intento,
                    duracion,
                )
                return self._extraer_contenido(completion.choices[0].message)
            except Exception as exc:
                ultimo_error = exc
                transitorio = _es_error_transitorio(exc)
                status_code = getattr(exc, "status_code", None)
                logger.warning(
                    "llm_error provider=%s model=%s stream=false json=%s attempt=%s transient=%s status_code=%s error_type=%s error=%s",
                    self.provider_name,
                    self.model_name,
                    json_response,
                    intento,
                    transitorio,
                    status_code,
                    type(exc).__name__,
                    str(exc),
                )
                if intento >= _retry_attempts() or not transitorio:
                    raise
                await _esperar_reintento(intento)

        if ultimo_error is not None:
            raise ultimo_error
        raise RuntimeError("No se pudo completar la llamada al LLM.")

    async def generate_response_stream(
        self,
        prompt: str,
        *,
        thinking_enabled: bool | None = None,
        system_prompt: str | None = None,
        user_content: str | None = None,
        json_response: bool = False,
        on_thinking_delta: Callable[[str], Awaitable[None]] | None = None,
        on_content_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        inicio = time.perf_counter()
        contenido_acumulado: list[str] = []
        kwargs = self._openai_request_kwargs(
            prompt,
            thinking_enabled=thinking_enabled,
            system_prompt=system_prompt,
            user_content=user_content,
            stream=True,
            json_response=json_response,
        )
        ultimo_error: Exception | None = None
        for intento in range(1, _retry_attempts() + 1):
            try:
                await _adquirir_llm_slot()
                try:
                    stream = await self._client.chat.completions.create(**kwargs)

                    async for chunk in stream:
                        if not chunk.choices:
                            continue

                        delta = chunk.choices[0].delta
                        reasoning = getattr(delta, "reasoning_content", None)
                        if reasoning and on_thinking_delta:
                            await on_thinking_delta(str(reasoning))
                            continue

                        texto = getattr(delta, "content", None) or ""
                        if not texto:
                            continue

                        contenido_acumulado.append(texto)
                        if on_content_delta:
                            await on_content_delta(texto)
                finally:
                    _liberar_llm_slot()

                duracion = time.perf_counter() - inicio
                logger.info(
                    "llm_call provider=%s model=%s stream=true json=%s attempt=%s duration_seconds=%.3f",
                    self.provider_name,
                    self.model_name,
                    json_response,
                    intento,
                    duracion,
                )
                break
            except Exception as exc:
                ultimo_error = exc
                transitorio = _es_error_transitorio(exc)
                status_code = getattr(exc, "status_code", None)
                logger.warning(
                    "llm_error provider=%s model=%s stream=true json=%s attempt=%s transient=%s status_code=%s partial_content=%s error_type=%s error=%s",
                    self.provider_name,
                    self.model_name,
                    json_response,
                    intento,
                    transitorio,
                    status_code,
                    bool(contenido_acumulado),
                    type(exc).__name__,
                    str(exc),
                )
                if contenido_acumulado or intento >= _retry_attempts() or not transitorio:
                    raise
                await _esperar_reintento(intento)

        if contenido_acumulado:
            return "".join(contenido_acumulado)

        if ultimo_error is not None:
            raise ultimo_error

        return await self.generate_response(
            prompt,
            thinking_enabled=thinking_enabled,
            system_prompt=system_prompt,
            user_content=user_content,
            json_response=json_response,
        )
