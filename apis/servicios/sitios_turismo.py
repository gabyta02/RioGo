from sqlalchemy import text
from sqlalchemy.orm import Session

from core.imagenes import normalizar_url_imagen
from modelos.sitios_turismo import Categoria, Subcategoria
from cache_redis import RedisCliente


redis_cliente = RedisCliente()

CLAVE_HASH_SITIOS = "sitios:items:v2"


def obtener_categorias(db: Session):
    return (
        db.query(Categoria)
        .filter(Categoria.activo == True)
        .order_by(Categoria.nombre)
        .all()
    )


def obtener_subcategorias(db: Session, id_categoria: int):
    return (
        db.query(Subcategoria)
        .filter(
            Subcategoria.id_categoria == id_categoria,
            Subcategoria.activo == True,
        )
        .order_by(Subcategoria.nombre)
        .all()
    )


def transformar_sitio_resumen(row) -> dict:
    sitio = dict(row._mapping)
    imagen_original = sitio.get("img_url", sitio.get("img_Url"))

    point = sitio.get("point")
    if point and not isinstance(point, dict):
        point = {
            "type": "Point",
            "coordinates": [
                float(sitio["longitud"]),
                float(sitio["latitud"]),
            ],
        }

    return {
        "id_sitio": sitio["id_sitio"],
        "id_categoria": sitio["id_categoria"],
        "id_subcategoria": sitio["id_subcategoria"],
        "nombre": sitio["nombre"],
        "categoria": sitio["categoria"],
        "subcategoria": sitio["subcategoria"],
        "descripcion": sitio["descripcion"],
        "direccion": sitio["direccion"],
        "img_Url": normalizar_url_imagen(imagen_original),
        "point": point,
    }


def query_sitios_resumen(where: str = ""):
    return text(f"""
        SELECT
            s.id_sitio,
            s.id_categoria,
            s.id_subcategoria,
            s.nombre,
            c.nombre AS categoria,
            sc.nombre AS subcategoria,
            s.descripcion_corta AS descripcion,
            d.direccion_texto AS direccion,
            (
                SELECT m.url
                FROM turismo.multimedia m
                WHERE m.id_sitio = s.id_sitio
                  AND m.activo = TRUE
                ORDER BY m.es_principal DESC NULLS LAST, m.id_multimedia ASC
                LIMIT 1
            ) AS img_url,
            CASE
                WHEN s.ubicacion IS NULL THEN NULL
                ELSE json_build_object(
                    'type', 'Point',
                    'coordinates', json_build_array(
                        ST_X(s.ubicacion::geometry),
                        ST_Y(s.ubicacion::geometry)
                    )
                )
            END AS point,
            ST_X(s.ubicacion::geometry) AS longitud,
            ST_Y(s.ubicacion::geometry) AS latitud
        FROM turismo.sitio s
        JOIN turismo.categoria c ON c.id_categoria = s.id_categoria
        LEFT JOIN turismo.subcategoria sc ON sc.id_subcategoria = s.id_subcategoria
        LEFT JOIN turismo.direccion d ON d.id_sitio = s.id_sitio
        WHERE s.activo = TRUE
        {where}
        ORDER BY s.nombre ASC
    """)


def consultar_sitios_resumen_db(db: Session):
    rows = db.execute(query_sitios_resumen()).fetchall()
    return [transformar_sitio_resumen(row) for row in rows]


def consultar_sitio_resumen_db(db: Session, id_sitio: int):
    row = db.execute(
        query_sitios_resumen("AND s.id_sitio = :id_sitio"),
        {"id_sitio": id_sitio},
    ).first()

    if not row:
        return None

    return transformar_sitio_resumen(row)


def cargar_cache_sitios_si_vacia(db: Session) -> None:
    if redis_cliente.hlen(CLAVE_HASH_SITIOS) > 0:
        return

    for sitio in consultar_sitios_resumen_db(db):
        redis_cliente.hset_json(
            CLAVE_HASH_SITIOS,
            str(sitio["id_sitio"]),
            sitio,
        )


def obtener_sitios_cacheados(db: Session):
    cargar_cache_sitios_si_vacia(db)
    return list(redis_cliente.hgetall_json(CLAVE_HASH_SITIOS).values())


def filtrar_sitios_cacheados(
    sitios: list[dict],
    id_categoria: int | None = None,
    id_subcategoria: int | None = None,
    nombre: str | None = None,
):
    if id_categoria:
        sitios = [
            sitio for sitio in sitios
            if sitio.get("id_categoria") == id_categoria
        ]

    if id_subcategoria:
        sitios = [
            sitio for sitio in sitios
            if sitio.get("id_subcategoria") == id_subcategoria
        ]

    if nombre:
        nombre_normalizado = nombre.strip().lower()
        sitios = [
            sitio for sitio in sitios
            if nombre_normalizado in sitio.get("nombre", "").lower()
        ]

    return sorted(sitios, key=lambda sitio: sitio.get("nombre", ""))


def limpiar_campos_internos(sitio: dict) -> dict:
    return {
        clave: valor
        for clave, valor in sitio.items()
        if clave not in {"id_categoria", "id_subcategoria"}
    }


def normalizar_sitio_respuesta(sitio: dict) -> dict:
    sitio_respuesta = dict(sitio)
    imagen_original = sitio_respuesta.get("img_url", sitio_respuesta.get("img_Url"))
    sitio_respuesta["img_Url"] = normalizar_url_imagen(imagen_original)
    return sitio_respuesta


def listar_sitios_resumen(
    db: Session,
    id_categoria: int | None = None,
    id_subcategoria: int | None = None,
    nombre: str | None = None,
):
    sitios = filtrar_sitios_cacheados(
        obtener_sitios_cacheados(db),
        id_categoria=id_categoria,
        id_subcategoria=id_subcategoria,
        nombre=nombre,
    )

    return [
        limpiar_campos_internos(normalizar_sitio_respuesta(sitio))
        for sitio in sitios
    ]


def actualizar_sitio_cache(db: Session, id_sitio: int):
    sitio = consultar_sitio_resumen_db(db, id_sitio)

    if not sitio:
        return None

    redis_cliente.hset_json(CLAVE_HASH_SITIOS, str(id_sitio), sitio)

    return {
        "accion": "upsert",
        "id_sitio": id_sitio,
        "sitio": limpiar_campos_internos(normalizar_sitio_respuesta(sitio)),
    }


def eliminar_sitio_cache(id_sitio: int):
    eliminado = redis_cliente.hdel(CLAVE_HASH_SITIOS, str(id_sitio))

    return {
        "accion": "delete",
        "id_sitio": id_sitio,
        "eliminado": eliminado > 0,
    }


def cargar_cache_sitios(db: Session):
    sitios = consultar_sitios_resumen_db(db)

    for sitio in sitios:
        redis_cliente.hset_json(
            CLAVE_HASH_SITIOS,
            str(sitio["id_sitio"]),
            sitio,
        )

    return {
        "total": len(sitios),
    }
