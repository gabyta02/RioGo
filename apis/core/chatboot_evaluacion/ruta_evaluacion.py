from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.filtro_sitios import normalizar_ids_consulta

TIPOS_RUTA_ALIAS: dict[str, tuple[str, ...]] = {
    "senderismo": ("senderismo", "senderos", "trekking", "hiking"),
    "ciclismo": ("ciclismo", "cicloturismo", "bici", "bicicleta", "ciclismo de montaña"),
    "caminata_urbana": (
        "caminata urbana",
        "caminata_urbana",
        "ruta urbana",
        "city walk",
        "paseo urbano",
    ),
    "montanismo": ("montanismo", "montaña", "alpinismo", "escalada"),
    "otro": ("otro", "otros", "otras", "otra"),
}

TIPOS_RUTA_BD: dict[str, str] = {
    "senderismo": "Senderismo",
    "ciclismo": "Ciclismo",
    "caminata_urbana": "Caminata Urbana",
    "montanismo": "Montañismo",
    "otro": "Otras",
}


def _normalizar_termino(texto: str) -> str:
    return " ".join(str(texto or "").strip().lower().split())


def resolver_tipo_ruta(texto: str) -> str | None:
    termino = _normalizar_termino(texto)
    for clave, alias in TIPOS_RUTA_ALIAS.items():
        if termino in {_normalizar_termino(item) for item in alias}:
            return clave
    return None


def resolver_tipos_ruta_excluidos(excluir: list[str]) -> list[str]:
    tipos_bd: list[str] = []
    for termino in excluir:
        clave = resolver_tipo_ruta(termino)
        if not clave:
            continue
        tipo_bd = TIPOS_RUTA_BD[clave]
        if tipo_bd not in tipos_bd:
            tipos_bd.append(tipo_bd)
    return tipos_bd


def filtrar_rutas_por_tipo(
    db: Session,
    *,
    tipo_ruta: str,
    excluir_tipos: list[str],
    ids_consulta: list[int],
) -> tuple[list[int], str | None, str | None]:
    tipo_consultado = _normalizar_termino(tipo_ruta)
    tipo_clave = resolver_tipo_ruta(tipo_consultado)
    if not tipo_clave:
        return [], tipo_consultado, None

    tipo_bd = TIPOS_RUTA_BD[tipo_clave]
    tipos_excluidos = resolver_tipos_ruta_excluidos(excluir_tipos)
    if tipo_bd in tipos_excluidos:
        return [], tipo_consultado, tipo_bd

    ids_candidatos = normalizar_ids_consulta(ids_consulta)
    filtros_sql = ["activo = TRUE", "tipo_ruta::text = :tipo_ruta"]
    params: dict[str, Any] = {"tipo_ruta": tipo_bd}

    if ids_candidatos:
        filtros_sql.append("id_ruta = ANY(:ids_rutas)")
        params["ids_rutas"] = ids_candidatos

    if tipos_excluidos:
        filtros_sql.append("tipo_ruta::text <> ALL(:tipos_excluidos)")
        params["tipos_excluidos"] = tipos_excluidos

    rows = db.execute(
        text(
            f"""
            SELECT id_ruta
            FROM gis.rutas_turistica
            WHERE {' AND '.join(filtros_sql)}
            ORDER BY titulo ASC
            """
        ),
        params,
    ).scalars().all()

    return [int(id_ruta) for id_ruta in rows], tipo_consultado, tipo_bd
