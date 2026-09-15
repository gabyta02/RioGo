import json

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from esquemas.rutas_movil_turismo import (
    CoordenadaRutaMovilTurismo,
    PuntoRutaMovilTurismo,
    RutaMovilTurismo,
    RutasMovilTurismoResponse,
)

COLORES_RUTAS = [
    "#E53935",
    "#1E88E5",
    "#43A047",
    "#FB8C00",
    "#8E24AA",
    "#00ACC1",
    "#6D4C41",
    "#3949AB",
]


def obtener_color_ruta_movil_turismo(id_ruta: int) -> str:
    return COLORES_RUTAS[id_ruta % len(COLORES_RUTAS)]


def construir_leyenda_ruta_movil_turismo(titulo: str | None, id_ruta: int) -> str:
    return titulo or f"Ruta turística {id_ruta}"


def convertir_geom_linea_a_coordenadas_movil(geojson: str | None) -> list[CoordenadaRutaMovilTurismo]:
    if not geojson:
        return []
    coords = json.loads(geojson).get("coordinates", [])
    return [
        CoordenadaRutaMovilTurismo(latitud=float(c[1]), longitud=float(c[0]), orden=i + 1)
        for i, c in enumerate(coords)
    ]


def obtener_puntos_ruta_movil_turismo(db: Session, id_ruta: int) -> list[PuntoRutaMovilTurismo]:
    rows = db.execute(
        text(
            """
            SELECT
                rp.id_ruta_punto,
                rp.id_sitio,
                rp.orden,
                CASE WHEN rp.punto_inicio IS NOT NULL THEN TRUE ELSE FALSE END AS es_inicio,
                CASE WHEN rp.punto_fin IS NOT NULL THEN TRUE ELSE FALSE END AS es_fin,
                ST_Y(COALESCE(s.ubicacion::geometry, rp.punto_inicio, rp.punto_fin)) AS latitud,
                ST_X(COALESCE(s.ubicacion::geometry, rp.punto_inicio, rp.punto_fin)) AS longitud,
                s.nombre AS nombre_sitio
            FROM gis.ruta_puntos rp
            LEFT JOIN turismo.sitio s ON s.id_sitio = rp.id_sitio
            WHERE rp.id_ruta = :id_ruta AND rp.activo = TRUE
            ORDER BY rp.orden
            """
        ),
        {"id_ruta": id_ruta},
    ).mappings().all()

    puntos = []
    for row in rows:
        lat = row["latitud"]
        lng = row["longitud"]
        puntos.append(
            PuntoRutaMovilTurismo(
                id_ruta_punto=int(row["id_ruta_punto"]),
                id_sitio=int(row["id_sitio"]) if row["id_sitio"] else None,
                nombre_sitio=row["nombre_sitio"],
                orden=int(row["orden"]),
                punto_inicio=bool(row["es_inicio"]),
                punto_fin=bool(row["es_fin"]),
                latitud=float(lat) if lat else None,
                longitud=float(lng) if lng else None,
            )
        )
    return puntos


def listar_rutas_movil_turismo(db: Session) -> RutasMovilTurismoResponse:
    rows = db.execute(
        text(
            """
            SELECT
                r.id_ruta,
                r.tipo_ruta::TEXT AS tipo_ruta,
                r.titulo,
                r.url_imagen,
                r.descripcion,
                r.activo,
                ST_AsGeoJSON(r.geom_linea) AS linea_geojson
            FROM gis.rutas_turistica r
            WHERE r.activo = TRUE
            ORDER BY r.id_ruta DESC
            """
        )
    ).mappings().all()

    rutas = []
    for row in rows:
        id_ruta = int(row["id_ruta"])
        color = obtener_color_ruta_movil_turismo(id_ruta)
        leyenda = construir_leyenda_ruta_movil_turismo(row["titulo"], id_ruta)
        coordenadas = convertir_geom_linea_a_coordenadas_movil(row["linea_geojson"])
        puntos = obtener_puntos_ruta_movil_turismo(db, id_ruta)

        rutas.append(
            RutaMovilTurismo(
                id_ruta=id_ruta,
                tipo_ruta=row["tipo_ruta"],
                titulo=row["titulo"],
                url_imagen=row["url_imagen"],
                descripcion=row["descripcion"],
                color=color,
                leyenda=leyenda,
                activo=bool(row["activo"]),
                coordenadas=coordenadas,
                puntos=puntos,
            )
        )

    return RutasMovilTurismoResponse(total=len(rutas), rutas=rutas)


def obtener_ruta_movil_turismo_por_id(db: Session, id_ruta: int) -> RutaMovilTurismo:
    row = db.execute(
        text(
            """
            SELECT
                r.id_ruta,
                r.tipo_ruta::TEXT AS tipo_ruta,
                r.titulo,
                r.url_imagen,
                r.descripcion,
                r.activo,
                ST_AsGeoJSON(r.geom_linea) AS linea_geojson
            FROM gis.rutas_turistica r
            WHERE r.id_ruta = :id_ruta
            """
        ),
        {"id_ruta": id_ruta},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    color = obtener_color_ruta_movil_turismo(id_ruta)
    leyenda = construir_leyenda_ruta_movil_turismo(row["titulo"], id_ruta)
    coordenadas = convertir_geom_linea_a_coordenadas_movil(row["linea_geojson"])
    puntos = obtener_puntos_ruta_movil_turismo(db, id_ruta)

    return RutaMovilTurismo(
        id_ruta=id_ruta,
        tipo_ruta=row["tipo_ruta"],
        titulo=row["titulo"],
        url_imagen=row["url_imagen"],
        descripcion=row["descripcion"],
        color=color,
        leyenda=leyenda,
        activo=bool(row["activo"]),
        coordenadas=coordenadas,
        puntos=puntos,
    )