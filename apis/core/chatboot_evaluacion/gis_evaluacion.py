from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata
from typing import Literal

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.busqueda_texto import score_trigram_local
from core.infra.catalogo_trgm import (
    UMBRAL_CATALOGO,
    normalizar_texto,
    params_texto_busqueda,
    sql_score_trgm,
)
from core.infra.filtro_sitios import normalizar_ids_consulta

RADIO_BUSQUEDA_DEFECTO_M = 500.0
RADIOS_GIS_PROGRESIVOS_M = (500.0, 1000.0, 1500.0)
RADIO_GIS_MAX_M = 1500.0
UMBRAL_EXCLUSION_ZONA = 0.55

ModoBusquedaGis = Literal["progresivo", "fijo"]


@dataclass
class CandidatoGisEvaluado:
    id_entidad: int
    nombre: str
    distancia_metros: float


@dataclass
class ResultadoGisEvaluacion:
    ids: list[int] = field(default_factory=list)
    candidatos: list[CandidatoGisEvaluado] = field(default_factory=list)
    radio_aplicado_metros: float | None = None
    radios_intentados_metros: list[float] = field(default_factory=list)
    modo_busqueda: ModoBusquedaGis = "progresivo"


def formatear_distancia_aproximada(distancia_metros: float) -> str:
    metros = max(0.0, float(distancia_metros))
    if metros < 1000:
        return f"{int(round(metros))} m"
    km = metros / 1000.0
    if km < 10:
        texto = f"{km:.1f}".rstrip("0").rstrip(".")
        return f"{texto} km"
    return f"{int(round(km))} km"


def _sin_tildes(texto: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", texto)
        if unicodedata.category(char) != "Mn"
    )


def _consultar_nominatim(
    consulta: str,
) -> tuple[float, float, str] | tuple[None, None, None]:
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": consulta,
                "format": "json",
                "limit": 1,
            },
            headers={"User-Agent": "RiobambaGo-Chatbot/1.0"},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                nombre = data[0].get("display_name", consulta)
                return lat, lon, nombre
    except Exception:
        pass
    return None, None, None


def _variantes_nominatim(punto_referencia: str) -> list[str]:
    referencia = str(punto_referencia or "").strip()
    if not referencia:
        return []

    variantes = [
        f"{referencia}, Riobamba, Ecuador",
        f"{_sin_tildes(referencia)}, Riobamba, Ecuador",
    ]
    if not re.search(r"\briobamba\b", referencia, flags=re.IGNORECASE):
        variantes.append(f"{referencia}, Chimborazo, Ecuador")
    return list(dict.fromkeys(variantes))


def _partes_interseccion(punto_referencia: str) -> tuple[str, str] | None:
    partes = [
        parte.strip(" ,.;")
        for parte in re.split(r"\s+(?:y|&)\s+", punto_referencia, maxsplit=1, flags=re.IGNORECASE)
    ]
    if len(partes) != 2 or not partes[0] or not partes[1]:
        return None
    return partes[0], partes[1]


def _coordenadas_interseccion_aproximada(
    punto_referencia: str,
) -> tuple[float, float, str] | tuple[None, None, None]:
    partes = _partes_interseccion(punto_referencia)
    if partes is None:
        return None, None, None

    coordenadas: list[tuple[float, float, str]] = []
    for parte in partes:
        lat, lon, nombre = obtener_coordenadas_nominatim(parte)
        if lat is None or lon is None:
            return None, None, None
        coordenadas.append((lat, lon, nombre or parte))

    lat = sum(item[0] for item in coordenadas) / len(coordenadas)
    lon = sum(item[1] for item in coordenadas) / len(coordenadas)
    nombre = " / ".join(item[2] for item in coordenadas)
    return lat, lon, nombre


def obtener_coordenadas_nominatim(
    punto_referencia: str,
) -> tuple[float, float, str] | tuple[None, None, None]:
    lat, lon, nombre = _coordenadas_interseccion_aproximada(punto_referencia)
    if lat is not None and lon is not None:
        return lat, lon, nombre

    for consulta in _variantes_nominatim(punto_referencia):
        lat, lon, nombre = _consultar_nominatim(consulta)
        if lat is not None and lon is not None:
            return lat, lon, nombre

    return None, None, None


def _referencia_catalogo_equivalente(
    punto_referencia: str,
    nombre_catalogo: str,
) -> bool:
    referencia = normalizar_texto(punto_referencia)
    nombre = normalizar_texto(nombre_catalogo)
    if not referencia or not nombre:
        return False
    return referencia == nombre or referencia in nombre or nombre in referencia


