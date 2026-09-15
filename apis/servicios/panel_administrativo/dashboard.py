import hashlib
import json
import pickle
import unicodedata
from datetime import date
from time import monotonic
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.redis_cliente import ejecutar_redis
from esquemas.panel_administrativo.dashboard import (
    AgruparPor,
    CanalChatbot,
    CompararPor,
    DashboardConsultasResponse,
    DashboardDistribucionResponse,
    DashboardMetricResponse,
    DashboardRankingResponse,
    DashboardResumenResponse,
    DashboardSemanticaResponse,
    DashboardSeriesResponse,
    Dimension,
    Estado,
    Metric,
    OrdenConsultas,
    Periodo,
    RankingTipo,
    TipoChatbot,
)

try:
    import numpy as np
except ImportError:  # pragma: no cover - solo para entornos sin dependencias instaladas.
    np = None

_SEMANTICA_CACHE_TTL_SECONDS = 60
_SEMANTICA_CACHE_MAX_ITEMS = 32
_SEMANTICA_CACHE: dict[tuple[Any, ...], tuple[float, DashboardSemanticaResponse]] = {}
_SEMANTICA_REDIS_PREFIX = "dashboard:semantica:v1:"

DATE_COLUMNS = {
    "usuarios": "u.actualizado_en",
    "preguntas": "creado_en",
    "favoritos": "creado_en",
    "noticias": "fecha_inicio",
}

GROUP_UNITS = {
    "hour": "hour",
    "day": "day",
    "week": "week",
    "month": "month",
    "year": "year",
}

LABEL_FORMATS = {
    "hour": "HH24:00",
    "day": "YYYY-MM-DD",
    "week": "IYYY-\"W\"IW",
    "month": "YYYY-MM",
    "year": "YYYY",
}


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _date_filter(
    column: str,
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    prefix: str = "",
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}

    if periodo == "all":
        return "", params

    if periodo == "custom":
        if not fecha_inicio or not fecha_fin:
            raise _bad_request("fecha_inicio y fecha_fin son obligatorias para periodo=custom")
        return (
            f" AND {column} >= :{prefix}fecha_inicio AND {column} < (CAST(:{prefix}fecha_fin AS date) + INTERVAL '1 day')",
            {f"{prefix}fecha_inicio": fecha_inicio, f"{prefix}fecha_fin": fecha_fin},
        )

    if periodo == "today":
        unit = "day"
    elif periodo == "week":
        unit = "week"
    elif periodo == "month":
        unit = "month"
    elif periodo == "year":
        unit = "year"
    else:
        raise _bad_request("Periodo no valido")

    return (
        f" AND {column} >= date_trunc('{unit}', NOW())",
        params,
    )


def _previous_date_filter(
    column: str,
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
) -> tuple[str, dict[str, Any]]:
    if periodo in ("all", "custom"):
        return "", {}

    unit = {"today": "day", "week": "week", "month": "month", "year": "year"}[periodo]
    return (
        f"""
        AND {column} >= date_trunc('{unit}', NOW()) - INTERVAL '1 {unit}'
        AND {column} < date_trunc('{unit}', NOW())
        """,
        {},
    )


def _variation(current: int, previous: int) -> float:
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round(((current - previous) / previous) * 100, 1)


def _fetch_count(db: Session, sql: str, params: dict[str, Any]) -> int:
    return int(db.execute(text(sql), params).scalar() or 0)


def _preguntas_source_sql() -> str:
    return """
        SELECT
            id_mensaje_ex AS id_mensaje,
            contenido,
            'general' AS tipo_chatbot,
            'exploracion' AS canal,
            NULLIF(array_to_string(categoria, ', '), '') AS categoria,
            NULLIF(array_to_string(subcategoria, ', '), '') AS subcategoria,
            NULL::INT AS id_sitio,
            NULL::TEXT AS sitio,
            creado_en
        FROM conversacion.mensaje_explorador
        WHERE rol = 'usuario'
        UNION ALL
        SELECT
            md.id_mensaje_pd AS id_mensaje,
            md.contenido,
            'sitio' AS tipo_chatbot,
            'pregunta_directa' AS canal,
            NULL::TEXT AS categoria,
            NULL::TEXT AS subcategoria,
            s.id_sitio::INT AS id_sitio,
            s.nombre AS sitio,
            md.creado_en
        FROM conversacion.mensaje_detalle md
        LEFT JOIN turismo.sitio s ON lower(s.nombre) = lower(md.entidad_asociada)
        WHERE md.rol = 'usuario'
    """


def _parse_embedding(value: str | None) -> list[float] | None:
    if not value:
        return None
    clean = value.strip().strip("[]")
    if not clean:
        return None
    return [float(item) for item in clean.split(",")]


def _normalize_embedding(embedding: list[float]) -> list[float]:
    norm = sum(value * value for value in embedding) ** 0.5
    if norm == 0:
        return []
    return [value / norm for value in embedding]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _agrupar_mensajes_semanticos(
    mensajes: list[dict[str, Any]],
    umbral: float,
) -> list[dict[str, Any]]:
    if not mensajes:
        return []

    if np is not None:
        matriz = np.array([mensaje["embedding"] for mensaje in mensajes], dtype=np.float32)
        normas = np.linalg.norm(matriz, axis=1)
        validos = normas > 0
        matriz[validos] = matriz[validos] / normas[validos, None]
        representantes = np.empty_like(matriz)
        total_representantes = 0
        grupos: list[dict[str, Any]] = []

        for indice, mensaje in enumerate(mensajes):
            vector = matriz[indice]
            if not validos[indice]:
                continue
            if total_representantes:
                sims = representantes[:total_representantes] @ vector
                mejor_indice = int(np.argmax(sims))
                mejor_similitud = float(sims[mejor_indice])
            else:
                mejor_indice = -1
                mejor_similitud = 0.0

            if mejor_indice >= 0 and mejor_similitud >= umbral:
                grupos[mejor_indice]["consultas"].append(mensaje)
                grupos[mejor_indice]["similitudes"].append(mejor_similitud)
            else:
                representantes[total_representantes] = vector
                total_representantes += 1
                grupos.append({"consultas": [mensaje], "similitudes": [1.0]})

        return grupos

    grupos: list[dict[str, Any]] = []
    for mensaje in mensajes:
        embedding = _normalize_embedding(mensaje["embedding"])
        if not embedding:
            continue
        mejor_grupo: dict[str, Any] | None = None
        mejor_similitud = 0.0
        for grupo in grupos:
            similitud = _cosine_similarity(embedding, grupo["embedding_representativo"])
            if similitud >= umbral and similitud > mejor_similitud:
                mejor_grupo = grupo
                mejor_similitud = similitud

        if mejor_grupo is None:
            grupos.append(
                {
                    "embedding_representativo": embedding,
                    "consultas": [mensaje],
                    "similitudes": [1.0],
                }
            )
        else:
            mejor_grupo["consultas"].append(mensaje)
            mejor_grupo["similitudes"].append(mejor_similitud)
    return grupos


