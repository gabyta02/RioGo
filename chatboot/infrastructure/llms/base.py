from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable


class BaseLLMClient(ABC):
    def __init__(self, provider_name: str, model_name: str) -> None:
        self.provider_name = provider_name
        self.model_name = model_name

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        *,
        thinking_enabled: bool | None = None,
        system_prompt: str | None = None,
        user_content: str | None = None,
        json_response: bool = False,
    ) -> str:
        """Return a text response for the provided prompt."""

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
        """Stream a response and return the accumulated final text."""
        return await self.generate_response(
            prompt,
            thinking_enabled=thinking_enabled,
            system_prompt=system_prompt,
            user_content=user_content,
            json_response=json_response,
        )
