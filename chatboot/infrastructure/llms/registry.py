from collections.abc import Callable

from .base import BaseLLMClient
from .deepseek import DeepSeekLLMClient

LLMFactory = Callable[[str, str], BaseLLMClient]

LLM_PROVIDER_REGISTRY: dict[str, LLMFactory] = {
    "deepseek": DeepSeekLLMClient,
}
