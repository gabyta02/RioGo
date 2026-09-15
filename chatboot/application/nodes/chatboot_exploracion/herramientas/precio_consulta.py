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
    error_contrato = _validar_contrato_precio(parametros)
    if error_contrato:
        estado_busqueda = construir_estado_busqueda_local(
            herramienta="precio",
            status="error",
            parametros=parametros,
            ids_entrada=ids_consulta,
            nota=error_contrato,
        )
        return (
            construir_estado(
                "precio",
                orden,
                "error",
                payload={"fallo": error_contrato},
                nota=error_contrato,
                estado_busqueda=estado_busqueda,
            ),
            None,
        )
    return await ejecutar_http_generico(
        herramienta="precio",
        endpoint="/precio-consulta",
        orden=orden,
        parametros=parametros,
        ids_consulta=ids_consulta,
        cliente=cliente,
    )


def _validar_contrato_precio(parametros: dict[str, Any]) -> str:
    payload = parametros or {}
    etiqueta = _normalizar_etiqueta_local(payload.get("etiqueta"))
    if etiqueta and etiqueta not in {"economico", "medio", "alto"}:
        return "Contrato inválido: precio.etiqueta debe ser economico, medio o alto."
    if payload.get("precio_numero") is not None:
        operador = str(payload.get("operador") or "").strip()
        if operador not in {"", "=", "<", "<=", ">", ">="}:
            return "Contrato inválido: precio.operador no es válido."
    if (
        payload.get("es_gratuito") is None
        and payload.get("precio_numero") is None
        and not etiqueta
    ):
        return "Contrato inválido: precio requiere es_gratuito, precio_numero o etiqueta."
    return ""


def _normalizar_etiqueta_local(valor: Any) -> str:
    etiqueta = str(valor or "").strip().lower()
    if etiqueta == "moderado":
        return "medio"
    return etiqueta
