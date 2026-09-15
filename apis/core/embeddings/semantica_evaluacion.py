from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.busqueda_texto import score_keyword_en_texto
from core.infra.catalogo_trgm import normalizar_excluir, normalizar_texto, sin_acentos
from core.infra.filtro_sitios import normalizar_ids_consulta

UMBRAL_ALTO = 0.75
UMBRAL_MEDIO = 0.60
TRGM_KEYWORD_FUERTE = 0.95
TRGM_KEYWORD_DEBIL_MIN = 0.95
BOOST_TITULO = 0.15
BOOST_DESCRIPCION = 0.10
BOOST_CHUNK_EXACTO = 0.25
BOOST_CHUNK_FUERTE = 0.20
BOOST_CHUNK_DEBIL = 0.10
BOOST_DEBIL = 0.05
MAX_CANDIDATOS_DEBUG = 25
MAX_CANDIDATOS_SQL = 1000

_SQL_ASCII = (
    "translate(lower({campo}), "
    "'áéíóúüñàèìòùâêîôûãõç', "
    "'aeiouunaeiouaeiouaoc')"
)


@dataclass
class CandidatoSemanticoEvaluado:
    id_sitio: int
    nombre: str
    score_semantico: float
    score_final: float
    boost_keywords: float
    keywords_match: list[str] = field(default_factory=list)
    supera_umbral: bool = False
    motivo: str = "descartado"
    id_chunk: str | None = None
    contenido_chunk: str | None = None


def _sql_ascii(campo: str) -> str:
    return _SQL_ASCII.format(campo=campo)


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


def _construir_filtro_exclusion(
    terminos: list[str],
) -> tuple[str, dict[str, str]]:
    if not terminos:
        return "", {}

    condiciones: list[str] = []
    params: dict[str, str] = {}
    for indice, termino in enumerate(terminos):
        clave = f"excluir_{indice}"
        params[clave] = f"%{termino}%"
        condiciones.append(
            f"""(
                {_sql_ascii("s.nombre")} LIKE :{clave}
                OR {_sql_ascii("COALESCE(s.descripcion_corta, '')")} LIKE :{clave}
                OR {_sql_ascii("c.contenido")} LIKE :{clave}
            )"""
        )
    return f"NOT ({' OR '.join(condiciones)})", params


def _obtener_mejor_chunk_por_sitio(
    db: Session,
    *,
    embedding: str,
    ids_consulta: list[int],
    excluir_terminos: list[str],
) -> list[dict[str, Any]]:
    ids_validos = normalizar_ids_consulta(ids_consulta)
    filtros = [
        "cf.origen = 'sitio'",
        "s.activo = TRUE",
    ]
    params: dict[str, Any] = {"embedding": embedding}

    if ids_validos:
        filtros.append("s.id_sitio = ANY(:ids_consulta)")
        params["ids_consulta"] = ids_validos

    filtro_exclusion, params_exclusion = _construir_filtro_exclusion(excluir_terminos)
    if filtro_exclusion:
        filtros.append(filtro_exclusion)
        params.update(params_exclusion)

    query = f"""
        SELECT
            id_sitio,
            nombre,
            descripcion_corta,
            id_chunk,
            contenido_chunk,
            score_semantico
        FROM (
            SELECT DISTINCT ON (s.id_sitio)
                s.id_sitio,
                s.nombre,
                s.descripcion_corta,
                c.id_chunk::text AS id_chunk,
                c.contenido AS contenido_chunk,
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS score_semantico
            FROM turismo.chunk c
            JOIN turismo.chunk_fuente cf ON cf.id_fuente = c.id_fuente
            JOIN turismo.sitio s ON s.id_sitio = cf.id_vinculo
            WHERE {' AND '.join(filtros)}
            ORDER BY s.id_sitio, c.embedding <=> CAST(:embedding AS vector) ASC
        ) mejor_por_sitio
        ORDER BY score_semantico DESC
        LIMIT :limite
    """
    params["limite"] = MAX_CANDIDATOS_SQL

    return list(db.execute(text(query), params).mappings().all())


def _keyword_en_titulo(nombre: str, keyword: str) -> bool:
    nombre_norm = sin_acentos(normalizar_texto(nombre))
    keyword_norm = sin_acentos(normalizar_texto(keyword))
    return keyword_norm in nombre_norm if keyword_norm else False




