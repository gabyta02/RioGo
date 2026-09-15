from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.state import ContextoTemporal, DiaContextoTemporal, SharedFlowState

DIAS_SEMANA = [
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
]

DIAS_SEMANA_ETIQUETA = [
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
]


def _zona_horaria() -> str:
    return os.getenv("CHATBOOT_TIMEZONE") or "America/Guayaquil"


def _resolver_zona_horaria(nombre_zona: str) -> ZoneInfo:
    try:
        return ZoneInfo(nombre_zona)
    except ZoneInfoNotFoundError:
        try:
            return ZoneInfo("America/Guayaquil")
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")


def _relativo(indice: int) -> str | None:
    if indice == 0:
        return "hoy"
    if indice == 1:
        return "mañana"
    if indice == 2:
        return "pasado_mañana"
    return None


def _dia(fecha: date, indice: int) -> DiaContextoTemporal:
    weekday = fecha.weekday()
    dia: DiaContextoTemporal = {
        "fecha": fecha.isoformat(),
        "dia_semana": DIAS_SEMANA[weekday],
        "dia_semana_etiqueta": DIAS_SEMANA_ETIQUETA[weekday],
    }
    relativo = _relativo(indice)
    if relativo:
        dia["relativo"] = relativo
    return dia


def construir_contexto_temporal(
    ahora: datetime | None = None,
    *,
    dias_adelante: int = 14,
) -> ContextoTemporal:
    nombre_zona = _zona_horaria()
    zona = _resolver_zona_horaria(nombre_zona)
    ahora_local = ahora.astimezone(zona) if ahora else datetime.now(zona)
    fecha_actual = ahora_local.date()
    dias = [
        _dia(fecha_actual + timedelta(days=indice), indice)
        for indice in range(dias_adelante)
    ]
    proxima_ocurrencia: dict[str, str] = {}
    for dia in dias:
        proxima_ocurrencia.setdefault(dia["dia_semana"], dia["fecha"])

    return {
        "zona_horaria": str(zona.key),
        "fecha_actual": fecha_actual.isoformat(),
        "dia_actual": DIAS_SEMANA[fecha_actual.weekday()],
        "dia_actual_etiqueta": DIAS_SEMANA_ETIQUETA[fecha_actual.weekday()],
        "hora_actual": ahora_local.strftime("%H:%M"),
        "dias": dias,
        "proxima_ocurrencia": proxima_ocurrencia,
    }


def ejecutar_inyectar_fecha(state: SharedFlowState) -> SharedFlowState:
    return {
        **state,
        "contexto_temporal": construir_contexto_temporal(),
    }
