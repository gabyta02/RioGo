from pathlib import Path
from typing import Any
from uuid import uuid4
import json
import re
import shutil
import unicodedata

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.trazabilidad import ACTOR_SISTEMA, ActorTrazabilidad, registrar_evento_actor
from servicios.panel_administrativo.chunks_descripcion import regenerar_chunk_descripcion
from servicios.panel_administrativo.contenido_chatbots import eliminar_directorios_repositorio, eliminar_repositorios_de_vinculo
from esquemas.panel_administrativo.rutas_turisticas import (
    EstadoRuta,
    ImagenRutaResponse,
    RutaGeometriaResponse,
    RutaGeometriaUpdate,
    RutaCreate,
    RutaResponse,
    RutasListResponse,
    RutaUpdate,
    SitioRutaResponse,
    TipoRuta,
)

IMAGES_DIR = Path("fuente_datos/imagenes/rutas")
IMAGE_URL_PREFIX = "/api/v1/imagenes/rutas"


def _trazar(
    db: Session,
    actor: ActorTrazabilidad,
    accion: str,
    tabla: str,
    entidad: str | int | None = None,
    anterior: dict | None = None,
    nuevo: dict | None = None,
    referencia: str | None = None,
    esquema: str = "gis",
) -> None:
    registrar_evento_actor(
        db,
        actor,
        accion=accion,
        esquema_modificado=esquema,
        tabla_modificada=tabla,
        entidad_modificada=entidad,
        datos_anteriores=anterior,
        datos_nuevos=nuevo,
        referencia=referencia,
    )


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _route_response(row: dict[str, Any]) -> RutaResponse:
    return RutaResponse(**row)


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "ruta"


def _titulo_documento_ruta(documento: str) -> str:
    nombre_archivo = Path(documento).name.strip()
    titulo = Path(nombre_archivo).stem.strip() or documento.strip()
    return titulo[:200]


def _local_image_path(url: str | None) -> Path | None:
    if not url or not url.startswith(f"{IMAGE_URL_PREFIX}/"):
        return None
    relative = url.removeprefix(f"{IMAGE_URL_PREFIX}/").lstrip("/")
    path = (IMAGES_DIR / relative).resolve()
    base = IMAGES_DIR.resolve()
    if base not in path.parents:
        return None
    return path


def _eliminar_archivo_local(url: str | None) -> None:
    path = _local_image_path(url)
    if not path or not path.exists() or not path.is_file():
        return
    parent = path.parent
    path.unlink()
    try:
        parent.rmdir()
    except OSError:
        pass


def guardar_imagen_ruta(titulo_ruta: str, archivo: UploadFile) -> ImagenRutaResponse:
    if not titulo_ruta.strip():
        raise _bad_request("Debe enviar el titulo de la ruta para guardar la imagen")
    if not archivo.content_type or not archivo.content_type.startswith("image/"):
        raise _bad_request("El archivo debe ser una imagen")

    extension = Path(archivo.filename or "").suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".jpg"

    ruta_dir = IMAGES_DIR / _slugify(titulo_ruta)
    ruta_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    destination = ruta_dir / filename

    with destination.open("wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    return ImagenRutaResponse(
        url=f"{IMAGE_URL_PREFIX}/{ruta_dir.name}/{filename}",
        nombre_archivo=filename,
    )


def _line_wkt(linea) -> str | None:
    if not linea:
        return None
    if len(linea) < 2:
        raise _bad_request("La linea debe tener al menos dos puntos")
    pairs = [f"{point.longitud} {point.latitud}" for point in linea]
    return f"LINESTRING({', '.join(pairs)})"


def _point_wkt(point) -> str | None:
    if not point:
        return None
    return f"POINT({point.longitud} {point.latitud})"


def _point_wkt_from_lat_lng(latitud: float | None, longitud: float | None) -> str | None:
    if latitud is None or longitud is None:
        return None
    return f"POINT({longitud} {latitud})"


_COORDINATE_EPSILON = 0.000001


