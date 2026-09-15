from sqlalchemy import text
from sqlalchemy.orm import Session

from esquemas.chatboot_exploracion.fallback_opciones import (
    OpcionFallbackExploracion,
    OpcionesFallbackExploracionSalida,
)

MAX_CATEGORIAS_FALLBACK = 8
MAX_SUBCATEGORIAS_FALLBACK = 6


def listar_opciones_fallback_exploracion(
    db: Session,
) -> OpcionesFallbackExploracionSalida:
    rows = db.execute(
        text(
            """
            SELECT
                c.nombre AS categoria,
                sc.nombre AS subcategoria
            FROM turismo.categoria c
            JOIN turismo.subcategoria sc
              ON sc.id_categoria = c.id_categoria
             AND sc.activo = TRUE
            WHERE c.activo = TRUE
            ORDER BY c.nombre ASC, sc.nombre ASC
            """
        )
    ).mappings().all()

    agrupadas: dict[str, list[str]] = {}
    for row in rows:
        categoria = str(row["categoria"] or "").strip()
        subcategoria = str(row["subcategoria"] or "").strip()
        if not categoria or not subcategoria:
            continue
        agrupadas.setdefault(categoria, [])
        if (
            subcategoria not in agrupadas[categoria]
            and len(agrupadas[categoria]) < MAX_SUBCATEGORIAS_FALLBACK
        ):
            agrupadas[categoria].append(subcategoria)

    opciones = [
        OpcionFallbackExploracion(
            categoria=categoria,
            subcategorias=subcategorias,
        )
        for categoria, subcategorias in list(agrupadas.items())[:MAX_CATEGORIAS_FALLBACK]
        if subcategorias
    ]
    return OpcionesFallbackExploracionSalida(opciones=opciones)
