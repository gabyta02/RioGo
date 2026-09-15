from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from application.shared.empaquetar_mensaje import construir_globo
from application.shared.sanitizar_plan import PREGUNTA_HERRAMIENTAS, sanitizar_plan_pregunta

PROMPT_FILE = Path(__file__).resolve().parents[1] / "promp" / "crear_plan_pregunta.md"
HERRAMIENTAS_VALIDAS = PREGUNTA_HERRAMIENTAS


@lru_cache(maxsize=1)
def cargar_prompt_crear_plan_pregunta() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def _serializar_palabras(palabras: list[str]) -> list[str]:
    return [str(palabra).strip() for palabra in palabras if str(palabra).strip()]


def construir_payload_clasificacion_pregunta(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "texto_usuario": state.get("texto_usuario", ""),
        "nombre_sitio": state.get("nombre_sitio", ""),
        "prompt_injection": float(state.get("score_prompt_inyection", 0.0)),
        "palabras_inyectadas": _serializar_palabras(
            list(state.get("palabras_inyectadas", []))
        ),
        "contexto_temporal": dict(state.get("contexto_temporal") or {}),
        "memoria": dict(state.get("memoria") or {"turnos": []}),
    }


def construir_mensajes_clasificacion_pregunta(
    state: dict[str, Any],
) -> tuple[str, str, str]:
    payload = construir_payload_clasificacion_pregunta(state)
    bloque_json = json.dumps(payload, ensure_ascii=False, indent=2)
    system_prompt = cargar_prompt_crear_plan_pregunta()
    prompt_completo = f"{system_prompt}\n\n{bloque_json}"
    return system_prompt, bloque_json, prompt_completo


def construir_prompt_clasificacion_pregunta(state: dict[str, Any]) -> str:
    _, _, prompt_completo = construir_mensajes_clasificacion_pregunta(state)
    return prompt_completo


def _extraer_json(texto: str) -> str:
    texto = str(texto or "").strip()
    if not texto:
        return ""

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texto, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio >= 0 and fin > inicio:
        return texto[inicio : fin + 1]
    return texto


def validar_plan_pregunta(raw: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    try:
        parsed = json.loads(_extraer_json(raw))
    except json.JSONDecodeError as exc:
        return None, [{"tipo": "json_invalido", "detalle": str(exc)}]

    if not isinstance(parsed, dict):
        return None, [
            {
                "tipo": "json_invalido",
                "detalle": "La respuesta del LLM debe ser un objeto JSON",
            }
        ]

    if not isinstance(parsed.get("consultas"), list):
        return None, [
            {
                "tipo": "estructura_invalida",
                "detalle": "El plan debe incluir la clave consultas como lista",
            }
        ]

    return sanitizar_plan_pregunta(parsed)


async def crear_plan_pregunta_directa(state: dict[str, Any]) -> dict[str, Any]:
    system_prompt, user_content, prompt = construir_mensajes_clasificacion_pregunta(
        state
    )
    try:
        from infrastructure.llms import get_llm_router

        router = get_llm_router()
        route_settings = router.get_route_settings("sitio")
        client = router.get_client_for_route("sitio")
        respuesta_llm = await client.generate_response(
            "",
            thinking_enabled=route_settings.thinking_enabled,
            system_prompt=system_prompt,
            user_content=user_content,
            json_response=route_settings.json_response,
        )
    except Exception as exc:
        mensaje_sistema = (
            "No pude clasificar tu pregunta sobre este sitio en este momento. "
            "¿Podrías intentarlo otra vez?"
        )
        errores = [{"tipo": "llm_error", "detalle": str(exc)}]
        return {
            **state,
            "prompt_clasificacion": prompt,
            "respuesta_llm_cruda": "",
            "plan": None,
            "plan_valido": False,
            "errores_formato": errores,
            "mensaje_sistema": mensaje_sistema,
            "mensaje_app": construir_globo(
                mensaje_sistema,
                origen="crear_plan_pregunta",
            ),
            "resultado_pregunta_directa": {
                "plan_valido": False,
                "plan": None,
                "errores_formato": errores,
            },
        }

    plan, errores = validar_plan_pregunta(respuesta_llm)
    if errores:
        mensaje_sistema = (
            "No pude clasificar tu pregunta sobre este sitio en este momento. "
            "¿Podrías intentarlo otra vez?"
        )
        return {
            **state,
            "prompt_clasificacion": prompt,
            "respuesta_llm_cruda": respuesta_llm,
            "plan": None,
            "plan_valido": False,
            "errores_formato": errores,
            "mensaje_sistema": mensaje_sistema,
            "mensaje_app": construir_globo(
                mensaje_sistema,
                origen="crear_plan_pregunta",
            ),
            "resultado_pregunta_directa": {
                "plan_valido": False,
                "plan": None,
                "errores_formato": errores,
            },
        }

    return {
        **state,
        "prompt_clasificacion": prompt,
        "respuesta_llm_cruda": respuesta_llm,
        "plan": plan,
        "plan_valido": True,
        "errores_formato": [],
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_pregunta_directa": {
            "plan_valido": True,
            "plan": plan,
            "errores_formato": [],
        },
    }