def _same_coordinate(a, b) -> bool:
    return (
        abs(float(a.latitud) - float(b.latitud)) <= _COORDINATE_EPSILON
        and abs(float(a.longitud) - float(b.longitud)) <= _COORDINATE_EPSILON
    )


def _validar_geometria_ruta(db: Session, datos: RutaGeometriaUpdate) -> None:
    """Validate the complete route before changing any persisted geometry."""
    linea = datos.linea
    puntos = sorted(datos.puntos, key=lambda item: item.orden)

    if len(linea) < 2:
        raise _bad_request("La línea debe tener al menos dos vértices")
    if any(_same_coordinate(linea[index - 1], coordinate) for index, coordinate in enumerate(linea) if index):
        raise _bad_request("La línea no puede tener vértices consecutivos repetidos")
    if len(puntos) < 2:
        raise _bad_request("La ruta debe tener un origen y un destino")

    expected_order = list(range(1, len(puntos) + 1))
    if [point.orden for point in puntos] != expected_order:
        raise _bad_request("Los puntos de la ruta deben tener un orden consecutivo")
    if puntos[0].tipo != "inicio" or puntos[-1].tipo != "fin":
        raise _bad_request("El primer punto debe ser el origen y el último el destino")
    if sum(point.tipo == "inicio" for point in puntos) != 1 or sum(point.tipo == "fin" for point in puntos) != 1:
        raise _bad_request("La ruta debe tener exactamente un origen y un destino")

    for index, punto in enumerate(puntos):
        is_endpoint = index in {0, len(puntos) - 1}
        if punto.tipo == "sitio":
            if is_endpoint:
                raise _bad_request("Los sitios solo pueden ser paradas intermedias")
            if not punto.id_sitio:
                raise _bad_request("Los puntos de tipo sitio deben enviar id_sitio")
            sitio = db.execute(
                text(
                    """
                    SELECT ST_Y(ubicacion::geometry) AS latitud, ST_X(ubicacion::geometry) AS longitud
                    FROM turismo.sitio
                    WHERE id_sitio = :id_sitio AND activo = TRUE AND ubicacion IS NOT NULL
                    """
                ),
                {"id_sitio": punto.id_sitio},
            ).mappings().first()
            if not sitio:
                raise _bad_request("El sitio seleccionado no existe, está inactivo o no tiene ubicación")
            # A site is an anchor: never trust a draggable client coordinate for it.
            punto.latitud = float(sitio["latitud"])
            punto.longitud = float(sitio["longitud"])
        else:
            if punto.id_sitio:
                raise _bad_request("Solo las paradas intermedias pueden estar vinculadas a un sitio")
            if punto.latitud is None or punto.longitud is None:
                raise _bad_request("Los puntos libres deben enviar latitud y longitud")
            if is_endpoint and punto.tipo not in {"inicio", "fin"}:
                raise _bad_request("Los extremos de la ruta deben ser origen y destino")
            if not is_endpoint and punto.tipo != "libre":
                raise _bad_request("Los puntos intermedios deben ser libres o sitios")

        if not any(_same_coordinate(punto, coordinate) for coordinate in linea):
            raise _bad_request("Cada punto de control debe coincidir con un vértice de la línea")


def _validar_puntos(puntos) -> None:
    for punto in puntos or []:
        if not punto.id_sitio and not punto.punto_inicio and not punto.punto_fin:
            raise _bad_request("Cada punto debe tener sitio, punto_inicio o punto_fin")


