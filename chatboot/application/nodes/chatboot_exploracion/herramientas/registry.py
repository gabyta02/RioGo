from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from . import (
    atributos_booleanos_consulta,
    busqueda_referencia,
    busqueda_ubicacion,
    busqueda_semantica_consulta,
    contacto_busqueda,
    conversacional,
    fallback,
    gis_consulta,
    horario_consulta,
    pensamiento_fake,
    pregunta_directa,
    precio_consulta,
    ruta_consulta,
    tarifa_acceso_consulta,
)
from .base import ResultadoHerramienta, TipoIds, construir_estado

EjecutorHerramienta = Callable[..., Awaitable[tuple[ResultadoHerramienta, TipoIds | None]]]

REGISTRY: dict[str, EjecutorHerramienta] = {
    "busqueda_ubicacion": busqueda_ubicacion.ejecutar,
    "busqueda_ubicacion_consulta": busqueda_ubicacion.ejecutar,
    "busqueda_referencia": busqueda_referencia.ejecutar,
    "contactos": contacto_busqueda.ejecutar,
    "contacto_busqueda": contacto_busqueda.ejecutar,
    "horario": horario_consulta.ejecutar,
    "horario_consulta": horario_consulta.ejecutar,
    "precio": precio_consulta.ejecutar,
    "precio_consulta": precio_consulta.ejecutar,
    "tarifa_acceso": tarifa_acceso_consulta.ejecutar,
    "tarifa_acceso_consulta": tarifa_acceso_consulta.ejecutar,
    "atributos_booleanos": atributos_booleanos_consulta.ejecutar,
    "atributos_booleanos_consulta": atributos_booleanos_consulta.ejecutar,
    "ruta": ruta_consulta.ejecutar,
    "ruta_consulta": ruta_consulta.ejecutar,
    "gis": gis_consulta.ejecutar,
    "gis_consulta": gis_consulta.ejecutar,
    "busqueda_semantica": busqueda_semantica_consulta.ejecutar,
    "busqueda_semantica_consulta": busqueda_semantica_consulta.ejecutar,
    "conversacional": conversacional.ejecutar,
    "fallback": fallback.ejecutar,
    "pensamiento_fake": pensamiento_fake.ejecutar,
    "pregunta_directa": pregunta_directa.ejecutar,
    "pregunta-directa": pregunta_directa.ejecutar,
}


async def ejecutar_herramienta(
    *,
    nombre: str,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    nombre_normalizado = str(nombre or "").strip()
    ejecutor = REGISTRY.get(nombre_normalizado)
    if ejecutor is None:
        return (
            construir_estado(
                nombre_normalizado or "desconocida",
                orden,
                "error",
                payload={"fallo": f"Herramienta no registrada: {nombre_normalizado}"},
                nota=f"Herramienta no registrada: {nombre_normalizado}",
            ),
            tipo_ids,
        )

    return await ejecutor(
        orden=orden,
        parametros=parametros,
        ids_consulta=ids_consulta,
        tipo_ids=tipo_ids,
        state=state,
        cliente=cliente,
    )
