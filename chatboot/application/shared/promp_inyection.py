from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from application.state import RiesgoPromptInyection, SharedFlowState
from infrastructure.config import get_settings

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "promp_inyection.json"


@lru_cache(maxsize=1)
def cargar_prompt_inyection_data() -> dict[str, Any]:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _settings():
    return get_settings().tools.shared.promp_inyection


def _pattern_groups() -> dict[str, list[dict[str, Any]]]:
    return dict(cargar_prompt_inyection_data().get("pattern_groups", {}))


def _responses() -> dict[str, str]:
    return dict(cargar_prompt_inyection_data().get("responses", {}))


def _riesgo_vacio() -> RiesgoPromptInyection:
    return {
        "score": 0.0,
        "porcentaje": 0.0,
        "bloqueado": False,
        "coincidencias": [],
        "motivo_principal": None,
    }


def evaluar_prompt_inyection(texto: str) -> RiesgoPromptInyection:
    texto = str(texto or "")
    score = 0.0
    coincidencias: list[dict[str, Any]] = []

    for group_name, items in _pattern_groups().items():
        for item in items:
            patrones = item.get("patrones", [])
            matched = any(
                re.search(pattern, texto, flags=re.IGNORECASE | re.DOTALL)
                for pattern in patrones
            )
            if not matched:
                continue

            score += float(item.get("peso", 0.0))
            coincidencias.append(
                {
                    "grupo": group_name,
                    "motivo": item.get("motivo", ""),
                    "peso": item.get("peso", 0.0),
                    "descripcion": item.get("descripcion", ""),
                }
            )

    score = max(0.0, score)
    bloqueado = score >= _settings().umbral_bloqueo
    return {
        "score": round(score, 4),
        "porcentaje": round(min(score, 1.0) * 100, 2),
        "bloqueado": bloqueado,
        "coincidencias": coincidencias,
        "motivo_principal": coincidencias[0]["motivo"] if coincidencias else None,
    }


def ejecutar_prompt_inyection(state: SharedFlowState) -> SharedFlowState:
    evaluacion = evaluar_prompt_inyection(state.get("mensaje_limpio", ""))
    responses = _responses()
    bloqueado = bool(evaluacion["bloqueado"])
    mensaje_sistema = (
        responses.get("bloqueado") or responses.get("default")
        if bloqueado
        else state.get("mensaje_sistema")
    )
    return {
        **state,
        "riesgo_prompt_inyection": evaluacion,
        "bloqueado": bloqueado,
        "motivo_bloqueo": evaluacion["motivo_principal"] if bloqueado else None,
        "mensaje_sistema": mensaje_sistema,
        "origen_mensaje_sistema": "promp_inyection" if bloqueado else state.get("origen_mensaje_sistema"),
    }


RIESGO_PROMPT_INYECTION_VACIO = _riesgo_vacio()