def _insertar_relaciones_ruta(db: Session, id_ruta: int, datos: RutaCreate | RutaUpdate) -> None:
    puntos = datos.puntos or []
    _validar_puntos(puntos)

    for punto in puntos:
        db.execute(
            text(
                """
                INSERT INTO gis.ruta_puntos (
                    id_ruta,
                    id_sitio,
                    punto_inicio,
                    punto_fin,
                    orden,
                    activo
                )
                VALUES (
                    :id_ruta,
                    :id_sitio,
                    CASE
                        WHEN :punto_inicio IS NULL THEN NULL
                        ELSE ST_GeomFromText(:punto_inicio, 4326)
                    END,
                    CASE
                        WHEN :punto_fin IS NULL THEN NULL
                        ELSE ST_GeomFromText(:punto_fin, 4326)
                    END,
                    :orden,
                    TRUE
                )
                """
            ),
            {
                "id_ruta": id_ruta,
                "id_sitio": punto.id_sitio,
                "punto_inicio": _point_wkt(punto.punto_inicio),
                "punto_fin": _point_wkt(punto.punto_fin),
                "orden": punto.orden,
            },
        )

    for documento in datos.documentos or []:
        if documento:
            db.execute(
                text(
                    """
                    INSERT INTO turismo.sitio_documento (
                        origen,
                        titulo,
                        id_vinculo,
                        repositorio_nombre,
                        descripcion,
                        ruta_archivo,
                        activo
                    )
                    VALUES (
                        'ruta',
                        :titulo,
                        :id_ruta,
                        NULL,
                        :descripcion,
                        :ruta_archivo,
                        TRUE
                    )
                    """
                ),
                {
                    "id_ruta": id_ruta,
                    "titulo": _titulo_documento_ruta(documento),
                    "descripcion": documento,
                    "ruta_archivo": documento,
                },
            )


