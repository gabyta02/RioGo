from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from application.shared.empaquetar_mensaje import construir_globo
from application.shared.sanitizar_plan import sanitizar_plan_exploracion

PROMPT_FILE = Path(__file__).resolve().parents[1] / "promp" / "crear_plan.md"
PLACEHOLDER = "##inyectar memoria##"


@lru_cache(maxsize=1)
def cargar_prompt_crear_plan() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def _serializar_palabras(palabras: list[Any]) -> list[Any]:
    serializadas: list[Any] = []
    for palabra in palabras:
        if isinstance(palabra, dict):
            item = {
                clave: valor
                for clave, valor in palabra.items()
                if valor not in (None, "", [])
            }
            if item:
                serializadas.append(item)
            continue
        texto = str(palabra).strip()
        if texto:
            serializadas.append(texto)
    return serializadas


def _extraer_correcciones(palabras: list[Any]) -> list[dict[str, Any]]:
    correcciones: list[dict[str, Any]] = []
    for palabra in palabras:
        if not isinstance(palabra, dict):
            continue
        if not palabra.get("correccion_sugerida"):
            continue
        correcciones.append(
            {
                "original": palabra.get("texto_detectado"),
                "corregido": palabra.get("termino_normalizado")
                or str(palabra.get("palabra", "")).replace("_", " "),
                "confianza": palabra.get("confianza"),
                "score": palabra.get("score"),
                "significado": palabra.get("significado"),
            }
        )
    return correcciones


def construir_payload_clasificacion(state: dict[str, Any]) -> dict[str, Any]:
    texto_usuario = state.get("texto_usuario", "")
    riesgo = float(state.get("score_prompt_inyection", 0.0))
    palabras_raw = list(state.get("palabras_inyectadas", []))
    palabras = _serializar_palabras(palabras_raw)
    correcciones = _extraer_correcciones(palabras_raw)
    return {
        "texto_usuario": texto_usuario,
        "texto_limpio": texto_usuario,
        "prompt_inyeccion": riesgo,
        "riesgo_prompt_inyection": riesgo,
        "palabra_inyectada": palabras,
        "palabras_inyectadas": palabras,
        "correcciones_detectadas": correcciones,
        "contexto_temporal": dict(state.get("contexto_temporal") or {}),
        "memoria": dict(state.get("memoria") or {"turnos": []}),
    }


def construir_mensajes_clasificacion(
    state: dict[str, Any],
) -> tuple[str, str, str]:
    payload = construir_payload_clasificacion(state)
    bloque_json = json.dumps(payload, ensure_ascii=False, indent=2)
    system_prompt = cargar_prompt_crear_plan()
    if PLACEHOLDER in system_prompt:
        system_prompt = system_prompt.replace(PLACEHOLDER, "").strip()
    prompt_completo = f"{system_prompt}\n\n{bloque_json}"
    return system_prompt, bloque_json, prompt_completo


def construir_prompt_clasificacion(state: dict[str, Any]) -> str:
    _, _, prompt_completo = construir_mensajes_clasificacion(state)
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


def _validar_plan_estructura(raw: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
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

    return parsed, []


async def crear_plan_exploracion(state: dict[str, Any]) -> dict[str, Any]:
    system_prompt, user_content, prompt = construir_mensajes_clasificacion(state)
    try:
        from infrastructure.llms import get_llm_router

        router = get_llm_router()
        route_settings = router.get_route_settings("exploracion_plan")
        client = router.get_client_for_route("exploracion_plan")
        respuesta_llm = await client.generate_response(
            "",
            thinking_enabled=route_settings.thinking_enabled,
            system_prompt=system_prompt,
            user_content=user_content,
            json_response=route_settings.json_response,
        )
    except Exception as exc:
        mensaje_sistema = (
            "No pude clasificar tu consulta correctamente en este momento. "
            "¿Podrías intentarlo otra vez?"
        )
        return {
            **state,
            "prompt_clasificacion": prompt,
            "respuesta_llm_cruda": "",
            "plan": None,
            "plan_valido": False,
            "errores_formato": [{"tipo": "llm_error", "detalle": str(exc)}],
            "mensaje_sistema": mensaje_sistema,
            "mensaje_app": construir_globo(
                mensaje_sistema,
                origen="crear_plan_tools",
            ),
            "resultado_exploracion": {
                "plan_valido": False,
                "plan": None,
                "errores_formato": [{"tipo": "llm_error", "detalle": str(exc)}],
            },
        }

    plan, errores = _validar_plan_estructura(respuesta_llm)

    if errores:
        mensaje_sistema = (
            "No pude clasificar tu consulta correctamente en este momento. "
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
                origen="crear_plan_tools",
            ),
            "resultado_exploracion": {
                "plan_valido": False,
                "plan": None,
                "errores_formato": errores,
            },
        }

    plan, errores_sanitizacion = sanitizar_plan_exploracion(plan)
    if plan is None:
        errores = errores_sanitizacion
        mensaje_sistema = (
            "No pude clasificar tu consulta correctamente en este momento. "
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
                origen="crear_plan_tools",
            ),
            "resultado_exploracion": {
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
        "errores_formato": errores_sanitizacion,
        "mensaje_sistema": None,
        "mensaje_app": None,
        "resultado_exploracion": {
            "plan_valido": True,
            "plan": plan,
            "errores_formato": errores_sanitizacion,
        },
    }
