from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.busqueda_texto import (
    UMBRAL_FINAL_REFERENCIA,
    UMBRAL_TRGM_REFERENCIA,
    TOP_CANDIDATOS_REFERENCIA,
    PALABRAS_PRIORIZA_DIRECCION,
    contar_palabras,
    mejor_score_direccion,
    quitar_prefijos_via,
    score_comparacion,
)
from core.infra.catalogo_trgm import normalizar_texto, params_texto_busqueda, sql_score_trgm
from core.infra.filtro_sitios import intersectar_ids, normalizar_ids_consulta
from esquemas.chatboot_exploracion.busqueda_referencia import (
    BusquedaReferenciaEntrada,
    BusquedaReferenciaExito,
    BusquedaReferenciaFallo,
    BusquedaReferenciaSinSitios,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda

FuenteReferencia = Literal["direccion", "parroquia", "plataforma", "ninguna"]


def _candidatos_direccion(
    db: Session,
    params: dict[str, str],
    ids_consulta: list[int] | None = None,
) -> list[dict[str, Any]]:
    score_direccion = sql_score_trgm("d.direccion_texto")
    score_referencia = sql_score_trgm("COALESCE(d.referencia_adicional, '')")
    filtro_ids = ""
    query_params: dict[str, Any] = {
        **params,
        "umbral_trgm": UMBRAL_TRGM_REFERENCIA,
        "limite": TOP_CANDIDATOS_REFERENCIA,
    }
    if ids_consulta:
        filtro_ids = " AND s.id_sitio = ANY(:ids_consulta)"
        query_params["ids_consulta"] = ids_consulta
    rows = db.execute(
        text(
            f"""
            SELECT
                s.id_sitio,
                d.direccion_texto,
                d.referencia_adicional,
                GREATEST({score_direccion}, {score_referencia}) AS score_trgm
            FROM turismo.direccion d
            JOIN turismo.sitio s ON s.id_sitio = d.id_sitio
            WHERE s.activo = TRUE
              {filtro_ids}
              AND (
                {score_direccion} > :umbral_trgm
                OR {score_referencia} > :umbral_trgm
              )
            ORDER BY score_trgm DESC
            LIMIT :limite
            """
        ),
        query_params,
    ).mappings().all()
    return [dict(row) for row in rows]


def _candidatos_parroquia(
    db: Session,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    score_nombre = sql_score_trgm("nombre")
    rows = db.execute(
        text(
            f"""
            SELECT
                id_parroquia,
                nombre,
                {score_nombre} AS score_trgm
            FROM turismo.parroquia
            WHERE activo = TRUE
              AND {score_nombre} > :umbral_trgm
            ORDER BY score_trgm DESC
            LIMIT :limite
            """
        ),
        {
            **params,
            "umbral_trgm": UMBRAL_TRGM_REFERENCIA,
            "limite": TOP_CANDIDATOS_REFERENCIA,
        },
    ).mappings().all()
    return [dict(row) for row in rows]


def _candidatos_plataforma(
    db: Session,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    score_nombre = sql_score_trgm("pl.nombre")
    rows = db.execute(
        text(
            f"""
            SELECT
                pl.id_plataforma,
                pl.nombre,
                {score_nombre} AS score_trgm
            FROM turismo.plataforma pl
            JOIN turismo.parroquia p ON p.id_parroquia = pl.id_parroquia
            WHERE pl.activo = TRUE
              AND p.activo = TRUE
              AND {score_nombre} > :umbral_trgm
            ORDER BY score_trgm DESC
            LIMIT :limite
            """
        ),
        {
            **params,
            "umbral_trgm": UMBRAL_TRGM_REFERENCIA,
            "limite": TOP_CANDIDATOS_REFERENCIA,
        },
    ).mappings().all()
    return [dict(row) for row in rows]


def _filtrar_direccion(
    candidatos: list[dict[str, Any]],
    texto_limpio: str,
) -> list[dict[str, Any]]:
    validos: list[dict[str, Any]] = []
    for candidato in candidatos:
        score = mejor_score_direccion(
            texto_limpio,
            candidato.get("direccion_texto") or "",
            candidato.get("referencia_adicional"),
        )
        if score >= UMBRAL_FINAL_REFERENCIA:
            item = dict(candidato)
            item["score_final"] = score
            validos.append(item)
    validos.sort(key=lambda item: item["score_final"], reverse=True)
    return validos


def _mejor_nombre(
    candidatos: list[dict[str, Any]],
    texto_limpio: str,
) -> dict[str, Any] | None:
    mejor: dict[str, Any] | None = None
    mejor_score = 0.0
    for candidato in candidatos:
        score = score_comparacion(texto_limpio, candidato.get("nombre") or "")
        if score >= UMBRAL_FINAL_REFERENCIA and score > mejor_score:
            mejor = dict(candidato)
            mejor["score_final"] = score
            mejor_score = score
    return mejor


def _max_score(candidatos: list[dict[str, Any]]) -> float:
    if not candidatos:
        return 0.0
    return max(float(item["score_final"]) for item in candidatos)


def _resolver_fuente(
    score_direccion: float,
    score_parroquia: float,
    score_plataforma: float,
    palabras: int,
) -> FuenteReferencia:
    scores = {
        "direccion": score_direccion,
        "parroquia": score_parroquia,
        "plataforma": score_plataforma,
    }
    max_score = max(scores.values())
    if max_score <= 0:
        return "ninguna"

    ganadores = [fuente for fuente, score in scores.items() if score == max_score]
    if len(ganadores) == 1:
        return ganadores[0]  # type: ignore[return-value]

    if palabras > PALABRAS_PRIORIZA_DIRECCION:
        if "direccion" in ganadores:
            return "direccion"
        return "plataforma" if score_plataforma >= score_parroquia else "parroquia"

    if "parroquia" in ganadores and "plataforma" in ganadores:
        return "plataforma" if score_plataforma >= score_parroquia else "parroquia"
    if "parroquia" in ganadores:
        return "parroquia"
    if "plataforma" in ganadores:
        return "plataforma"
    return "direccion"


def _ids_por_parroquia(
    db: Session,
    id_parroquia: int,
    ids_consulta: list[int] | None = None,
) -> list[int]:
    filtro_ids = ""
    params: dict[str, Any] = {"id_parroquia": id_parroquia}
    if ids_consulta:
        filtro_ids = " AND id_sitio = ANY(:ids_consulta)"
        params["ids_consulta"] = ids_consulta
    rows = db.execute(
        text(
            f"""
            SELECT id_sitio
            FROM turismo.sitio
            WHERE activo = TRUE
              AND id_parroquia = :id_parroquia
              {filtro_ids}
            ORDER BY id_sitio
            """
        ),
        params,
    ).scalars().all()
    return [int(item) for item in rows]


def _ids_por_plataforma(
    db: Session,
    id_plataforma: int,
    ids_consulta: list[int] | None = None,
) -> list[int]:
    filtro_ids = ""
    params: dict[str, Any] = {"id_plataforma": id_plataforma}
    if ids_consulta:
        filtro_ids = " AND id_sitio = ANY(:ids_consulta)"
        params["ids_consulta"] = ids_consulta
    rows = db.execute(
        text(
            f"""
            SELECT id_sitio
            FROM turismo.sitio
            WHERE activo = TRUE
              AND id_plataforma = :id_plataforma
              {filtro_ids}
            ORDER BY id_sitio
            """
        ),
        params,
    ).scalars().all()
    return [int(item) for item in rows]


def buscar_sitios_por_referencia(
    db: Session,
    payload: BusquedaReferenciaEntrada,
) -> BusquedaReferenciaExito | BusquedaReferenciaSinSitios | BusquedaReferenciaFallo:
    valor_estado = payload.model_dump(mode="json")
    texto = normalizar_texto(payload.direccion_referencia)
    if not texto:
        mensaje = "La dirección o referencia consultada no puede estar vacía."
        return BusquedaReferenciaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="busqueda_referencia",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    texto_limpio = quitar_prefijos_via(texto) or texto
    palabras = contar_palabras(texto_limpio)
    params = params_texto_busqueda(texto, texto_limpio)
    ids_consulta = normalizar_ids_consulta(payload.ids_consulta)
    ids_filtro = ids_consulta or None

    direccion_validos = _filtrar_direccion(
        _candidatos_direccion(db, params, ids_filtro),
        texto_limpio,
    )
    parroquia_mejor = _mejor_nombre(_candidatos_parroquia(db, params), texto_limpio)
    plataforma_mejor = _mejor_nombre(_candidatos_plataforma(db, params), texto_limpio)

    score_direccion = _max_score(direccion_validos)
    score_parroquia = (
        float(parroquia_mejor["score_final"]) if parroquia_mejor else 0.0
    )
    score_plataforma = (
        float(plataforma_mejor["score_final"]) if plataforma_mejor else 0.0
    )

    fuente = _resolver_fuente(
        score_direccion,
        score_parroquia,
        score_plataforma,
        palabras,
    )

    if fuente == "ninguna":
        mensaje = "Ningún sitio cumple con la dirección o referencia indicada."
        return BusquedaReferenciaSinSitios(
            sin_sitios=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="busqueda_referencia",
                estado="no_cumplido",
                valor={**valor_estado, "fuente_resuelta": fuente},
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    ids_sitio: list[int] = []
    if fuente == "direccion":
        ids_sitio = [int(item["id_sitio"]) for item in direccion_validos]
    elif fuente == "parroquia" and parroquia_mejor:
        ids_sitio = _ids_por_parroquia(
            db, int(parroquia_mejor["id_parroquia"]), ids_filtro
        )
    elif fuente == "plataforma" and plataforma_mejor:
        ids_sitio = _ids_por_plataforma(
            db, int(plataforma_mejor["id_plataforma"]), ids_filtro
        )

    ids_sitio = intersectar_ids(ids_sitio, payload.ids_consulta)

    if not ids_sitio:
        mensaje = "Ningún sitio cumple con la dirección o referencia indicada."
        return BusquedaReferenciaSinSitios(
            sin_sitios=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="busqueda_referencia",
                estado="no_cumplido",
                valor={**valor_estado, "fuente_resuelta": fuente},
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    ids_ordenados = sorted(set(ids_sitio))
    return BusquedaReferenciaExito(
        ids_sitio=ids_ordenados,
        estado_busqueda=construir_estado_busqueda(
            nombre="busqueda_referencia",
            estado="cumplido",
            valor={**valor_estado, "fuente_resuelta": fuente},
            ids_entrada=payload.ids_consulta,
            ids_salida=ids_ordenados,
            detalle=f"Se filtraron sitios por referencia de {fuente}.",
        ),
    )
