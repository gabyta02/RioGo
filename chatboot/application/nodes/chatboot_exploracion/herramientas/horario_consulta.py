from __future__ import annotations

from typing import Any

from .base import (
    ResultadoHerramienta,
    TipoIds,
    construir_estado,
    construir_estado_busqueda_local,
    ejecutar_http_generico,
)


async def ejecutar(
    *,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    error_contrato = _validar_contrato_horario(parametros)
    if error_contrato:
        estado_busqueda = construir_estado_busqueda_local(
            herramienta="horario",
            status="error",
            parametros=parametros,
            ids_entrada=ids_consulta,
            nota=error_contrato,
        )
        return (
            construir_estado(
                "horario",
                orden,
                "error",
                payload={"fallo": error_contrato},
                nota=error_contrato,
                estado_busqueda=estado_busqueda,
            ),
            None,
        )

    return await ejecutar_http_generico(
        herramienta="horario",
        endpoint="/horario-consulta",
        orden=orden,
        parametros=parametros,
        ids_consulta=ids_consulta,
        cliente=cliente,
    )


def _validar_contrato_horario(parametros: dict[str, Any]) -> str:
    payload = parametros or {}
    tipo = str(payload.get("tipo") or "").strip()
    if tipo == "relacional":
        comparador = str(payload.get("comparador") or "").strip()
        if not payload.get("hora"):
            return "Contrato inválido: horario relacional requiere hora."
        if comparador not in {"mayor_que", "menor_que"}:
            return (
                "Contrato inválido: horario relacional requiere comparador "
                "'mayor_que' o 'menor_que'."
            )
    if tipo == "punto_tiempo" and not payload.get("hora"):
        return "Contrato inválido: horario punto_tiempo requiere hora."
    if tipo == "bloque_tiempo" and not payload.get("rango_hora"):
        return "Contrato inválido: horario bloque_tiempo requiere rango_hora."
    if tipo == "dias_solamente" and not (
        payload.get("dia_semana") or payload.get("dias_semana")
    ):
        return "Contrato inválido: horario dias_solamente requiere dia_semana o dias_semana."
    return ""
