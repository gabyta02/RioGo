from __future__ import annotations

from typing import Any


def construir_texto_precio_resumen(sitio: Any) -> str:
    if sitio.es_gratuito is True:
        return "Gratuita"

    if sitio.es_gratuito is False:
        if sitio.precio:
            precio_min = sitio.precio.precio_min
            precio_max = sitio.precio.precio_max
            if precio_min is not None and precio_max is not None:
                if precio_min == precio_max:
                    return f"${float(precio_min):.2f}"
                return f"${float(precio_min):.2f} - ${float(precio_max):.2f}"

            if precio_min is not None:
                return f"Desde ${float(precio_min):.2f}"

            if precio_max is not None:
                return f"Hasta ${float(precio_max):.2f}"

            if sitio.precio.etiqueta_precio:
                return str(sitio.precio.etiqueta_precio)

        if sitio.tarifas:
            tarifa = sitio.tarifas[0]
            return f"{tarifa.condicion}: ${float(tarifa.precio):.2f}"

        return "Consultar costo"

    return "No disponible"