def resolver_punto_origen(
    db: Session,
    usar_ubicacion_usuario: bool | None,
    ubicacion_usuario: dict[str, float] | None,
    punto_referencia: str | None,
) -> tuple[float | None, float | None]:
    if usar_ubicacion_usuario and ubicacion_usuario:
        lat = ubicacion_usuario.get("lat")
        lon = ubicacion_usuario.get("lon") or ubicacion_usuario.get("lng")
        if lat is not None and lon is not None:
            return float(lat), float(lon)

    if not punto_referencia or not punto_referencia.strip():
        return None, None

    texto = normalizar_texto(punto_referencia)
    params = params_texto_busqueda(texto, texto)
    score_nombre = sql_score_trgm("nombre")
    row = db.execute(
        text(
            f"""
            SELECT
                nombre,
                ST_Y(ubicacion::geometry) AS lat,
                ST_X(ubicacion::geometry) AS lon
            FROM turismo.sitio
            WHERE activo = TRUE
              AND ubicacion IS NOT NULL
              AND {score_nombre} > :umbral_candidato
            ORDER BY {score_nombre} DESC
            LIMIT 1
            """
        ),
        {**params, "umbral_candidato": UMBRAL_CATALOGO},
    ).mappings().first()

    if row and _referencia_catalogo_equivalente(
        punto_referencia,
        str(row["nombre"] or ""),
    ):
        return float(row["lat"]), float(row["lon"])

    lat, lon, _ = obtener_coordenadas_nominatim(punto_referencia)
    if lat is not None and lon is not None:
        return lat, lon

    return None, None


def resolver_distancia_metros(
    distancia: float | None,
    unidad: str | None,
) -> float:
    if distancia is None or distancia <= 0:
        return RADIO_BUSQUEDA_DEFECTO_M
    if unidad == "km":
        return distancia * 1000.0
    return distancia


def radios_a_intentar(
    distancia: float | None,
    unidad: str | None,
) -> list[float]:
    if distancia is None:
        return list(RADIOS_GIS_PROGRESIVOS_M)
    radio = resolver_distancia_metros(distancia, unidad)
    return [min(radio, RADIO_GIS_MAX_M)]


def modo_busqueda_gis(distancia: float | None) -> ModoBusquedaGis:
    return "progresivo" if distancia is None else "fijo"


def _esta_excluido_por_zona(
    nombre_sitio: str,
    zonas_excluidas: list[str],
) -> bool:
    if not zonas_excluidas or not nombre_sitio:
        return False
    for termino in zonas_excluidas:
        if score_trigram_local(nombre_sitio, termino) >= UMBRAL_EXCLUSION_ZONA:
            return True
    return False


def buscar_sitios_dentro_radio(
    db: Session,
    *,
    lat_origen: float,
    lon_origen: float,
    radio_metros: float,
    ids_consulta: list[int],
    zonas_excluidas: list[str],
) -> list[CandidatoGisEvaluado]:
    ids_validos = normalizar_ids_consulta(ids_consulta)
    if not ids_validos:
        return []

    rows = db.execute(
        text(
            """
            SELECT
                s.id_sitio,
                s.nombre,
                ST_Distance(s.ubicacion, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distancia
            FROM turismo.sitio s
            WHERE s.activo = TRUE
              AND s.ubicacion IS NOT NULL
              AND s.id_sitio = ANY(:ids_consulta)
              AND ST_DWithin(
                    s.ubicacion,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radio
                  )
            ORDER BY distancia ASC
            """
        ),
        {
            "lat": lat_origen,
            "lon": lon_origen,
            "radio": radio_metros,
            "ids_consulta": ids_validos,
        },
    ).mappings().all()

    candidatos: list[CandidatoGisEvaluado] = []
    for row in rows:
        nombre = str(row["nombre"] or "")
        if _esta_excluido_por_zona(nombre, zonas_excluidas):
            continue
        candidatos.append(
            CandidatoGisEvaluado(
                id_entidad=int(row["id_sitio"]),
                nombre=nombre,
                distancia_metros=round(float(row["distancia"]), 1),
            )
        )
    return candidatos


