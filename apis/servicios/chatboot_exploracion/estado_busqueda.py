from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from esquemas.chatboot_comun import EstadoBusqueda, EstadoFiltroBusqueda, FiltroBusqueda


def _serializar_valor(valor: Any) -> Any:
    if isinstance(valor, BaseModel):
        return valor.model_dump(mode="json")
    if isinstance(valor, dict):
        return {str(k): _serializar_valor(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_serializar_valor(item) for item in valor]
    return valor


def construir_estado_busqueda(
    *,
    nombre: str,
    estado: EstadoFiltroBusqueda,
    valor: Any,
    ids_entrada: list[int] | None = None,
    ids_salida: list[int] | None = None,
    detalle: str = "",
    retroalimentacion: dict[str, Any] | BaseModel | None = None,
) -> EstadoBusqueda:
    ids_entrada = [int(item) for item in ids_entrada or []]
    ids_salida = [int(item) for item in ids_salida or []]
    filtro = FiltroBusqueda(
        nombre=nombre,
        valor=_serializar_valor(valor) if isinstance(_serializar_valor(valor), dict) else {"valor": _serializar_valor(valor)},
        estado=estado,
        detalle=detalle,
    )
    return EstadoBusqueda(
        estado=estado,
        ids_entrada=ids_entrada,
        ids_salida=ids_salida,
        filtros=[filtro],
        retroalimentacion=(
            _serializar_valor(retroalimentacion)
            if retroalimentacion is not None
            else {}
        ),
    )
