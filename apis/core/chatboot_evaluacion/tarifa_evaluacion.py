from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.busqueda_texto import score_trigram_local
from core.infra.filtro_sitios import agregar_filtro_ids
from core.chatboot_evaluacion.precio_evaluacion import (
    OperadorPrecioInterno,
    normalizar_etiqueta,
)

UMBRAL_CONDICION = 0.40

CONDICIONES_ALIAS: dict[str, tuple[str, ...]] = {
    "general": (
        "general",
        "publico",
        "público",
        "todo publico",
        "todo público",
        "todo el publico",
        "todo el público",
        "todos",
        "todos los publicos",
        "todos los públicos",
    ),
    "adulto": ("adulto", "adultos"),
    "nino": ("nino", "niño", "ninos", "niños", "infantil"),
    "joven": ("joven", "jovenes", "jóvenes"),
    "estudiante": ("estudiante", "estudiantes"),
    "tercera_edad": ("tercera_edad", "tercera edad", "adulto mayor", "adultos mayores"),
    "discapacidad": ("discapacidad", "discapacitado", "capacidades especiales"),
}


def _normalizar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.strip().lower())


def _sin_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(caracter for caracter in normalizado if not unicodedata.combining(caracter))


def _a_float(valor: Any) -> float:
    if isinstance(valor, Decimal):
        return float(valor)
    return float(valor)


def clasificar_etiqueta_por_monto(precio: float) -> str:
    if precio <= 1:
        return "economico"
    if precio <= 5:
        return "medio"
    return "alto"


def normalizar_condicion(texto: str) -> str | None:
    termino = _sin_acentos(_normalizar_texto(texto))
    if not termino:
        return None
    if termino in CONDICIONES_ALIAS:
        return termino
    for clave, alias in CONDICIONES_ALIAS.items():
        if termino in {_sin_acentos(_normalizar_texto(item)) for item in alias}:
            return clave
    return termino


def condicion_coincide(
    condicion: str,
    texto_busqueda: str,
) -> bool:
    if not condicion or not texto_busqueda:
        return False
    condicion_ascii = normalizar_condicion(condicion) or _sin_acentos(
        _normalizar_texto(condicion)
    )
    busqueda_ascii = normalizar_condicion(texto_busqueda) or _sin_acentos(
        _normalizar_texto(texto_busqueda)
    )
    if condicion_ascii == busqueda_ascii:
        return True
    if busqueda_ascii in condicion_ascii:
        return True
    return score_trigram_local(condicion, texto_busqueda) >= UMBRAL_CONDICION


def monto_cumple_filtro(
    precio: float,
    etiqueta: str | None,
    precio_numero: float | None,
    operador: OperadorPrecioInterno | None,
) -> bool:
    if etiqueta and clasificar_etiqueta_por_monto(precio) != etiqueta:
        return False
    if precio_numero is None:
        return etiqueta is not None
    if operador == "exacto":
        return abs(precio - precio_numero) < 0.01
    if operador == "min":
        return precio <= precio_numero
    if operador == "max":
        return precio >= precio_numero
    if operador == "lt":
        return precio < precio_numero
    if operador == "gt":
        return precio > precio_numero
    return False


def obtener_datos_tarifa_sitios(
    db: Session,
    ids_consulta: list[int],
) -> dict[int, list[dict[str, Any]]]:
    filtros_sql = ["s.activo = TRUE", "s.es_gratuito IS FALSE"]
    params: dict[str, Any] = {}
    agregar_filtro_ids(filtros_sql, params, ids_consulta)

    sitios_rows = db.execute(
        text(
            f"""
            SELECT s.id_sitio
            FROM turismo.sitio s
            WHERE {' AND '.join(filtros_sql)}
            ORDER BY s.id_sitio ASC
            """
        ),
        params,
    ).scalars().all()

    ids_sitios = [int(item) for item in sitios_rows]
    if not ids_sitios:
        return {}

    tarifas_rows = db.execute(
        text(
            """
            SELECT id_sitio, precio, condicion
            FROM turismo.tarifa_acceso
            WHERE activo = TRUE
              AND id_sitio = ANY(:ids_sitios)
            ORDER BY id_sitio ASC, precio ASC, id_tarifa_acceso ASC
            """
        ),
        {"ids_sitios": ids_sitios},
    ).mappings().all()

    sitios: dict[int, list[dict[str, Any]]] = {id_sitio: [] for id_sitio in ids_sitios}
    for row in tarifas_rows:
        id_sitio = int(row["id_sitio"])
        sitios[id_sitio].append(
            {
                "precio": _a_float(row["precio"]),
                "condicion": row["condicion"],
            }
        )
    return sitios


def sitio_excluido_por_condiciones(
    tarifas: list[dict[str, Any]],
    condiciones_excluidas: list[str],
) -> bool:
    if not condiciones_excluidas or not tarifas:
        return False
    for tarifa in tarifas:
        condicion = tarifa.get("condicion") or ""
        for termino in condiciones_excluidas:
            if condicion_coincide(condicion, termino):
                return True
    return False


def sitio_cumple_entrada_gratuita(
    tarifas: list[dict[str, Any]],
    entrada_gratuita: bool,
) -> bool:
    tiene_gratis = any(tarifa["precio"] == 0 for tarifa in tarifas)
    if entrada_gratuita:
        return tiene_gratis
    return not tiene_gratis


def _seleccionar_mejor_tarifa(
    tarifas: list[dict[str, Any]],
    operador: OperadorPrecioInterno | None,
) -> dict[str, Any]:
    if operador in {"max", "gt"}:
        return max(tarifas, key=lambda item: item["precio"])
    return min(tarifas, key=lambda item: item["precio"])


def filtrar_sitios_por_tarifa(
    db: Session,
    tarifas_por_sitio: dict[int, list[dict[str, Any]]],
    entrada_gratuita: bool | None,
    etiqueta: str | None,
    precio_numero: float | None,
    operador: OperadorPrecioInterno | None,
    condicion: str | None,
    condiciones_excluidas: list[str],
) -> list[int]:
    ids_coincidentes: list[int] = []
    necesita_tarifa = (
        entrada_gratuita is not None
        or etiqueta is not None
        or precio_numero is not None
        or condicion is not None
    )

    for id_sitio, tarifas in tarifas_por_sitio.items():
        if not tarifas:
            if necesita_tarifa:
                continue
            ids_coincidentes.append(id_sitio)
            continue

        if sitio_excluido_por_condiciones(tarifas, condiciones_excluidas):
            continue

        if entrada_gratuita is not None and not sitio_cumple_entrada_gratuita(
            tarifas, entrada_gratuita
        ):
            continue

        if etiqueta or precio_numero is not None or condicion:
            tarifas_validas = tarifas
            if condicion:
                tarifas_validas = [
                    tarifa
                    for tarifa in tarifas_validas
                    if condicion_coincide(
                        tarifa.get("condicion") or "", condicion
                    )
                ]
                if not tarifas_validas:
                    continue

            tarifas_validas = [
                tarifa
                for tarifa in tarifas_validas
                if monto_cumple_filtro(
                    tarifa["precio"],
                    etiqueta,
                    precio_numero,
                    operador,
                )
            ]
            if not tarifas_validas:
                continue
            _seleccionar_mejor_tarifa(tarifas_validas, operador)
        elif entrada_gratuita is None:
            continue

        ids_coincidentes.append(id_sitio)

    return sorted(ids_coincidentes)