def buscar_rutas_dentro_radio(
    db: Session,
    *,
    lat_origen: float,
    lon_origen: float,
    radio_metros: float,
    ids_rutas: list[int],
    zonas_excluidas: list[str],
) -> list[CandidatoGisEvaluado]:
    ids_validos = normalizar_ids_consulta(ids_rutas)
    if not ids_validos:
        return []

    rows = db.execute(
        text(
            """
            WITH puntos_inicio AS (
                SELECT
                    rp.id_ruta,
                    rp.orden,
                    COALESCE(
                        rp.punto_inicio,
                        s.ubicacion
                    ) AS geom_inicio,
                    r.titulo
                FROM gis.ruta_puntos rp
                JOIN gis.rutas_turistica r
                  ON r.id_ruta = rp.id_ruta
                LEFT JOIN turismo.sitio s
                  ON s.id_sitio = rp.id_sitio
                 AND s.activo = TRUE
                WHERE rp.activo = TRUE
                  AND r.activo = TRUE
                  AND rp.id_ruta = ANY(:ids_rutas)
                  AND (
                        rp.punto_inicio IS NOT NULL
                        OR s.ubicacion IS NOT NULL
                      )
            ),
            distancias AS (
                SELECT
                    id_ruta,
                    MIN(
                        ST_Distance(
                            geom_inicio::geography,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                        )
                    ) AS distancia,
                    MIN(titulo) AS titulo
                FROM puntos_inicio
                WHERE geom_inicio IS NOT NULL
                GROUP BY id_ruta
            )
            SELECT id_ruta, distancia, titulo
            FROM distancias
            WHERE distancia <= :radio
            ORDER BY distancia ASC
            """
        ),
        {
            "lat": lat_origen,
            "lon": lon_origen,
            "radio": radio_metros,
            "ids_rutas": ids_validos,
        },
    ).mappings().all()

    candidatos: list[CandidatoGisEvaluado] = []
    for row in rows:
        titulo = str(row["titulo"] or "")
        if _esta_excluido_por_zona(titulo, zonas_excluidas):
            continue
        candidatos.append(
            CandidatoGisEvaluado(
                id_entidad=int(row["id_ruta"]),
                nombre=titulo,
                distancia_metros=round(float(row["distancia"]), 1),
            )
        )
    return candidatos


def _ejecutar_busqueda_por_radios(
    db: Session,
    *,
    lat: float,
    lon: float,
    distancia: float | None,
    unidad: str | None,
    buscar_en_radio,
    **kwargs,
) -> ResultadoGisEvaluacion:
    radios = radios_a_intentar(distancia, unidad)
    modo = modo_busqueda_gis(distancia)
    radios_intentados: list[float] = []

    for radio in radios:
        radios_intentados.append(radio)
        candidatos = buscar_en_radio(
            db,
            lat_origen=lat,
            lon_origen=lon,
            radio_metros=radio,
            **kwargs,
        )
        if candidatos:
            return ResultadoGisEvaluacion(
                ids=[item.id_entidad for item in candidatos],
                candidatos=candidatos,
                radio_aplicado_metros=radio,
                radios_intentados_metros=radios_intentados,
                modo_busqueda=modo,
            )

    return ResultadoGisEvaluacion(
        radios_intentados_metros=radios_intentados,
        modo_busqueda=modo,
    )


def filtrar_rutas_por_gis(
    db: Session,
    *,
    usar_ubicacion_usuario: bool | None,
    ubicacion_usuario: dict[str, float] | None,
    punto_referencia: str | None,
    distancia: float | None,
    unidad: str | None,
    ids_rutas: list[int],
    zonas_excluidas: list[str],
) -> ResultadoGisEvaluacion:
    lat, lon = resolver_punto_origen(
        db,
        bool(usar_ubicacion_usuario),
        ubicacion_usuario,
        punto_referencia,
    )
    if lat is None or lon is None:
        return ResultadoGisEvaluacion()

    return _ejecutar_busqueda_por_radios(
        db,
        lat=lat,
        lon=lon,
        distancia=distancia,
        unidad=unidad,
        buscar_en_radio=buscar_rutas_dentro_radio,
        ids_rutas=ids_rutas,
        zonas_excluidas=zonas_excluidas,
    )


def filtrar_sitios_por_gis(
    db: Session,
    *,
    usar_ubicacion_usuario: bool | None,
    ubicacion_usuario: dict[str, float] | None,
    punto_referencia: str | None,
    distancia: float | None,
    unidad: str | None,
    ids_consulta: list[int],
    zonas_excluidas: list[str],
) -> ResultadoGisEvaluacion:
    lat, lon = resolver_punto_origen(
        db,
        bool(usar_ubicacion_usuario),
        ubicacion_usuario,
        punto_referencia,
    )
    if lat is None or lon is None:
        return ResultadoGisEvaluacion()

    return _ejecutar_busqueda_por_radios(
        db,
        lat=lat,
        lon=lon,
        distancia=distancia,
        unidad=unidad,
        buscar_en_radio=buscar_sitios_dentro_radio,
        ids_consulta=ids_consulta,
        zonas_excluidas=zonas_excluidas,
    )