def _boost_por_keyword(
    *,
    nombre: str,
    descripcion_corta: str | None,
    contenido_chunk: str | None,
    keyword: str,
) -> float:
    keyword_norm = sin_acentos(normalizar_texto(keyword))
    if _keyword_en_titulo(nombre, keyword):
        return BOOST_TITULO

    score_nombre = score_keyword_en_texto(nombre, keyword)
    if score_nombre >= TRGM_KEYWORD_FUERTE:
        return BOOST_TITULO

    score_desc = score_keyword_en_texto(descripcion_corta, keyword)
    boost_desc = 0.0
    if score_desc >= TRGM_KEYWORD_FUERTE:
        boost_desc = BOOST_DESCRIPCION
    elif TRGM_KEYWORD_DEBIL_MIN <= score_desc < TRGM_KEYWORD_FUERTE:
        boost_desc = BOOST_DEBIL

    chunk_norm = sin_acentos(normalizar_texto(str(contenido_chunk or "")))
    if keyword_norm and keyword_norm in chunk_norm:
        return max(boost_desc, BOOST_CHUNK_EXACTO)


    score_chunk = score_keyword_en_texto(contenido_chunk, keyword)
    if score_chunk >= TRGM_KEYWORD_FUERTE:
        return max(boost_desc, BOOST_CHUNK_FUERTE)
    if TRGM_KEYWORD_DEBIL_MIN <= score_chunk < TRGM_KEYWORD_FUERTE:
        return max(boost_desc, BOOST_CHUNK_DEBIL)
    return boost_desc


def _calcular_boosts(
    *,
    nombre: str,
    descripcion_corta: str | None,
    contenido_chunk: str | None,
    keywords: list[str],
) -> tuple[float, list[str]]:
    if not keywords:
        return 0.0, []

    boost_total = 0.0
    coincidencias: list[str] = []
    for keyword in keywords:
        boost = _boost_por_keyword(
            nombre=nombre,
            descripcion_corta=descripcion_corta,
            contenido_chunk=contenido_chunk,
            keyword=keyword,
        )
        if boost > 0:
            boost_total += boost
            coincidencias.append(keyword)
    return boost_total, coincidencias


def _evaluar_candidato(
    *,
    score_semantico: float,
    boost_keywords: float,
    keywords_match: list[str] | None = None,
) -> tuple[bool, str, float]:
    score_final = score_semantico
    if keywords_match and boost_keywords > 0:
        return True, "keyword", score_final

    if score_semantico >= UMBRAL_ALTO:
        return True, "alto", score_final
    return False, "descartado", score_final


def buscar_sitios_por_semantica(
    db: Session,
    *,
    embedding: str,
    keywords: list[str],
    ids_consulta: list[int],
    excluir_terminos: list[str],
) -> tuple[list[int], list[CandidatoSemanticoEvaluado]]:
    keywords_norm = _normalizar_keywords(keywords)
    excluir_norm = normalizar_excluir(excluir_terminos)

    filas = _obtener_mejor_chunk_por_sitio(
        db,
        embedding=embedding,
        ids_consulta=ids_consulta,
        excluir_terminos=excluir_norm,
    )

    candidatos: list[CandidatoSemanticoEvaluado] = []
    for fila in filas:
        score_semantico = float(fila["score_semantico"])
        boost_keywords, keywords_match = _calcular_boosts(
            nombre=str(fila["nombre"] or ""),
            descripcion_corta=fila.get("descripcion_corta"),
            contenido_chunk=fila.get("contenido_chunk"),
            keywords=keywords_norm,
        )
        supera_umbral, motivo, score_final = _evaluar_candidato(
            score_semantico=score_semantico,
            boost_keywords=boost_keywords,
            keywords_match=keywords_match,
        )
        candidatos.append(
            CandidatoSemanticoEvaluado(
                id_sitio=int(fila["id_sitio"]),
                nombre=str(fila["nombre"] or ""),
                score_semantico=round(score_semantico, 4),
                score_final=round(score_final, 4),
                boost_keywords=round(boost_keywords, 4),
                keywords_match=keywords_match,
                supera_umbral=supera_umbral,
                motivo=motivo,
                id_chunk=fila.get("id_chunk"),
                contenido_chunk=fila.get("contenido_chunk"),
            )
        )

    candidatos.sort(key=lambda item: item.score_final, reverse=True)
    debug = candidatos[:MAX_CANDIDATOS_DEBUG]
    ids_sitio = [item.id_sitio for item in candidatos if item.supera_umbral]
    return ids_sitio, debug
