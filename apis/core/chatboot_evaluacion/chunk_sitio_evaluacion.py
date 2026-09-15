from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.busqueda_texto import score_keyword_en_texto
from core.infra.catalogo_trgm import normalizar_texto

UMBRAL_MINIMO = 0.60
BOOST_KEYWORD = 0.20
TRGM_KEYWORD_FUERTE = 0.85
MAX_CHUNKS_SQL = 50
MAX_CHUNKS_SALIDA = 3


@dataclass
class ChunkSitioEvaluado:
    id_chunk: str
    contenido: str
    score_semantico: float
    score_final: float
    keywords_match: list[str] = field(default_factory=list)
    supera_umbral: bool = False


def _normalizar_keywords(keywords: list[str]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []
    for item in keywords:
        texto = str(item or "").strip()
        if not texto:
            continue
        clave = normalizar_texto(texto)
        if clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(texto)
    return resultado


def _calcular_boost_chunk(
    *,
    contenido: str,
    keywords: list[str],
) -> tuple[float, list[str]]:
    if not keywords:
        return 0.0, []

    boost_total = 0.0
    coincidencias: list[str] = []
    for keyword in keywords:
        score = score_keyword_en_texto(contenido, keyword)
        if score >= TRGM_KEYWORD_FUERTE:
            boost_total += BOOST_KEYWORD
            coincidencias.append(keyword)
    return boost_total, coincidencias


def _obtener_chunks_por_embedding(
    db: Session,
    *,
    id_sitio: int,
    embedding: str,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            c.id_chunk::text AS id_chunk,
            c.contenido AS contenido,
            1 - (c.embedding <=> CAST(:embedding AS vector)) AS score_semantico
        FROM turismo.chunk c
        JOIN turismo.chunk_fuente cf ON cf.id_fuente = c.id_fuente
        JOIN turismo.sitio s ON s.id_sitio = cf.id_vinculo
        WHERE cf.origen = 'sitio'
          AND cf.id_vinculo = :id_sitio
          AND s.activo = TRUE
        ORDER BY score_semantico DESC
        LIMIT :limite
    """
    return list(
        db.execute(
            text(query),
            {
                "embedding": embedding,
                "id_sitio": id_sitio,
                "limite": MAX_CHUNKS_SQL,
            },
        ).mappings().all()
    )


def _fusionar_scores_semanticos(
    acumulado: dict[str, dict[str, Any]],
    filas: list[dict[str, Any]],
) -> None:
    for fila in filas:
        if fila is None:
            continue
        id_chunk = str(fila["id_chunk"])
        score = float(fila["score_semantico"])
        if id_chunk not in acumulado or score > float(acumulado[id_chunk]["score_semantico"]):
            acumulado[id_chunk] = {
                "id_chunk": id_chunk,
                "contenido": str(fila["contenido"] or ""),
                "score_semantico": score,
            }


def buscar_chunks_en_sitio(
    db: Session,
    *,
    id_sitio: int,
    embeddings: list[str],
    keywords: list[str],
) -> list[ChunkSitioEvaluado]:
    keywords_norm = _normalizar_keywords(keywords)
    acumulado: dict[str, dict[str, Any]] = {}

    for embedding in embeddings:
        filas = _obtener_chunks_por_embedding(
            db,
            id_sitio=id_sitio,
            embedding=embedding,
        )
        _fusionar_scores_semanticos(acumulado, filas)

    candidatos: list[ChunkSitioEvaluado] = []
    for item in acumulado.values():
        score_semantico = float(item["score_semantico"])
        boost_keywords, keywords_match = _calcular_boost_chunk(
            contenido=str(item["contenido"]),
            keywords=keywords_norm,
        )
        score_final = min(1.0, score_semantico + boost_keywords)
        candidatos.append(
            ChunkSitioEvaluado(
                id_chunk=str(item["id_chunk"]),
                contenido=str(item["contenido"]),
                score_semantico=round(score_semantico, 4),
                score_final=round(score_final, 4),
                keywords_match=keywords_match,
                supera_umbral=score_final >= UMBRAL_MINIMO,
            )
        )

    candidatos.sort(key=lambda item: item.score_final, reverse=True)
    return candidatos
