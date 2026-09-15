import json
import logging
from typing import Any

from infrastructure.config.settings import get_settings
from infrastructure.memory.client import escribir_valor, leer_valor
from infrastructure.memory.schemas import MemoriaPlanificador, MemoriaSitio

logger = logging.getLogger(__name__)


def _clave_memoria(sesion_id: str) -> str:
    settings = get_settings().memory
    return f"{settings.key_prefix}:{sesion_id}"


def _clave_memoria_sitio(sesion_id: str) -> str:
    return f"chatboot:memoria:sitio:{sesion_id}"


def cargar_memoria(sesion_id: str) -> dict[str, Any]:
    if not sesion_id:
        return MemoriaPlanificador.vacia("").model_dump(mode="json")

    settings = get_settings().memory
    if not settings.enabled:
        return MemoriaPlanificador.vacia(sesion_id).model_dump(mode="json")

    clave = _clave_memoria(sesion_id)
    try:
        raw = leer_valor(clave)
        if not raw:
            return MemoriaPlanificador.vacia(sesion_id).model_dump(mode="json")

        parsed = json.loads(raw)
        memoria = MemoriaPlanificador.model_validate(parsed)
        if memoria.sesion_id != sesion_id:
            memoria.sesion_id = sesion_id
        return memoria.model_dump(mode="json")
    except Exception as exc:
        logger.warning(
            "No se pudo cargar memoria para sesion_id=%s: %s",
            sesion_id,
            exc,
        )
        return MemoriaPlanificador.vacia(sesion_id).model_dump(mode="json")


def guardar_memoria(sesion_id: str, memoria: dict[str, Any]) -> dict[str, Any]:
    if not sesion_id:
        return memoria

    settings = get_settings().memory
    if not settings.enabled:
        return memoria

    try:
        modelo = MemoriaPlanificador.model_validate(
            {
                **memoria,
                "sesion_id": sesion_id,
            }
        )
        payload = modelo.model_dump(mode="json")
        clave = _clave_memoria(sesion_id)
        escribir_valor(
            clave,
            json.dumps(payload, ensure_ascii=False),
            settings.ttl_seconds,
        )
        return payload
    except Exception as exc:
        logger.warning(
            "No se pudo guardar memoria para sesion_id=%s: %s",
            sesion_id,
            exc,
        )
        return memoria


def cargar_memoria_sitio(sesion_id: str) -> dict[str, Any]:
    if not sesion_id:
        return MemoriaSitio.vacia("").model_dump(mode="json")

    settings = get_settings().memory
    if not settings.enabled:
        return MemoriaSitio.vacia(sesion_id).model_dump(mode="json")

    clave = _clave_memoria_sitio(sesion_id)
    try:
        raw = leer_valor(clave)
        if not raw:
            return MemoriaSitio.vacia(sesion_id).model_dump(mode="json")

        parsed = json.loads(raw)
        memoria = MemoriaSitio.model_validate(parsed)
        if memoria.sesion_id != sesion_id:
            memoria.sesion_id = sesion_id
        return memoria.model_dump(mode="json")
    except Exception as exc:
        logger.warning(
            "No se pudo cargar memoria de sitio para sesion_id=%s: %s",
            sesion_id,
            exc,
        )
        return MemoriaSitio.vacia(sesion_id).model_dump(mode="json")


def guardar_memoria_sitio(sesion_id: str, memoria: dict[str, Any]) -> dict[str, Any]:
    if not sesion_id:
        return memoria

    settings = get_settings().memory
    if not settings.enabled:
        return memoria

    try:
        modelo = MemoriaSitio.model_validate(
            {
                **memoria,
                "sesion_id": sesion_id,
            }
        )
        payload = modelo.model_dump(mode="json")
        escribir_valor(
            _clave_memoria_sitio(sesion_id),
            json.dumps(payload, ensure_ascii=False),
            settings.ttl_seconds,
        )
        return payload
    except Exception as exc:
        logger.warning(
            "No se pudo guardar memoria de sitio para sesion_id=%s: %s",
            sesion_id,
            exc,
        )
        return memoria
