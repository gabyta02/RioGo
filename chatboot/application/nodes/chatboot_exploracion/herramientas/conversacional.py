from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

from application.shared.empaquetar_mensaje import construir_globo

from .base import ResultadoHerramienta, TipoIds, construir_estado

DATA_FILE = Path(__file__).resolve().parents[4] / "data" / "conversacional.json"


@lru_cache(maxsize=1)
def _cargar_respuestas() -> dict[str, Any]:
    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


async def ejecutar(
    *,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    tipo = str((parametros or {}).get("tipo") or "saludo").strip()
    respuestas = _cargar_respuestas().get("chatboot_exploracion") or {}
    opciones = respuestas.get(tipo) or respuestas.get("saludo") or []
    texto = random.choice(opciones) if opciones else "Hola, ¿qué te gustaría descubrir?"
    mensaje = construir_globo(texto, origen="conversacional")
    payload = {"mensaje_app": mensaje, "texto": texto, "tipo": tipo}
    return (
        construir_estado(
            "conversacional",
            orden,
            "ok",
            payload=payload,
            nota=texto,
        ),
        tipo_ids,
    )
