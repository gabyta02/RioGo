from __future__ import annotations

from collections import defaultdict
from typing import Any

_NOMBRES_DIA = {
    1: "Lun",
    2: "Mar",
    3: "Mié",
    4: "Jue",
    5: "Vie",
    6: "Sáb",
    7: "Dom",
}


def _formatear_hora(valor) -> str:
    if valor is None:
        return ""
    return valor.strftime("%H:%M")


def _agrupar_dias_consecutivos(dias: list[int]) -> list[str]:
    if not dias:
        return []

    ordenados = sorted(set(dias))
    grupos: list[list[int]] = []
    grupo_actual = [ordenados[0]]

    for dia in ordenados[1:]:
        if dia == grupo_actual[-1] + 1:
            grupo_actual.append(dia)
        else:
            grupos.append(grupo_actual)
            grupo_actual = [dia]
    grupos.append(grupo_actual)

    etiquetas: list[str] = []
    for grupo in grupos:
        if len(grupo) == 1:
            etiquetas.append(_NOMBRES_DIA.get(grupo[0], f"Día {grupo[0]}"))
        else:
            inicio = _NOMBRES_DIA.get(grupo[0], f"Día {grupo[0]}")
            fin = _NOMBRES_DIA.get(grupo[-1], f"Día {grupo[-1]}")
            etiquetas.append(f"{inicio}-{fin}")
    return etiquetas


def _construir_texto_franjas(franjas_por_dias: dict[tuple[str, str], list[int]]) -> str:
    partes: list[str] = []
    for (hora_inicio, hora_fin), dias in sorted(
        franjas_por_dias.items(),
        key=lambda item: min(item[1]),
    ):
        rango_hora = f"{hora_inicio}-{hora_fin}"
        dias_ordenados = sorted(dias)

        if len(dias_ordenados) == 7:
            partes.append(f"Todos los días: {rango_hora}")
            continue

        etiquetas = _agrupar_dias_consecutivos(dias_ordenados)
        partes.append(f"{', '.join(etiquetas)}: {rango_hora}")

    return " | ".join(partes) if partes else "No disponible"


def construir_horario_compacto(horario) -> dict[str, Any]:
    if not horario or not getattr(horario, "activo", True):
        return {
            "abierto_24h": False,
            "texto": "No disponible",
            "comentario": None,
        }

    comentario = (horario.comentario or "").strip() or None

    if horario.abierto_24h:
        return {
            "abierto_24h": True,
            "texto": "Abierto 24 horas",
            "comentario": comentario,
        }

    detalles = [
        detalle
        for detalle in (horario.detalles or [])
        if getattr(detalle, "activo", True)
        and detalle.hora_inicio
        and detalle.hora_fin
    ]

    if not detalles:
        return {
            "abierto_24h": False,
            "texto": "No disponible",
            "comentario": comentario,
        }

    franjas_por_dias: dict[tuple[str, str], list[int]] = defaultdict(list)
    for detalle in detalles:
        clave = (
            _formatear_hora(detalle.hora_inicio),
            _formatear_hora(detalle.hora_fin),
        )
        franjas_por_dias[clave].append(int(detalle.dia_semana))

    return {
        "abierto_24h": False,
        "texto": _construir_texto_franjas(franjas_por_dias),
        "comentario": comentario,
    }
