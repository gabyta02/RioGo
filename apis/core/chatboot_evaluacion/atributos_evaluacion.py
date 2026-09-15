from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.filtro_sitios import agregar_filtro_ids

CAMPOS_BOOLEANOS: dict[str, tuple[str, ...]] = {
    "tiene_wifi": ("tiene_wifi", "wifi", "wi-fi", "wi fi"),
    "permite_mascotas": ("permite_mascotas", "mascotas", "mascota"),
    "accesibilidad": ("accesibilidad", "accesible"),
    "parqueadero": ("parqueadero", "estacionamiento", "parking"),
    "es_gratuito": ("es_gratuito", "gratuito", "gratis", "gratuita"),
}


def _normalizar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.strip().lower())


def _sin_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(caracter for caracter in normalizado if not unicodedata.combining(caracter))


def _resolver_campo_por_termino(termino: str) -> str | None:
    termino_norm = _sin_acentos(_normalizar_texto(termino))
    for campo, alias in CAMPOS_BOOLEANOS.items():
        if termino_norm in {_sin_acentos(_normalizar_texto(item)) for item in alias}:
            return campo
    return None


def campos_excluidos(excluir: list[str]) -> set[str]:
    campos: set[str] = set()
    for termino in excluir:
        campo = _resolver_campo_por_termino(termino)
        if campo:
            campos.add(campo)
    return campos


def filtrar_sitios_por_atributos(
    db: Session,
    ids_consulta: list[int],
    tiene_wifi: bool | None,
    permite_mascotas: bool | None,
    accesibilidad: bool | None,
    parqueadero: bool | None,
    es_gratuito: bool | None,
    excluir: list[str],
) -> list[int]:
    filtros_sql = ["s.activo = TRUE"]
    params: dict[str, Any] = {}
    agregar_filtro_ids(filtros_sql, params, ids_consulta)

    filtros_aplicados = {
        "tiene_wifi": tiene_wifi,
        "permite_mascotas": permite_mascotas,
        "accesibilidad": accesibilidad,
        "parqueadero": parqueadero,
        "es_gratuito": es_gratuito,
    }
    excluidos = campos_excluidos(excluir)

    for campo, valor in filtros_aplicados.items():
        if valor is not None:
            filtros_sql.append(f"s.{campo} = :{campo}")
            params[campo] = valor
        elif campo in excluidos:
            filtros_sql.append(f"(s.{campo} IS NULL OR s.{campo} = FALSE)")

    rows = db.execute(
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
    return [int(item) for item in rows]
