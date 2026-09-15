import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"
SETTINGS_FILE = Path(__file__).resolve().with_name("settings.json")


class ProviderSettings(BaseModel):
    enabled: bool = True
    name: str
    model: str
    base_url: str | None = None
    api_key_env: str
    timeout_seconds: float = 30.0
    sdk: Literal["anthropic", "openai"] = "openai"
    max_tokens: int = 8192
    thinking_enabled: bool = True
    output_effort: Literal["high", "max"] = "high"
    reasoning_effort: str | None = None
    thinking_type: str | None = None


class RouteLLMSettings(BaseModel):
    provider: str | None = None
    model: str | None = None
    stream: bool = False
    stream_thinking: bool = True
    thinking_enabled: bool | None = None
    json_response: bool = False


class ConstruirPlanNodeSettings(BaseModel):
    estado_inicial: str = "analizando_consulta"
    mensaje_inicial: str = "Estoy entendiendo lo que buscas..."
    estado_validando: str = "validando_plan"
    mensaje_validando: str = "Estoy organizando tu consulta..."


class EjecutarPlanNodeSettings(BaseModel):
    estado_inicial: str = "ejecutando_plan"
    mensaje_inicial: str = "Estoy ejecutando las herramientas del plan..."
    estado_final: str = "fin_ejecucion"
    mensaje_final: str = "Ejecución del plan completada."


class LimpiezaSettings(BaseModel):
    max_palabras_mensaje: int = 80
    max_repeticion_caracter: int = 2
    max_saltos_linea_consecutivos: int = 2
    min_digitos_sin_contexto: int = 5


class PromptInyectionSettings(BaseModel):
    umbral_bloqueo: float = 0.80


class InyectarPalabraSettings(BaseModel):
    rapidfuzz_score_minimo: int = 85
    rapidfuzz_score_medio: int = 90
    rapidfuzz_score_alto: int = 95
    max_etiquetas: int = 8
    ventana_ngrams_max: int = 4


class SharedToolsSettings(BaseModel):
    limpieza: LimpiezaSettings = Field(default_factory=LimpiezaSettings)
    promp_inyection: PromptInyectionSettings = Field(
        default_factory=PromptInyectionSettings
    )
    inyectar_palabra: InyectarPalabraSettings = Field(
        default_factory=InyectarPalabraSettings
    )


class ToolsSettings(BaseModel):
    shared: SharedToolsSettings = Field(default_factory=SharedToolsSettings)


class MemorySettings(BaseModel):
    enabled: bool = True
    key_prefix: str = "chatboot:memoria:planificador"
    ttl_seconds: int = 3600
    max_preguntas: int = 20


class LLMSettings(BaseModel):
    default_provider: str
    default_model: str
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)
    routes: dict[str, RouteLLMSettings] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_defaults(self) -> "LLMSettings":
        if self.default_provider not in self.providers:
            raise ValueError(
                f"Default provider '{self.default_provider}' is not declared in llm.providers"
            )

        provider = self.providers[self.default_provider]
        if not provider.enabled:
            raise ValueError(
                f"Default provider '{self.default_provider}' is disabled in llm.providers"
            )

        return self


class PreparacionNodeSettings(BaseModel):
    estado: str = "preparando_consulta"
    mensaje: str = "Preparando consulta..."


class NodesSettings(BaseModel):
    preparacion: PreparacionNodeSettings = Field(
        default_factory=PreparacionNodeSettings
    )
    construir_plan: ConstruirPlanNodeSettings = Field(
        default_factory=ConstruirPlanNodeSettings
    )
    ejecutar_plan: EjecutarPlanNodeSettings = Field(
        default_factory=EjecutarPlanNodeSettings
    )


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    llm: LLMSettings
    nodes: NodesSettings = Field(default_factory=NodesSettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)


def _load_raw_settings() -> dict[str, Any]:
    load_dotenv(ENV_FILE)

    with SETTINGS_FILE.open("r", encoding="utf-8") as settings_file:
        data = json.load(settings_file)

    timeout_seconds = os.getenv("LLM_TIMEOUT_SECONDS")
    if timeout_seconds:
        for provider in (data.get("llm", {}).get("providers") or {}).values():
            if isinstance(provider, dict):
                provider["timeout_seconds"] = float(timeout_seconds)

    max_tokens = os.getenv("LLM_MAX_TOKENS")
    if max_tokens:
        for provider in (data.get("llm", {}).get("providers") or {}).values():
            if isinstance(provider, dict):
                provider["max_tokens"] = int(max_tokens)

    return data


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings.model_validate(_load_raw_settings())
