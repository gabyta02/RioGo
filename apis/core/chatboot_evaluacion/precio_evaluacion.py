from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.filtro_sitios import agregar_filtro_ids

OperadorPrecioInterno = Literal["exacto", "min", "max", "lt", "gt"]

ETIQUETAS_PRECIO: dict[str, tuple[str, ...]] = {
    "economico": ("economico", "barato", "barata", "economica"),
    "medio": ("medio", "mediana", "mediano", "moderado", "moderada", "intermedio"),
    "alto": ("alto", "alta", "caro", "cara", "premium", "lujo", "costoso", "costosa"),
}


def normalizar_etiqueta(texto: str) -> str | None:
    termino = texto.strip().lower()
    if not termino:
        return None
    if termino in {"economico", "medio", "alto"}:
        return termino
    if termino == "moderado":
        return "medio"
    for etiqueta, alias in ETIQUETAS_PRECIO.items():
        if termino in alias:
            return etiqueta
    return None


def normalizar_etiquetas_excluidas(terminos: list[str]) -> list[str]:
    etiquetas: list[str] = []
    for termino in terminos:
        etiqueta = normalizar_etiqueta(termino)
        if etiqueta and etiqueta not in etiquetas:
            etiquetas.append(etiqueta)
    return etiquetas


def mapear_operador(operador: str) -> OperadorPrecioInterno | None:
    return {
        "": "exacto",
        "=": "exacto",
        "<=": "min",
        "<": "lt",
        ">=": "max",
        ">": "gt",
    }.get(operador)


def _a_float(valor: Any) -> float:
    if isinstance(valor, Decimal):
        return float(valor)
    return float(valor)


def obtener_datos_precio_sitios(
    db: Session,
    ids_consulta: list[int],
) -> dict[int, dict[str, Any]]:
    filtros_sql: list[str] = []
    params: dict[str, Any] = {}
    agregar_filtro_ids(filtros_sql, params, ids_consulta)
    alcance_sql = ""
    if filtros_sql:
        alcance_sql = " AND " + " AND ".join(filtros_sql)

    sitios_rows = db.execute(
        text(
            f"""
            SELECT s.id_sitio, s.es_gratuito
            FROM turismo.sitio s
            WHERE s.activo = TRUE
              {alcance_sql}
            ORDER BY s.id_sitio ASC
            """
        ),
        params,
    ).mappings().all()

    sitios: dict[int, dict[str, Any]] = {
        int(row["id_sitio"]): {
            "es_gratuito": row["es_gratuito"],
            "rangos": [],
        }
        for row in sitios_rows
    }
    if not sitios:
        return sitios

    rangos_rows = db.execute(
        text(
            """
            SELECT
                rp.id_sitio,
                rp.precio_min,
                rp.precio_max,
                rp.etiqueta_precio::text AS etiqueta_precio
            FROM turismo.rango_precio rp
            WHERE rp.activo = TRUE
              AND rp.id_sitio = ANY(:ids_sitios)
            ORDER BY rp.id_sitio ASC, rp.precio_min ASC, rp.id_rango_precio ASC
            """
        ),
        {"ids_sitios": list(sitios.keys())},
    ).mappings().all()

    for row in rangos_rows:
        id_sitio = int(row["id_sitio"])
        sitios[id_sitio]["rangos"].append(
            {
                "precio_min": _a_float(row["precio_min"]),
                "precio_max": _a_float(row["precio_max"]),
                "etiqueta_precio": row["etiqueta_precio"],
            }
        )
    return sitios


def rango_cumple_filtro(
    precio_min: float,
    precio_max: float,
    etiqueta_precio: str | None,
    etiqueta: str | None,
    precio_numero: float | None,
    operador: OperadorPrecioInterno | None,
) -> bool:
    if etiqueta and etiqueta_precio and etiqueta_precio != etiqueta:
        return False

    if precio_numero is None:
        if etiqueta:
            return etiqueta_precio is None or etiqueta_precio == etiqueta
        return False

    if operador == "exacto":
        return precio_min <= precio_numero <= precio_max
    if operador == "min":
        return precio_max <= precio_numero
    if operador == "max":
        return precio_min >= precio_numero
    if operador == "lt":
        return precio_max < precio_numero
    if operador == "gt":
        return precio_min > precio_numero
    return False


def _seleccionar_mejor_rango(
    rangos: list[dict[str, Any]],
    operador: OperadorPrecioInterno | None,
) -> dict[str, Any]:
    if operador in {"max", "gt"}:
        return max(rangos, key=lambda item: item["precio_max"])
    return min(rangos, key=lambda item: item["precio_min"])


def sitio_cumple_es_gratuito(
    es_gratuito_sitio: bool | None,
    filtro: bool,
) -> bool:
    if filtro:
        return es_gratuito_sitio is True
    return es_gratuito_sitio is False


def filtrar_sitios_por_precio(
    sitios_datos: dict[int, dict[str, Any]],
    es_gratuito: bool | None,
    etiqueta: str | None,
    precio_numero: float | None,
    operador: OperadorPrecioInterno | None,
    etiquetas_excluidas: list[str],
) -> list[int]:
    ids_coincidentes: list[int] = []
    necesita_rango = etiqueta is not None or precio_numero is not None

    for id_sitio, datos in sitios_datos.items():
        if es_gratuito is not None and not sitio_cumple_es_gratuito(
            datos["es_gratuito"], es_gratuito
        ):
            continue

        if necesita_rango:
            rangos = datos["rangos"]
            if not rangos:
                continue
            rangos_validos = [
                rango
                for rango in rangos
                if rango_cumple_filtro(
                    rango["precio_min"],
                    rango["precio_max"],
                    rango.get("etiqueta_precio"),
                    etiqueta,
                    precio_numero,
                    operador,
                )
            ]
            if not rangos_validos:
                continue
            mejor = _seleccionar_mejor_rango(rangos_validos, operador)
            if mejor.get("etiqueta_precio") in etiquetas_excluidas:
                continue
        elif es_gratuito is None:
            continue

        ids_coincidentes.append(id_sitio)

    return sorted(ids_coincidentes)
