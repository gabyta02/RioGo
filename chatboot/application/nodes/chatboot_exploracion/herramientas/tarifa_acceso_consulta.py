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
    error_contrato = _validar_contrato_tarifa(parametros)
    if error_contrato:
        estado_busqueda = construir_estado_busqueda_local(
            herramienta="tarifa_acceso",
            status="error",
            parametros=parametros,
            ids_entrada=ids_consulta,
            nota=error_contrato,
        )
        return (
            construir_estado(
                "tarifa_acceso",
                orden,
                "error",
                payload={"fallo": error_contrato},
                nota=error_contrato,
                estado_busqueda=estado_busqueda,
            ),
            None,
        )
    return await ejecutar_http_generico(
        herramienta="tarifa_acceso",
        endpoint="/tarifa-acceso-consulta",
        orden=orden,
        parametros=parametros,
        ids_consulta=ids_consulta,
        cliente=cliente,
    )


def _validar_contrato_tarifa(parametros: dict[str, Any]) -> str:
    payload = parametros or {}
    etiqueta = _normalizar_etiqueta_local(payload.get("etiqueta"))
    condicion = _normalizar_condicion_local(payload.get("condicion"))
    if etiqueta and etiqueta not in {"economico", "medio", "alto"}:
        return "Contrato inválido: tarifa_acceso.etiqueta debe ser economico, medio o alto."
    if condicion and condicion not in {
        "general",
        "adulto",
        "nino",
        "joven",
        "estudiante",
        "tercera_edad",
        "discapacidad",
    }:
        return "Contrato inválido: tarifa_acceso.condicion no es válida."
    if payload.get("precio_numero") is not None:
        operador = str(payload.get("operador") or "").strip()
        if operador not in {"", "=", "<", "<=", ">", ">="}:
            return "Contrato inválido: tarifa_acceso.operador no es válido."
    if (
        payload.get("entrada_gratuita") is None
        and payload.get("precio_numero") is None
        and not etiqueta
        and not condicion
    ):
        return (
            "Contrato inválido: tarifa_acceso requiere entrada_gratuita, "
            "precio_numero, etiqueta o condicion."
        )
    return ""


def _normalizar_etiqueta_local(valor: Any) -> str:
    etiqueta = str(valor or "").strip().lower()
    if etiqueta == "moderado":
        return "medio"
    return etiqueta


def _normalizar_condicion_local(valor: Any) -> str:
    condicion = str(valor or "").strip().lower().replace("_", " ")
    if condicion in {
        "todo publico",
        "todo público",
        "todo el publico",
        "todo el público",
        "todos",
        "todos los publicos",
        "todos los públicos",
        "publico",
        "público",
    }:
        return "general"
    if condicion == "tercera edad":
        return "tercera_edad"
    return condicion.replace(" ", "_")
