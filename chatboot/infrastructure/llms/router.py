from functools import lru_cache

from infrastructure.config import AppSettings, RouteLLMSettings, get_settings

from .base import BaseLLMClient
from .registry import LLM_PROVIDER_REGISTRY


class LLMRouter:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._clients: dict[tuple[str, str], BaseLLMClient] = {}

    def get_route_settings(self, route_name: str) -> RouteLLMSettings:
        return self._settings.llm.routes.get(route_name, RouteLLMSettings())

    def get_client_for_route(self, route_name: str) -> BaseLLMClient:
        llm_settings = self._settings.llm
        route_settings = llm_settings.routes.get(route_name)

        provider_name = llm_settings.default_provider
        if route_settings and route_settings.provider:
            provider_name = route_settings.provider

        if provider_name not in llm_settings.providers:
            raise ValueError(f"Provider '{provider_name}' is not configured")

        provider_settings = llm_settings.providers[provider_name]
        if not provider_settings.enabled:
            raise ValueError(f"Provider '{provider_name}' is disabled")

        model_name = provider_settings.model
        if provider_name == llm_settings.default_provider:
            model_name = llm_settings.default_model or provider_settings.model
        if route_settings and route_settings.model:
            model_name = route_settings.model

        cache_key = (provider_name, model_name)
        if cache_key in self._clients:
            return self._clients[cache_key]

        factory = LLM_PROVIDER_REGISTRY.get(provider_name)
        if factory is None:
            raise ValueError(f"Provider '{provider_name}' is not implemented")

        client = factory(provider_name, model_name)
        self._clients[cache_key] = client
        return client


@lru_cache(maxsize=1)
def get_llm_router() -> LLMRouter:
    return LLMRouter(get_settings())