def listar_rutas(
    db: Session,
    q: str | None,
    tipo_ruta: TipoRuta | None,
    estado: EstadoRuta,
    page: int,
    page_size: int,
) -> RutasListResponse:
    params: dict[str, Any] = {}
    filtros = []

    if q:
        filtros.append("r.titulo ILIKE :q")
        params["q"] = f"%{q.strip()}%"
    if tipo_ruta:
        filtros.append("r.tipo_ruta = :tipo_ruta")
        params["tipo_ruta"] = tipo_ruta
    if estado == "activo":
        filtros.append("r.activo = TRUE")
    elif estado == "inactivo":
        filtros.append("r.activo = FALSE")

    where_sql = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size

    total = int(
        db.execute(
            text(f"SELECT COUNT(*) FROM gis.rutas_turistica r {where_sql}"),
            params,
        ).scalar()
        or 0
    )

    rows = db.execute(
        text(
            f"""
            SELECT
                r.id_ruta,
                r.tipo_ruta::TEXT AS tipo_ruta,
                r.titulo,
                r.url_imagen,
                r.descripcion,
                r.activo,
                COUNT(rp.id_ruta_punto)::INT AS total_puntos,
                (r.geom_linea IS NOT NULL) AS tiene_linea
            FROM gis.rutas_turistica r
            LEFT JOIN gis.ruta_puntos rp ON rp.id_ruta = r.id_ruta AND rp.activo = TRUE
            {where_sql}
            GROUP BY r.id_ruta, r.tipo_ruta, r.titulo, r.url_imagen, r.descripcion, r.activo, r.geom_linea
            ORDER BY r.id_ruta DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    return RutasListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[_route_response(dict(row)) for row in rows],
    )


def buscar_sitios_para_ruta(db: Session, q: str | None, limit: int) -> list[SitioRutaResponse]:
    params: dict[str, Any] = {"limit": limit}
    filtros = ["s.activo = TRUE", "s.ubicacion IS NOT NULL"]
    if q:
        filtros.append("s.nombre ILIKE :q")
        params["q"] = f"%{q.strip()}%"

    rows = db.execute(
        text(
            f"""
            SELECT
                s.id_sitio,
                s.nombre,
                c.nombre AS categoria,
                sc.nombre AS subcategoria,
                ST_Y(s.ubicacion::geometry) AS latitud,
                ST_X(s.ubicacion::geometry) AS longitud
            FROM turismo.sitio s
            LEFT JOIN turismo.categoria c ON c.id_categoria = s.id_categoria
            LEFT JOIN turismo.subcategoria sc ON sc.id_subcategoria = s.id_subcategoria
            WHERE {' AND '.join(filtros)}
            ORDER BY s.nombre ASC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()
    return [SitioRutaResponse(**dict(row)) for row in rows]


def obtener_geometria_ruta(db: Session, id_ruta: int) -> RutaGeometriaResponse:
    ruta = db.execute(
        text(
            """
            SELECT id_ruta, titulo, ST_AsGeoJSON(geom_linea) AS linea_geojson
            FROM gis.rutas_turistica
            WHERE id_ruta = :id_ruta
            """
        ),
        {"id_ruta": id_ruta},
    ).mappings().first()
    if not ruta:
        raise _not_found("La ruta no existe")

    linea: list[dict[str, float]] = []
    if ruta["linea_geojson"]:
        geojson = json.loads(ruta["linea_geojson"])
        linea = [
            {"longitud": float(coord[0]), "latitud": float(coord[1])}
            for coord in geojson.get("coordinates", [])
        ]

    rows = db.execute(
        text(
            """
            SELECT
                rp.orden,
                rp.id_sitio,
                s.nombre AS nombre_sitio,
                CASE
                    WHEN rp.punto_fin IS NOT NULL THEN 'fin'
                    WHEN rp.punto_inicio IS NOT NULL AND rp.orden = 1 THEN 'inicio'
                    WHEN rp.id_sitio IS NOT NULL THEN 'sitio'
                    ELSE 'libre'
                END AS tipo,
                ST_Y(COALESCE(s.ubicacion::geometry, rp.punto_inicio, rp.punto_fin)) AS latitud,
                ST_X(COALESCE(s.ubicacion::geometry, rp.punto_inicio, rp.punto_fin)) AS longitud
            FROM gis.ruta_puntos rp
            LEFT JOIN turismo.sitio s ON s.id_sitio = rp.id_sitio
            WHERE rp.id_ruta = :id_ruta AND rp.activo = TRUE
            ORDER BY rp.orden ASC, rp.id_ruta_punto ASC
            """
        ),
        {"id_ruta": id_ruta},
    ).mappings().all()

    return RutaGeometriaResponse(
        id_ruta=int(ruta["id_ruta"]),
        titulo=ruta["titulo"],
        linea=linea,
        puntos=[dict(row) for row in rows],
    )


def guardar_geometria_ruta(
    db: Session,
    id_ruta: int,
    datos: RutaGeometriaUpdate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> RutaGeometriaResponse:
    ruta = db.execute(
        text("SELECT titulo, (geom_linea IS NOT NULL) AS tiene_linea FROM gis.rutas_turistica WHERE id_ruta = :id_ruta"),
        {"id_ruta": id_ruta},
    ).mappings().first()
    if ruta is None:
        raise _not_found("La ruta no existe")

    # All semantic and database-dependent validation happens before DELETE.
    _validar_geometria_ruta(db, datos)
    line_wkt = _line_wkt(datos.linea)

    try:
        db.execute(
            text(
                """
                UPDATE gis.rutas_turistica
                SET geom_linea = ST_GeomFromText(:line_wkt, 4326)
                WHERE id_ruta = :id_ruta
                """
            ),
            {"id_ruta": id_ruta, "line_wkt": line_wkt},
        )
        db.execute(text("DELETE FROM gis.ruta_puntos WHERE id_ruta = :id_ruta"), {"id_ruta": id_ruta})

        for punto in sorted(datos.puntos, key=lambda item: item.orden):
            point_wkt = _point_wkt_from_lat_lng(punto.latitud, punto.longitud)
            punto_inicio = point_wkt if punto.tipo in {"inicio", "libre"} else None
            punto_fin = point_wkt if punto.tipo == "fin" else None
            db.execute(
                text(
                    """
                    INSERT INTO gis.ruta_puntos (
                        id_ruta, id_sitio, punto_inicio, punto_fin, orden, activo
                    ) VALUES (
                        :id_ruta, :id_sitio,
                        CASE WHEN :punto_inicio IS NULL THEN NULL ELSE ST_GeomFromText(:punto_inicio, 4326) END,
                        CASE WHEN :punto_fin IS NULL THEN NULL ELSE ST_GeomFromText(:punto_fin, 4326) END,
                        :orden, TRUE
                    )
                    """
                ),
                {
                    "id_ruta": id_ruta,
                    "id_sitio": punto.id_sitio,
                    "punto_inicio": punto_inicio,
                    "punto_fin": punto_fin,
                    "orden": punto.orden,
                },
            )

        _trazar(
            db,
            actor,
            "UPDATE",
            "rutas_turistica",
            id_ruta,
            anterior={"geometria": "registrada" if ruta["tiene_linea"] else None},
            nuevo={"geometria": "actualizada"},
            referencia=ruta["titulo"],
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return obtener_geometria_ruta(db, id_ruta)


def crear_ruta(
    db: Session,
    datos: RutaCreate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> RutaResponse:
    line_wkt = _line_wkt(datos.linea)
    row = db.execute(
        text(
            """
            INSERT INTO gis.rutas_turistica (
                tipo_ruta,
                titulo,
                url_imagen,
                descripcion,
                geom_linea,
                activo
            )
            VALUES (
                :tipo_ruta,
                :titulo,
                :url_imagen,
                :descripcion,
                CASE
                    WHEN :line_wkt IS NULL THEN NULL
                    ELSE ST_GeomFromText(:line_wkt, 4326)
                END,
                :activo
            )
            RETURNING id_ruta
            """
        ),
        {
            "tipo_ruta": datos.tipo_ruta,
            "titulo": datos.titulo,
            "url_imagen": datos.url_imagen,
            "descripcion": datos.descripcion,
            "line_wkt": line_wkt,
            "activo": datos.activo,
        },
    ).mappings().one()

    id_ruta = int(row["id_ruta"])
    _insertar_relaciones_ruta(db, id_ruta, datos)
    regenerar_chunk_descripcion(db, "ruta", id_ruta)
    _trazar(
        db,
        actor,
        "INSERT",
        "rutas_turistica",
        id_ruta,
        nuevo={"titulo": datos.titulo},
    )
    db.commit()

    return listar_rutas(db, None, None, "all", 1, 1).items[0]


def actualizar_ruta(
    db: Session,
    id_ruta: int,
    datos: RutaUpdate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> RutaResponse:
    anterior = db.execute(
        text(
            """
            SELECT id_ruta, tipo_ruta::TEXT AS tipo_ruta, titulo, url_imagen, descripcion, activo
            FROM gis.rutas_turistica
            WHERE id_ruta = :id_ruta
            """
        ),
        {"id_ruta": id_ruta},
    ).mappings().first()
    if not anterior:
        raise _not_found("La ruta no existe")
    old_url_imagen = anterior["url_imagen"]

    update_data = datos.model_dump(exclude_unset=True) if hasattr(datos, "model_dump") else datos.dict(exclude_unset=True)
    relation_keys = {"linea", "puntos", "documentos"}
    route_data = {key: value for key, value in update_data.items() if key not in relation_keys}

    if "linea" in update_data:
        route_data["line_wkt"] = _line_wkt(datos.linea)
        route_data["geom_linea"] = None

    if route_data:
        assignments = []
        params = {"id_ruta": id_ruta}
        for key, value in route_data.items():
            if key == "line_wkt":
                continue
            if key == "geom_linea":
                assignments.append(
                    "geom_linea = CASE WHEN :line_wkt IS NULL THEN NULL ELSE ST_GeomFromText(:line_wkt, 4326) END"
                )
                params["line_wkt"] = route_data["line_wkt"]
            else:
                assignments.append(f"{key} = :{key}")
                params[key] = value

        db.execute(
            text(
                f"""
                UPDATE gis.rutas_turistica
                SET {', '.join(assignments)}
                WHERE id_ruta = :id_ruta
                """
            ),
            params,
        )

    if "puntos" in update_data:
        db.execute(text("DELETE FROM gis.ruta_puntos WHERE id_ruta = :id_ruta"), {"id_ruta": id_ruta})
        _insertar_relaciones_ruta(db, id_ruta, datos)

    if "documentos" in update_data:
        db.execute(
            text(
                """
                DELETE FROM turismo.sitio_documento
                WHERE origen = 'ruta'
                  AND id_vinculo = :id_ruta
                """
            ),
            {"id_ruta": id_ruta},
        )
        _insertar_relaciones_ruta(
            db,
            id_ruta,
            RutaCreate(
                tipo_ruta=datos.tipo_ruta or "Otras",
                titulo=datos.titulo or "Ruta",
                documentos=datos.documentos or [],
                puntos=[],
                linea=None,
            ),
        )

    if "descripcion" in update_data:
        regenerar_chunk_descripcion(db, "ruta", id_ruta)

    _trazar(
        db,
        actor,
        "UPDATE",
        "rutas_turistica",
        id_ruta,
        anterior=dict(anterior),
        nuevo=dict(update_data),
        referencia=update_data.get("titulo") or anterior["titulo"],
    )
    db.commit()
    if "url_imagen" in update_data and old_url_imagen != datos.url_imagen:
        _eliminar_archivo_local(old_url_imagen)
    result = listar_rutas(db, None, None, "all", 1, 1000)
    for item in result.items:
        if item.id_ruta == id_ruta:
            return item
    raise _not_found("La ruta no existe")


def eliminar_ruta(
    db: Session,
    id_ruta: int,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> RutaResponse:
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
                COUNT(rp.id_ruta_punto)::INT AS total_puntos,
                (r.geom_linea IS NOT NULL) AS tiene_linea
            FROM gis.rutas_turistica r
            LEFT JOIN gis.ruta_puntos rp ON rp.id_ruta = r.id_ruta
            WHERE r.id_ruta = :id_ruta
            GROUP BY r.id_ruta, r.tipo_ruta, r.titulo, r.url_imagen, r.descripcion, r.activo, r.geom_linea
            """
        ),
        {"id_ruta": id_ruta},
    ).mappings().first()
    if not row:
        raise _not_found("La ruta no existe")
    repo_paths = eliminar_repositorios_de_vinculo(db, "ruta", id_ruta)
    db.execute(text("DELETE FROM gis.rutas_turistica WHERE id_ruta = :id_ruta"), {"id_ruta": id_ruta})
    _trazar(
        db,
        actor,
        "DELETE",
        "rutas_turistica",
        id_ruta,
        anterior=dict(row),
        referencia=row["titulo"],
    )
    db.commit()
    _eliminar_archivo_local(row["url_imagen"])
    eliminar_directorios_repositorio(repo_paths)
    return RutaResponse(
        id_ruta=row["id_ruta"],
        tipo_ruta=row["tipo_ruta"],
        titulo=row["titulo"],
        url_imagen=None,
        descripcion=row["descripcion"],
        activo=False,
        total_puntos=0,
        tiene_linea=False,
    )


def cambiar_estado_ruta(
    db: Session,
    id_ruta: int,
    activo: bool,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> RutaResponse:
    anterior = db.execute(
        text("SELECT titulo, activo FROM gis.rutas_turistica WHERE id_ruta = :id_ruta"),
        {"id_ruta": id_ruta},
    ).mappings().first()
    if not anterior:
        raise _not_found("La ruta no existe")
    row = db.execute(
        text("UPDATE gis.rutas_turistica SET activo = :activo WHERE id_ruta = :id_ruta RETURNING id_ruta"),
        {"id_ruta": id_ruta, "activo": activo},
    ).first()
    _trazar(
        db,
        actor,
        "UPDATE",
        "rutas_turistica",
        id_ruta,
        anterior={"activo": anterior["activo"]},
        nuevo={"activo": activo},
        referencia=anterior["titulo"],
    )
    db.commit()
    result = listar_rutas(db, None, None, "all", 1, 1000)
    for item in result.items:
        if item.id_ruta == id_ruta:
            return item
    raise _not_found("La ruta no existe")