def _most_common(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in items:
        value = item.get(key)
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return {"label": None, "valor": 0}
    label, value = max(counts.items(), key=lambda entry: entry[1])
    return {"label": label, "valor": value}


def _normalizar_pregunta_semantica(value: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")
    return " ".join(texto.split())


def _valor_mixto_o_unico(items: list[dict[str, Any]], key: str) -> str:
    valores = {str(item.get(key) or "").strip() for item in items}
    valores.discard("")
    if len(valores) == 1:
        return valores.pop()
    return "mixto"


def _preguntas_relacionadas_semantica(
    consultas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    agrupadas: dict[str, dict[str, Any]] = {}
    orden: list[str] = []

    for item in consultas:
        key = _normalizar_pregunta_semantica(item.get("pregunta"))
        if not key:
            continue
        if key not in agrupadas:
            agrupadas[key] = {"consultas": []}
            orden.append(key)
        agrupadas[key]["consultas"].append(item)

    relacionadas: list[dict[str, Any]] = []
    for key in orden:
        items = sorted(
            agrupadas[key]["consultas"],
            key=lambda item: item["fecha"],
            reverse=True,
        )
        reciente = items[0]
        relacionadas.append(
            {
                "pregunta": reciente["pregunta"],
                "total_consultas": len(items),
                "categoria": _most_common(items, "categoria")["label"],
                "subcategoria": _most_common(items, "subcategoria")["label"],
                "entidad": _most_common(items, "entidad")["label"],
                "tipo_chatbot": _valor_mixto_o_unico(items, "tipo_chatbot"),
                "canal": _valor_mixto_o_unico(items, "canal"),
                "ultima_fecha": reciente["fecha"],
            }
        )

    relacionadas.sort(
        key=lambda item: (item["total_consultas"], item["ultima_fecha"]),
        reverse=True,
    )
    return relacionadas


def _preguntas_alcance_sql(
    sitios_permitidos: list[int] | None,
) -> tuple[str, dict[str, Any]]:
    if sitios_permitidos is None:
        return "", {}
    if not sitios_permitidos:
        return " AND 1=0", {}
    return (
        " AND tipo_chatbot = 'sitio' AND id_sitio = ANY(:sitios_permitidos)",
        {"sitios_permitidos": sitios_permitidos},
    )


def _semantica_alcance_sql(
    sitios_permitidos: list[int] | None,
) -> tuple[str, str, dict[str, Any]]:
    if sitios_permitidos is None:
        return "", "", {}
    if not sitios_permitidos:
        return " AND 1=0", " AND 1=0", {}
    return (
        " AND 1=0",
        " AND s.id_sitio = ANY(:sitios_permitidos)",
        {"sitios_permitidos": sitios_permitidos},
    )


def _semantica_vacia(periodo: Periodo) -> DashboardSemanticaResponse:
    vacio = {"label": None, "valor": 0}
    return DashboardSemanticaResponse(
        periodo=periodo,
        total_grupos=0,
        total_consultas_agrupadas=0,
        resumen={
            "consultas_totales": 0,
            "total_preguntas_usuario": 0,
            "total_mensajes_historial": 0,
            "preguntas_con_embedding": 0,
            "preguntas_sin_embedding": 0,
            "preguntas_analizadas": 0,
            "categoria_mas_frecuente": vacio,
            "entidad_mas_relacionada": vacio,
        },
        grupos=[],
    )


def _semantica_cache_key(cache_key: tuple[Any, ...]) -> str:
    payload = json.dumps(cache_key, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{_SEMANTICA_REDIS_PREFIX}{digest}"


def _leer_semantica_cache_local(
    cache_key: tuple[Any, ...],
) -> DashboardSemanticaResponse | None:
    cached = _SEMANTICA_CACHE.get(cache_key)
    now = monotonic()
    if cached and now - cached[0] <= _SEMANTICA_CACHE_TTL_SECONDS:
        return cached[1]
    if cached:
        _SEMANTICA_CACHE.pop(cache_key, None)
    return None


def _guardar_semantica_cache_local(
    cache_key: tuple[Any, ...],
    respuesta: DashboardSemanticaResponse,
) -> DashboardSemanticaResponse:
    if len(_SEMANTICA_CACHE) >= _SEMANTICA_CACHE_MAX_ITEMS:
        oldest_key = min(_SEMANTICA_CACHE, key=lambda key: _SEMANTICA_CACHE[key][0])
        _SEMANTICA_CACHE.pop(oldest_key, None)
    _SEMANTICA_CACHE[cache_key] = (monotonic(), respuesta)
    return respuesta


def _leer_semantica_cache(
    cache_key: tuple[Any, ...],
) -> DashboardSemanticaResponse | None:
    redis_key = _semantica_cache_key(cache_key)

    def _desde_redis(redis):
        payload = redis.get(redis_key)
        if not payload:
            return None
        try:
            respuesta = pickle.loads(bytes.fromhex(payload))
            if isinstance(respuesta, DashboardSemanticaResponse):
                return respuesta
            redis.delete(redis_key)
            return None
        except Exception:
            redis.delete(redis_key)
            return None

    return ejecutar_redis(
        _desde_redis,
        fallback=lambda: _leer_semantica_cache_local(cache_key),
    )


def _guardar_semantica_cache(
    cache_key: tuple[Any, ...],
    respuesta: DashboardSemanticaResponse,
) -> DashboardSemanticaResponse:
    redis_key = _semantica_cache_key(cache_key)

    def _en_redis(redis):
        payload = pickle.dumps(respuesta, protocol=pickle.HIGHEST_PROTOCOL).hex()
        redis.setex(redis_key, _SEMANTICA_CACHE_TTL_SECONDS, payload)
        return respuesta

    return ejecutar_redis(
        _en_redis,
        fallback=lambda: _guardar_semantica_cache_local(cache_key, respuesta),
    )


def _sitio_alcance_sql(
    sitios_permitidos: list[int] | None,
    column: str = "id_sitio",
) -> tuple[str, dict[str, Any]]:
    if sitios_permitidos is None:
        return "", {}
    if not sitios_permitidos:
        return " AND 1=0", {}
    return (
        f" AND {column} = ANY(:sitios_permitidos)",
        {"sitios_permitidos": sitios_permitidos},
    )


def _metric_sql(
    metric: Metric,
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    estado: Estado = "all",
    tipo_chatbot: TipoChatbot = "all",
    categoria: str | None = None,
    subcategoria: str | None = None,
    id_sitio: int | None = None,
    sitios_permitidos: list[int] | None = None,
) -> tuple[str, dict[str, Any]]:
    if sitios_permitidos is not None and metric in ("usuarios", "noticias", "rutas"):
        return "SELECT 0", {}

    if metric == "usuarios":
        return _metric_usuarios_sql(periodo, fecha_inicio, fecha_fin, estado)

    if metric == "atractivos":
        return _metric_atractivos_sql(estado, sitios_permitidos)

    if metric == "preguntas":
        return _metric_preguntas_sql(
            periodo,
            fecha_inicio,
            fecha_fin,
            tipo_chatbot,
            categoria,
            subcategoria,
            id_sitio,
            sitios_permitidos,
        )

    if metric == "favoritos":
        return _metric_favoritos_sql(
            periodo,
            fecha_inicio,
            fecha_fin,
            categoria,
            subcategoria,
            id_sitio,
            sitios_permitidos,
        )

    if metric == "noticias":
        return _metric_noticias_sql(periodo, fecha_inicio, fecha_fin, estado)

    if metric == "rutas":
        return _metric_rutas_sql(estado)

    raise _bad_request("Metrica no valida")


def _metric_usuarios_sql(
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    estado: Estado,
) -> tuple[str, dict[str, Any]]:
    filter_sql, params = _date_filter("u.actualizado_en", periodo, fecha_inicio, fecha_fin)
    estado_sql = ""
    if estado == "activo":
        estado_sql = " AND u.activo = TRUE"
    elif estado == "inactivo":
        estado_sql = " AND u.activo = FALSE"
    return (
        """
        SELECT COUNT(*)
        FROM conversacion.usuario u
        LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
        WHERE COALESCE(LOWER(c.nombre), 'usuario') = 'usuario'
        """
        f"{filter_sql}{estado_sql}"
    ), params


def _metric_atractivos_sql(
    estado: Estado,
    sitios_permitidos: list[int] | None,
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    where_parts: list[str] = []
    if estado == "activo":
        where_parts.append("activo = TRUE")
    elif estado == "inactivo":
        where_parts.append("activo = FALSE")
    elif estado in ("publicado", "borrador"):
        raise _bad_request("estado no aplica para atractivos")

    alcance_sql, alcance_params = _sitio_alcance_sql(sitios_permitidos)
    if alcance_sql == " AND 1=0":
        return "SELECT 0", {}
    if alcance_sql:
        where_parts.append("id_sitio = ANY(:sitios_permitidos)")
        params.update(alcance_params)

    where_sql = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
    return f"SELECT COUNT(*) FROM turismo.sitio{where_sql}", params


def _metric_preguntas_sql(
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    tipo_chatbot: TipoChatbot,
    categoria: str | None,
    subcategoria: str | None,
    id_sitio: int | None,
    sitios_permitidos: list[int] | None,
) -> tuple[str, dict[str, Any]]:
    filter_sql, params = _date_filter("creado_en", periodo, fecha_inicio, fecha_fin)
    extra = ""
    alcance_sql, alcance_params = _preguntas_alcance_sql(sitios_permitidos)
    if alcance_sql == " AND 1=0":
        return "SELECT 0", {}
    extra += alcance_sql
    params.update(alcance_params)
    if tipo_chatbot != "all":
        extra += " AND tipo_chatbot = :tipo_chatbot"
        params["tipo_chatbot"] = tipo_chatbot
    if categoria:
        extra += " AND categoria = :categoria"
        params["categoria"] = categoria
    if subcategoria:
        extra += " AND subcategoria = :subcategoria"
        params["subcategoria"] = subcategoria
    if id_sitio:
        extra += " AND id_sitio = :id_sitio"
        params["id_sitio"] = id_sitio
    return f"SELECT COUNT(*) FROM ({_preguntas_source_sql()}) p WHERE 1=1{filter_sql}{extra}", params


def _metric_favoritos_sql(
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    categoria: str | None,
    subcategoria: str | None,
    id_sitio: int | None,
    sitios_permitidos: list[int] | None,
) -> tuple[str, dict[str, Any]]:
    filter_sql, params = _date_filter("f.creado_en", periodo, fecha_inicio, fecha_fin)
    extra = ""
    alcance_sql, alcance_params = _sitio_alcance_sql(sitios_permitidos, "f.id_sitio")
    if alcance_sql == " AND 1=0":
        return "SELECT 0", {}
    extra += alcance_sql
    params.update(alcance_params)
    if id_sitio:
        extra += " AND f.id_sitio = :id_sitio"
        params["id_sitio"] = id_sitio
    if categoria or subcategoria:
        extra += " AND EXISTS (SELECT 1 FROM turismo.sitio s LEFT JOIN turismo.categoria c ON c.id_categoria = s.id_categoria LEFT JOIN turismo.subcategoria sc ON sc.id_subcategoria = s.id_subcategoria WHERE s.id_sitio = f.id_sitio"
        if categoria:
            extra += " AND c.nombre = :categoria"
            params["categoria"] = categoria
        if subcategoria:
            extra += " AND sc.nombre = :subcategoria"
            params["subcategoria"] = subcategoria
        extra += ")"
    return f"SELECT COUNT(*) FROM conversacion.favorito f WHERE 1=1{filter_sql}{extra}", params


def _metric_noticias_sql(
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    estado: Estado,
) -> tuple[str, dict[str, Any]]:
    filter_sql, params = _date_filter("fecha_inicio", periodo, fecha_inicio, fecha_fin)
    estado_sql = ""
    if estado in ("activo", "publicado"):
        estado_sql = " AND activa = TRUE"
    elif estado in ("inactivo", "borrador"):
        estado_sql = " AND activa = FALSE"
    return f"SELECT COUNT(*) FROM turismo.noticia WHERE 1=1{filter_sql}{estado_sql}", params


def _metric_rutas_sql(estado: Estado) -> tuple[str, dict[str, Any]]:
    estado_sql = ""
    if estado == "activo":
        estado_sql = " WHERE activo = TRUE"
    elif estado == "inactivo":
        estado_sql = " WHERE activo = FALSE"
    elif estado in ("publicado", "borrador"):
        raise _bad_request("estado no aplica para rutas")
    return f"SELECT COUNT(*) FROM gis.rutas_turistica{estado_sql}", {}


def obtener_metrica(
    db: Session,
    metric: Metric,
    periodo: Periodo = "all",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    estado: Estado = "all",
    tipo_chatbot: TipoChatbot = "all",
    categoria: str | None = None,
    subcategoria: str | None = None,
    id_sitio: int | None = None,
    sitios_permitidos: list[int] | None = None,
) -> DashboardMetricResponse:
    sql, params = _metric_sql(
        metric,
        periodo,
        fecha_inicio,
        fecha_fin,
        estado,
        tipo_chatbot,
        categoria,
        subcategoria,
        id_sitio,
        sitios_permitidos,
    )
    return DashboardMetricResponse(
        metric=metric,
        periodo=periodo,
        valor=_fetch_count(db, sql, params),
    )


def _count_with_variation(
    db: Session,
    metric: Metric,
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    estado: Estado = "all",
    sitios_permitidos: list[int] | None = None,
) -> dict[str, float | int]:
    sql, params = _metric_sql(
        metric, periodo, fecha_inicio, fecha_fin, estado=estado, sitios_permitidos=sitios_permitidos
    )
    current = _fetch_count(db, sql, params)

    if metric not in DATE_COLUMNS:
        return {"valor": current, "variacion": 0.0}

    prev_filter, prev_params = _previous_date_filter(
        DATE_COLUMNS[metric], periodo, fecha_inicio, fecha_fin
    )
    if not prev_filter:
        previous = 0
    else:
        previous_sql, previous_params = _metric_sql(
            metric, "all", None, None, estado=estado, sitios_permitidos=sitios_permitidos
        )
        merged_params = {**previous_params, **prev_params}
        previous = _fetch_count(
            db,
            previous_sql.replace("WHERE 1=1", f"WHERE 1=1 {prev_filter}"),
            merged_params,
        )

    return {"valor": current, "variacion": _variation(current, previous)}


def obtener_resumen(
    db: Session,
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    sitios_permitidos: list[int] | None = None,
) -> DashboardResumenResponse:
    return DashboardResumenResponse(
        usuarios_registrados=_count_with_variation(
            db, "usuarios", periodo, fecha_inicio, fecha_fin, sitios_permitidos=sitios_permitidos
        ),
        atractivos_activos=_count_with_variation(
            db, "atractivos", periodo, fecha_inicio, fecha_fin, estado="activo", sitios_permitidos=sitios_permitidos
        ),
        preguntas_chatbots=_count_with_variation(
            db, "preguntas", periodo, fecha_inicio, fecha_fin, sitios_permitidos=sitios_permitidos
        ),
        favoritos_guardados=_count_with_variation(
            db, "favoritos", periodo, fecha_inicio, fecha_fin, sitios_permitidos=sitios_permitidos
        ),
        noticias_activas=_count_with_variation(
            db, "noticias", periodo, fecha_inicio, fecha_fin, estado="activo", sitios_permitidos=sitios_permitidos
        ),
        rutas_activas=_count_with_variation(
            db, "rutas", periodo, fecha_inicio, fecha_fin, estado="activo", sitios_permitidos=sitios_permitidos
        ),
    )


def obtener_series(
    db: Session,
    metric: Metric,
    agrupar_por: AgruparPor,
    periodo: Periodo = "month",
    comparar_por: CompararPor = "none",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    tipo_chatbot: TipoChatbot = "all",
    categoria: str | None = None,
    subcategoria: str | None = None,
    id_sitio: int | None = None,
    sitios_permitidos: list[int] | None = None,
) -> DashboardSeriesResponse:
    if metric != "preguntas":
        raise _bad_request("Por ahora series soporta metric=preguntas")

    if comparar_por not in ("none", "tipo_chatbot", "categoria", "subcategoria"):
        raise _bad_request("comparar_por no soportado para preguntas")

    filter_sql, params = _date_filter("creado_en", periodo, fecha_inicio, fecha_fin)
    extra = ""
    alcance_sql, alcance_params = _preguntas_alcance_sql(sitios_permitidos)
    extra += alcance_sql
    params.update(alcance_params)
    if tipo_chatbot != "all":
        extra += " AND tipo_chatbot = :tipo_chatbot"
        params["tipo_chatbot"] = tipo_chatbot
    if categoria:
        extra += " AND categoria = :categoria"
        params["categoria"] = categoria
    if subcategoria:
        extra += " AND subcategoria = :subcategoria"
        params["subcategoria"] = subcategoria
    if id_sitio:
        extra += " AND id_sitio = :id_sitio"
        params["id_sitio"] = id_sitio

    compare_expr = {
        "none": "'total'",
        "tipo_chatbot": "tipo_chatbot",
        "categoria": "COALESCE(categoria, 'Sin categoria')",
        "subcategoria": "COALESCE(subcategoria, 'Sin subcategoria')",
    }[comparar_por]

    unit = GROUP_UNITS[agrupar_por]
    label_format = LABEL_FORMATS[agrupar_por]
    rows = db.execute(
        text(
            f"""
            SELECT
                date_trunc('{unit}', creado_en) AS bucket,
                to_char(date_trunc('{unit}', creado_en), '{label_format}') AS label,
                {compare_expr} AS serie_key,
                COUNT(*)::INT AS valor
            FROM ({_preguntas_source_sql()}) p
            WHERE 1=1{filter_sql}{extra}
            GROUP BY bucket, label, serie_key
            ORDER BY bucket ASC
            """
        ),
        params,
    ).mappings().all()

    series: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["serie_key"])
        name = {
            "general": "Chatbot general",
            "sitio": "Chatbot por sitio",
            "total": "Total",
        }.get(key, key)
        series.setdefault(key, {"name": name, "key": key, "data": []})
        series[key]["data"].append(
            {
                "label": row["label"],
                "fecha": row["bucket"].date().isoformat(),
                "valor": row["valor"],
            }
        )

    return DashboardSeriesResponse(
        metric=metric,
        periodo=periodo,
        agrupar_por=agrupar_por,
        comparar_por=comparar_por,
        series=list(series.values()),
    )


def obtener_distribucion(
    db: Session,
    metric: str,
    dimension: Dimension,
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    limit: int = 10,
    sitios_permitidos: list[int] | None = None,
) -> DashboardDistribucionResponse:
    if limit < 1 or limit > 100:
        raise _bad_request("limit debe estar entre 1 y 100")

    params: dict[str, Any] = {"limit": limit}

    if sitios_permitidos is not None and metric in ("noticias", "rutas"):
        return DashboardDistribucionResponse(
            metric=metric,
            dimension=dimension,
            periodo=periodo,
            items=[],
        )

    if metric == "usuarios" and dimension == "estado":
        rows = db.execute(
            text(
                """
                WITH usuarios_clasificados AS (
                    SELECT
                        CASE
                            WHEN LOWER(COALESCE(c.nombre, '')) IN ('super admin', 'super administrador') THEN 'Super admin'
                            WHEN LOWER(COALESCE(c.nombre, '')) IN ('dueno', 'dueño') THEN 'Dueño'
                            WHEN LOWER(COALESCE(c.nombre, '')) = 'admin' THEN 'Admin'
                            ELSE 'Usuario móvil'
                        END AS label,
                        CASE
                            WHEN LOWER(COALESCE(c.nombre, '')) IN ('super admin', 'super administrador') THEN 'super_admin'
                            WHEN LOWER(COALESCE(c.nombre, '')) IN ('dueno', 'dueño') THEN 'dueno'
                            WHEN LOWER(COALESCE(c.nombre, '')) = 'admin' THEN 'admin'
                            ELSE 'usuario_movil'
                        END AS key
                    FROM conversacion.usuario u
                    LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
                )
                SELECT label, key, COUNT(*)::INT AS valor
                FROM usuarios_clasificados
                GROUP BY label, key
                ORDER BY
                    CASE key
                        WHEN 'usuario_movil' THEN 1
                        WHEN 'dueno' THEN 2
                        WHEN 'admin' THEN 3
                        WHEN 'super_admin' THEN 4
                        ELSE 5
                    END
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    elif metric == "preguntas":
        filter_sql, date_params = _date_filter("creado_en", periodo, fecha_inicio, fecha_fin)
        params.update(date_params)
        alcance_sql, alcance_params = _preguntas_alcance_sql(sitios_permitidos)
        params.update(alcance_params)
        dimension_expr = {
            "tipo_chatbot": "tipo_chatbot",
            "categoria": "COALESCE(categoria, 'Sin categoria')",
            "subcategoria": "COALESCE(subcategoria, 'Sin subcategoria')",
            "sitio": "COALESCE(sitio, 'Sin sitio')",
            "estado": "'registrada'",
        }[dimension]
        rows = db.execute(
            text(
                f"""
                SELECT {dimension_expr} AS label, {dimension_expr} AS key, COUNT(*)::INT AS valor
                FROM ({_preguntas_source_sql()}) p
                WHERE 1=1{filter_sql}{alcance_sql}
                GROUP BY label, key
                ORDER BY valor DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    elif metric == "atractivos" and dimension == "estado":
        alcance_sql, alcance_params = _sitio_alcance_sql(sitios_permitidos)
        params.update(alcance_params)
        if alcance_sql == " AND 1=0":
            rows = []
        else:
            rows = db.execute(
                text(
                    f"""
                    SELECT CASE WHEN activo THEN 'Activo' ELSE 'Inactivo' END AS label,
                           CASE WHEN activo THEN 'activo' ELSE 'inactivo' END AS key,
                           COUNT(*)::INT AS valor
                    FROM turismo.sitio
                    WHERE 1=1{alcance_sql}
                    GROUP BY activo
                    ORDER BY valor DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).mappings().all()
    elif metric == "noticias" and dimension == "estado":
        rows = db.execute(
            text(
                """
                SELECT CASE WHEN activa THEN 'Activa' ELSE 'Inactiva' END AS label,
                       CASE WHEN activa THEN 'activo' ELSE 'inactivo' END AS key,
                       COUNT(*)::INT AS valor
                FROM turismo.noticia
                GROUP BY activa
                ORDER BY valor DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    elif metric == "rutas" and dimension == "estado":
        rows = db.execute(
            text(
                """
                SELECT CASE WHEN activo THEN 'Activa' ELSE 'Inactiva' END AS label,
                       CASE WHEN activo THEN 'activo' ELSE 'inactivo' END AS key,
                       COUNT(*)::INT AS valor
                FROM gis.rutas_turistica
                GROUP BY activo
                ORDER BY valor DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    elif metric == "favoritos" and dimension in ("sitio", "categoria", "subcategoria"):
        filter_sql, date_params = _date_filter("f.creado_en", periodo, fecha_inicio, fecha_fin)
        params.update(date_params)
        alcance_sql, alcance_params = _sitio_alcance_sql(sitios_permitidos, "f.id_sitio")
        params.update(alcance_params)
        if alcance_sql == " AND 1=0":
            rows = []
        else:
            dimension_expr = {
                "sitio": "s.nombre",
                "categoria": "c.nombre",
                "subcategoria": "COALESCE(sc.nombre, 'Sin subcategoria')",
            }[dimension]
            rows = db.execute(
                text(
                    f"""
                    SELECT {dimension_expr} AS label, {dimension_expr} AS key, COUNT(*)::INT AS valor
                    FROM conversacion.favorito f
                    JOIN turismo.sitio s ON s.id_sitio = f.id_sitio
                    JOIN turismo.categoria c ON c.id_categoria = s.id_categoria
                    LEFT JOIN turismo.subcategoria sc ON sc.id_subcategoria = s.id_subcategoria
                    WHERE 1=1{filter_sql}{alcance_sql}
                    GROUP BY label, key
                    ORDER BY valor DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).mappings().all()
    else:
        raise _bad_request("Combinacion metric/dimension no soportada")

    return DashboardDistribucionResponse(
        metric=metric,
        dimension=dimension,
        periodo=periodo,
        items=[dict(row) for row in rows],
    )


def obtener_ranking(
    db: Session,
    tipo: RankingTipo,
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    limit: int = 5,
    categoria: str | None = None,
    subcategoria: str | None = None,
    tipo_chatbot: TipoChatbot = "all",
    sitios_permitidos: list[int] | None = None,
) -> DashboardRankingResponse:
    if limit < 1 or limit > 100:
        raise _bad_request("limit debe estar entre 1 y 100")

    params: dict[str, Any] = {"limit": limit}

    if sitios_permitidos is not None and tipo == "rutas_consultadas":
        rows = []
    elif tipo in ("categorias_buscadas", "subcategorias_buscadas", "sitios_consultados"):
        filter_sql, date_params = _date_filter("creado_en", periodo, fecha_inicio, fecha_fin)
        params.update(date_params)
        extra = ""
        alcance_sql, alcance_params = _preguntas_alcance_sql(sitios_permitidos)
        extra += alcance_sql
        params.update(alcance_params)
        if tipo_chatbot != "all":
            extra += " AND tipo_chatbot = :tipo_chatbot"
            params["tipo_chatbot"] = tipo_chatbot
        if categoria:
            extra += " AND categoria = :categoria"
            params["categoria"] = categoria
        if subcategoria:
            extra += " AND subcategoria = :subcategoria"
            params["subcategoria"] = subcategoria

        target = {
            "categorias_buscadas": ("NULL::INT", "categoria"),
            "subcategorias_buscadas": ("NULL::INT", "subcategoria"),
            "sitios_consultados": ("id_sitio", "sitio"),
        }[tipo]
        rows = db.execute(
            text(
                f"""
                SELECT {target[0]} AS id, {target[1]} AS nombre, COUNT(*)::INT AS valor
                FROM ({_preguntas_source_sql()}) p
                WHERE {target[1]} IS NOT NULL{filter_sql}{extra}
                GROUP BY id, nombre
                ORDER BY valor DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    elif tipo == "sitios_favoritos":
        filter_sql, date_params = _date_filter("f.creado_en", periodo, fecha_inicio, fecha_fin)
        params.update(date_params)
        alcance_sql, alcance_params = _sitio_alcance_sql(sitios_permitidos, "f.id_sitio")
        params.update(alcance_params)
        if alcance_sql == " AND 1=0":
            rows = []
        else:
            rows = db.execute(
                text(
                    f"""
                    SELECT s.id_sitio::INT AS id, s.nombre, COUNT(*)::INT AS valor
                    FROM conversacion.favorito f
                    JOIN turismo.sitio s ON s.id_sitio = f.id_sitio
                    WHERE 1=1{filter_sql}{alcance_sql}
                    GROUP BY s.id_sitio, s.nombre
                    ORDER BY valor DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).mappings().all()
    elif tipo == "rutas_consultadas":
        rows = db.execute(
            text(
                """
                SELECT id_ruta::INT AS id, titulo AS nombre, 0::INT AS valor
                FROM gis.rutas_turistica
                WHERE activo = TRUE
                ORDER BY titulo ASC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    else:
        raise _bad_request("Tipo de ranking no valido")

    return DashboardRankingResponse(
        tipo=tipo,
        periodo=periodo,
        limit=limit,
        items=[
            {"posicion": index + 1, "id": row["id"], "nombre": row["nombre"], "valor": row["valor"]}
            for index, row in enumerate(rows)
        ],
    )


def obtener_consultas(
    db: Session,
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    tipo_chatbot: TipoChatbot = "all",
    categoria: str | None = None,
    subcategoria: str | None = None,
    id_sitio: int | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    orden: OrdenConsultas = "fecha_desc",
    sitios_permitidos: list[int] | None = None,
) -> DashboardConsultasResponse:
    if page < 1:
        raise _bad_request("page debe ser mayor o igual a 1")
    if page_size < 1 or page_size > 100:
        raise _bad_request("page_size debe estar entre 1 y 100")

    filter_sql, params = _date_filter("creado_en", periodo, fecha_inicio, fecha_fin)
    extra = ""
    if tipo_chatbot != "all":
        extra += " AND tipo_chatbot = :tipo_chatbot"
        params["tipo_chatbot"] = tipo_chatbot
    if categoria:
        extra += " AND categoria = :categoria"
        params["categoria"] = categoria
    if subcategoria:
        extra += " AND subcategoria = :subcategoria"
        params["subcategoria"] = subcategoria
    if id_sitio:
        extra += " AND id_sitio = :id_sitio"
        params["id_sitio"] = id_sitio
    if q:
        extra += " AND contenido ILIKE :q"
        params["q"] = f"%{q}%"

    alcance_sql, alcance_params = _preguntas_alcance_sql(sitios_permitidos)
    extra += alcance_sql
    params.update(alcance_params)

    base_sql = f"FROM ({_preguntas_source_sql()}) p WHERE 1=1{filter_sql}{extra}"
    total = _fetch_count(db, f"SELECT COUNT(*) {base_sql}", params)

    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    order_sql = "ASC" if orden == "fecha_asc" else "DESC"
    rows = db.execute(
        text(
            f"""
            SELECT id_mensaje, contenido AS pregunta, tipo_chatbot, categoria,
                   subcategoria, id_sitio, sitio, creado_en AS fecha
            {base_sql}
            ORDER BY creado_en {order_sql}
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    return DashboardConsultasResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[dict(row) for row in rows],
    )


def _validar_parametros_semantica(
    *,
    limit: int,
    umbral: float,
    max_consultas_analisis: int,
    min_total_consultas: int,
) -> None:
    if limit < 1 or limit > 200:
        raise _bad_request("limit debe estar entre 1 y 200")
    if umbral < 0 or umbral > 1:
        raise _bad_request("umbral debe estar entre 0 y 1")
    if max_consultas_analisis < 1 or max_consultas_analisis > 50000:
        raise _bad_request("max_consultas_analisis debe estar entre 1 y 50000")
    if min_total_consultas < 1 or min_total_consultas > 50000:
        raise _bad_request("min_total_consultas debe estar entre 1 y 50000")


def _cache_key_semantica(
    *,
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    categoria: str | None,
    subcategoria: str | None,
    limit: int,
    umbral: float,
    canal: CanalChatbot,
    max_consultas_analisis: int,
    min_total_consultas: int,
    sitios_permitidos: list[int] | None,
) -> tuple[Any, ...]:
    # La cache depende del umbral, alcance y mínimo de consultas; si falta uno,
    # el panel puede mostrar grupos calculados con otro estándar visual.
    return (
        periodo,
        fecha_inicio.isoformat() if fecha_inicio else None,
        fecha_fin.isoformat() if fecha_fin else None,
        categoria,
        subcategoria,
        limit,
        round(umbral, 4),
        canal,
        max_consultas_analisis,
        min_total_consultas,
        tuple(sitios_permitidos) if sitios_permitidos is not None else None,
    )


def _filtros_semantica(
    *,
    periodo: Periodo,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    categoria: str | None,
    subcategoria: str | None,
    canal: CanalChatbot,
    max_consultas_analisis: int,
    sitios_permitidos: list[int] | None,
) -> tuple[str, str, str, str, dict[str, Any]]:
    # Exploración y pregunta directa viven en tablas distintas. Los filtros se
    # calculan por separado para no mezclar categorías de exploración con sitios.
    filter_ex, params_ex = _date_filter("creado_en", periodo, fecha_inicio, fecha_fin, "ex_")
    filter_dt, params_dt = _date_filter("md.creado_en", periodo, fecha_inicio, fecha_fin, "dt_")
    params: dict[str, Any] = {**params_ex, **params_dt, "max_consultas": max_consultas_analisis}

    extra_ex = ""
    extra_dt = ""
    if categoria:
        extra_ex += " AND :categoria = ANY(categoria)"
        extra_dt += " AND 1=0"
        params["categoria"] = categoria
    if subcategoria:
        extra_ex += " AND :subcategoria = ANY(subcategoria)"
        extra_dt += " AND 1=0"
        params["subcategoria"] = subcategoria
    if canal == "exploracion":
        extra_dt += " AND 1=0"
    elif canal == "pregunta_directa":
        extra_ex += " AND 1=0"

    alcance_ex, alcance_dt, alcance_params = _semantica_alcance_sql(sitios_permitidos)
    extra_ex += alcance_ex
    extra_dt += alcance_dt
    params.update(alcance_params)
    return filter_ex, filter_dt, extra_ex, extra_dt, params


def _consulta_publica_semantica(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_mensaje": item["id_mensaje"],
        "pregunta": item["pregunta"],
        "categoria": item.get("categoria"),
        "subcategoria": item.get("subcategoria"),
        "entidad": item.get("entidad"),
        "tipo_chatbot": item["tipo_chatbot"],
        "canal": item["canal"],
        "fecha": item["fecha"],
    }


def _construir_grupo_semantica_response(
    index: int,
    grupo: dict[str, Any],
) -> dict[str, Any]:
    consultas = sorted(grupo["consultas"], key=lambda item: item["fecha"], reverse=True)
    preguntas_relacionadas = _preguntas_relacionadas_semantica(consultas)
    representative = (
        preguntas_relacionadas[0]["pregunta"]
        if preguntas_relacionadas
        else consultas[0]["pregunta"]
    )
    tipos = {item["tipo_chatbot"] for item in consultas}
    tipo_chatbot = tipos.pop() if len(tipos) == 1 else "mixto"
    canales = {item["canal"] for item in consultas}
    canal_grupo = canales.pop() if len(canales) == 1 else "mixto"

    return {
        "id_grupo": index,
        "consulta_representativa": representative,
        "total_consultas": len(consultas),
        "categoria": _most_common(consultas, "categoria")["label"],
        "subcategoria": _most_common(consultas, "subcategoria")["label"],
        "entidad": _most_common(consultas, "entidad")["label"],
        "tipo_chatbot": tipo_chatbot,
        "canal": canal_grupo,
        "similitud_promedio": round(
            sum(grupo["similitudes"]) / len(grupo["similitudes"]),
            3,
        ),
        "ultima_fecha": consultas[0]["fecha"],
        "preguntas_relacionadas": preguntas_relacionadas,
        "consultas": [_consulta_publica_semantica(item) for item in consultas],
    }


def obtener_semantica(
    db: Session,
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    categoria: str | None = None,
    subcategoria: str | None = None,
    limit: int = 50,
    umbral: float = 0.82,
    canal: CanalChatbot = "all",
    max_consultas_analisis: int = 10000,
    min_total_consultas: int = 20,
    sitios_permitidos: list[int] | None = None,
) -> DashboardSemanticaResponse:
    _validar_parametros_semantica(
        limit=limit,
        umbral=umbral,
        max_consultas_analisis=max_consultas_analisis,
        min_total_consultas=min_total_consultas,
    )
    if sitios_permitidos is not None and not sitios_permitidos:
        return _semantica_vacia(periodo)

    cache_key = _cache_key_semantica(
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        categoria=categoria,
        subcategoria=subcategoria,
        limit=limit,
        umbral=umbral,
        canal=canal,
        max_consultas_analisis=max_consultas_analisis,
        min_total_consultas=min_total_consultas,
        sitios_permitidos=sitios_permitidos,
    )
    cached = _leer_semantica_cache(cache_key)
    if cached is not None:
        return cached

    filter_ex, filter_dt, extra_ex, extra_dt, params = _filtros_semantica(
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        categoria=categoria,
        subcategoria=subcategoria,
        canal=canal,
        max_consultas_analisis=max_consultas_analisis,
        sitios_permitidos=sitios_permitidos,
    )

    resumen_row = db.execute(
        text(
            f"""
            SELECT
                COALESCE(SUM(total_preguntas_usuario), 0)::INT AS total_preguntas_usuario,
                COALESCE(SUM(total_mensajes_historial), 0)::INT AS total_mensajes_historial,
                COALESCE(SUM(preguntas_con_embedding), 0)::INT AS preguntas_con_embedding
            FROM (
                SELECT
                    COUNT(*) FILTER (WHERE rol = 'usuario')::INT AS total_preguntas_usuario,
                    COUNT(*)::INT AS total_mensajes_historial,
                    COUNT(*) FILTER (WHERE rol = 'usuario' AND embedding IS NOT NULL)::INT AS preguntas_con_embedding
                FROM conversacion.mensaje_explorador
                WHERE 1=1
                  {filter_ex}
                  {extra_ex}
                  {"AND 1=0" if canal == "pregunta_directa" else ""}
                UNION ALL
                SELECT
                    COUNT(*) FILTER (WHERE md.rol = 'usuario')::INT AS total_preguntas_usuario,
                    COUNT(*)::INT AS total_mensajes_historial,
                    COUNT(*) FILTER (WHERE md.rol = 'usuario' AND md.embedding IS NOT NULL)::INT AS preguntas_con_embedding
                FROM conversacion.mensaje_detalle md
                LEFT JOIN turismo.sitio s ON lower(s.nombre) = lower(md.entidad_asociada)
                WHERE 1=1
                  {filter_dt}
                  {extra_dt}
            ) conteos
            """
        ),
        params,
    ).mappings().one()

    rows = db.execute(
        text(
            f"""
            SELECT *
            FROM (
                SELECT
                    id_mensaje_ex::INT AS id_mensaje,
                    contenido AS pregunta,
                    NULLIF(array_to_string(categoria, ', '), '') AS categoria,
                    NULLIF(array_to_string(subcategoria, ', '), '') AS subcategoria,
                    NULL::TEXT AS entidad,
                    'general' AS tipo_chatbot,
                    'exploracion' AS canal,
                    creado_en AS fecha,
                    embedding::TEXT AS embedding
                FROM conversacion.mensaje_explorador
                WHERE rol = 'usuario'
                  AND embedding IS NOT NULL
                  {filter_ex}
                  {extra_ex}
                UNION ALL
                SELECT
                    md.id_mensaje_pd::INT AS id_mensaje,
                    md.contenido AS pregunta,
                    NULL::VARCHAR AS categoria,
                    NULL::VARCHAR AS subcategoria,
                    md.entidad_asociada AS entidad,
                    'sitio' AS tipo_chatbot,
                    'pregunta_directa' AS canal,
                    md.creado_en AS fecha,
                    md.embedding::TEXT AS embedding
                FROM conversacion.mensaje_detalle md
                LEFT JOIN turismo.sitio s ON lower(s.nombre) = lower(md.entidad_asociada)
                WHERE md.rol = 'usuario'
                  AND md.embedding IS NOT NULL
                  {filter_dt}
                  {extra_dt}
            ) mensajes
            ORDER BY fecha DESC
            LIMIT :max_consultas
            """
        ),
        params,
    ).mappings().all()

    mensajes: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        embedding = _parse_embedding(item.pop("embedding", None))
        if embedding:
            item["embedding"] = embedding
            mensajes.append(item)

    grupos = [
        grupo
        for grupo in _agrupar_mensajes_semanticos(mensajes, umbral)
        if len(grupo["consultas"]) >= min_total_consultas
    ]

    grupos.sort(key=lambda grupo: len(grupo["consultas"]), reverse=True)
    grupos = grupos[:limit]

    response_groups = [
        _construir_grupo_semantica_response(index, grupo)
        for index, grupo in enumerate(grupos, start=1)
    ]

    grouped_messages = [
        consulta
        for grupo in response_groups
        for consulta in grupo["consultas"]
    ]

    total_preguntas = int(resumen_row["total_preguntas_usuario"] or 0)
    preguntas_con_embedding = int(resumen_row["preguntas_con_embedding"] or 0)
    respuesta = DashboardSemanticaResponse(
        periodo=periodo,
        total_grupos=len(response_groups),
        total_consultas_agrupadas=len(grouped_messages),
        resumen={
            "consultas_totales": len(grouped_messages),
            "total_preguntas_usuario": total_preguntas,
            "total_mensajes_historial": int(resumen_row["total_mensajes_historial"] or 0),
            "preguntas_con_embedding": preguntas_con_embedding,
            "preguntas_sin_embedding": max(total_preguntas - preguntas_con_embedding, 0),
            "preguntas_analizadas": len(mensajes),
            "categoria_mas_frecuente": _most_common(grouped_messages, "categoria"),
            "entidad_mas_relacionada": _most_common(grouped_messages, "entidad"),
        },
        grupos=response_groups,
    )

    return _guardar_semantica_cache(cache_key, respuesta)
