from pathlib import Path
from typing import Any
from uuid import uuid4
import re
import shutil
import unicodedata

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.trazabilidad import ACTOR_SISTEMA, ActorTrazabilidad, registrar_evento_actor
from core.autenticacion.permisos import aplicar_filtro_sitios_sql, obtener_sitios_permitidos, validar_acceso_sitio
from servicios.panel_administrativo.chunks_descripcion import regenerar_chunk_descripcion
from servicios.panel_administrativo.contenido_chatbots import eliminar_directorios_repositorio, eliminar_repositorios_de_vinculo
from esquemas.panel_administrativo.atractivos import (
    CatalogoSimpleResponse,
    CategoriaCreate,
    CategoriaDetalleResponse,
    CategoriaResponse,
    CategoriaUpdate,
    EstadoAtractivo,
    PrecioFiltro,
    ServicioFiltro,
    ImagenSubidaResponse,
    SitioCreate,
    SitioDetalleResponse,
    SitioResponse,
    SitiosListResponse,
    SubcategoriaCreate,
    SubcategoriaDetalleResponse,
    SubcategoriaResponse,
    SubcategoriaUpdate,
)

IMAGES_DIR = Path("fuente_datos/imagenes")
IMAGE_URL_PREFIX = "/api/v1/imagenes"


def _trazar(
    db: Session,
    actor: ActorTrazabilidad,
    accion: str,
    tabla: str,
    entidad: str | int | None = None,
    anterior: dict | None = None,
    nuevo: dict | None = None,
    referencia: str | None = None,
    esquema: str = "turismo",
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


def _resolver_detalles_horario(horario) -> list[tuple[int, str, str]]:
    """Devuelve la lista [(dia_semana, hora_inicio, hora_fin)] a persistir
    en `turismo.horario_detalle`.

    - Si `abierto_24h`, replica 00:00-23:59 en cada dia.
    - Si hay `detalles`, los usa tal cual (puede haber multiples filas por dia).
    - Si no, replica el rango global en cada dia de `dias_semana`.
    Los dias con `cerrado=True` se omiten (el contrato los representa por
    ausencia de fila; `dias_semana` indica que el sitio esta "abierto" ese
    dia, y la app/cliente infiere "cerrado" si no hay detalle).
    """
    if horario.abierto_24h:
        return [(dia, "00:00", "23:59") for dia in horario.dias_semana]

    if horario.detalles:
        resultado: list[tuple[int, str, str]] = []
        for detalle in horario.detalles:
            if detalle.cerrado:
                continue
            resultado.append(
                (
                    detalle.dia_semana,
                    detalle.hora_inicio or horario.hora_inicio,
                    detalle.hora_fin or horario.hora_fin,
                )
            )
        return resultado

    return [
        (dia, horario.hora_inicio, horario.hora_fin)
        for dia in horario.dias_semana
    ]


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "sitio"


def _local_image_path(url: str | None) -> Path | None:
    if not url or not url.startswith(f"{IMAGE_URL_PREFIX}/"):
        return None
    relative = url.removeprefix(f"{IMAGE_URL_PREFIX}/").lstrip("/")
    path = (IMAGES_DIR / relative).resolve()
    base = IMAGES_DIR.resolve()
    if base not in path.parents:
        return None
    return path


def _eliminar_archivos_locales(urls: list[str]) -> None:
    touched_dirs: set[Path] = set()
    for url in urls:
        path = _local_image_path(url)
        if not path or not path.exists() or not path.is_file():
            continue
        touched_dirs.add(path.parent)
        path.unlink()

    for directory in touched_dirs:
        try:
            directory.rmdir()
        except OSError:
            pass


def _sitio_select_sql() -> str:
    return """
        SELECT
            s.id_sitio,
            s.nombre,
            s.descripcion_corta,
            s.id_categoria,
            c.nombre AS categoria,
            s.id_subcategoria,
            sc.nombre AS subcategoria,
            s.activo,
            m.url AS imagen_url
        FROM turismo.sitio s
        JOIN turismo.categoria c ON c.id_categoria = s.id_categoria
        LEFT JOIN turismo.subcategoria sc ON sc.id_subcategoria = s.id_subcategoria
        LEFT JOIN LATERAL (
            SELECT url
            FROM turismo.multimedia
            WHERE id_sitio = s.id_sitio AND activo = TRUE
            ORDER BY es_principal DESC, id_multimedia ASC
            LIMIT 1
        ) m ON TRUE
    """


def _sitio_response(row: dict[str, Any]) -> SitioResponse:
    return SitioResponse(**row)


def _existe_categoria(db: Session, id_categoria: int) -> bool:
    return (
        db.execute(
            text("SELECT 1 FROM turismo.categoria WHERE id_categoria = :id_categoria"),
            {"id_categoria": id_categoria},
        ).first()
        is not None
    )


def _existe_subcategoria(db: Session, id_subcategoria: int, id_categoria: int) -> bool:
    return (
        db.execute(
            text(
                """
                SELECT 1
                FROM turismo.subcategoria
                WHERE id_subcategoria = :id_subcategoria
                  AND id_categoria = :id_categoria
                """
            ),
            {"id_subcategoria": id_subcategoria, "id_categoria": id_categoria},
        ).first()
        is not None
    )


def _validar_plataforma(db: Session, id_plataforma: int, id_parroquia: int) -> None:
    plataforma = db.execute(
        text(
            """
            SELECT id_parroquia
            FROM turismo.plataforma
            WHERE id_plataforma = :id_plataforma
            """
        ),
        {"id_plataforma": id_plataforma},
    ).mappings().first()

    if not plataforma:
        raise _not_found("La plataforma no existe")

    if int(plataforma["id_parroquia"]) != id_parroquia:
        raise _bad_request("La plataforma no pertenece a la parroquia enviada")


def _validar_parroquia(db: Session, id_parroquia: int) -> None:
    if (
        db.execute(
            text("SELECT 1 FROM turismo.parroquia WHERE id_parroquia = :id_parroquia"),
            {"id_parroquia": id_parroquia},
        ).first()
        is None
    ):
        raise _not_found("La parroquia no existe")


def _validar_catalogos_sitio(db: Session, datos: SitioCreate) -> None:
    _validar_ubicacion_catalogo(db, datos)
    _validar_categoria_subcategoria(db, datos)
    _validar_horario_sitio(datos)
    _validar_precio_sitio(datos)


def _validar_ubicacion_catalogo(db: Session, datos: SitioCreate) -> None:
    if datos.id_parroquia:
        _validar_parroquia(db, datos.id_parroquia)
    if datos.id_plataforma:
        if not datos.id_parroquia:
            raise _bad_request("Debe enviar parroquia si envia plataforma")
        _validar_plataforma(db, datos.id_plataforma, datos.id_parroquia)


def _validar_categoria_subcategoria(db: Session, datos: SitioCreate) -> None:
    if not _existe_categoria(db, datos.id_categoria):
        raise _not_found("La categoria no existe")

    if not _existe_subcategoria(
        db,
        datos.id_subcategoria,
        datos.id_categoria,
    ):
        raise _bad_request("La subcategoria no pertenece a la categoria enviada")


def _validar_horario_sitio(datos: SitioCreate) -> None:
    tiene_comentario = bool((datos.horario.comentario or "").strip())

    for day in datos.horario.dias_semana:
        if day < 1 or day > 7:
            raise _bad_request("Los dias de atencion deben estar entre 1 y 7")

    if not datos.horario.dias_semana and datos.horario.detalles:
        raise _bad_request("No puede enviar detalles de horario sin dias de atencion")

    for detalle in datos.horario.detalles:
        if detalle.dia_semana not in datos.horario.dias_semana:
            raise _bad_request(
                "Cada detalle de horario debe corresponder a un dia listado en dias_semana"
            )
        if not datos.horario.abierto_24h and not detalle.cerrado:
            if not detalle.hora_inicio or not detalle.hora_fin:
                raise _bad_request(
                    "Debe enviar hora_inicio y hora_fin en cada detalle no cerrado"
                )
            if detalle.hora_inicio >= detalle.hora_fin:
                raise _bad_request("hora_inicio debe ser menor que hora_fin en el detalle")

    if not datos.horario.dias_semana and (datos.horario.abierto_24h or tiene_comentario):
        return

    if not datos.horario.dias_semana:
        raise _bad_request("Debe enviar dias de atencion, activar 24 horas o agregar un comentario de horario")

    if not datos.horario.abierto_24h and not datos.horario.detalles:
        if not datos.horario.hora_inicio or not datos.horario.hora_fin:
            raise _bad_request("Debe enviar hora_inicio y hora_fin si no esta abierto 24 horas")

        if datos.horario.hora_inicio >= datos.horario.hora_fin:
            raise _bad_request("hora_inicio debe ser menor que hora_fin")


def _validar_precio_sitio(datos: SitioCreate) -> None:
    if datos.precio.es_gratuito:
        if datos.precio.precio_min is not None or datos.precio.precio_max is not None:
            raise _bad_request("Un sitio gratuito no debe enviar rango de precio")
        if datos.precio.tarifa_acceso is not None or datos.precio.condicion_tarifa is not None:
            raise _bad_request("Un sitio gratuito no debe enviar tarifa de acceso")
        return

    tiene_rango = (
        datos.precio.precio_min is not None or datos.precio.precio_max is not None
    )
    tiene_tarifa = datos.precio.tarifa_acceso is not None

    if tiene_rango and tiene_tarifa:
        raise _bad_request(
            "Rango de precio y tarifa de acceso son excluyentes: envie solo uno"
        )

    if not tiene_rango and not tiene_tarifa:
        raise _bad_request(
            "Debe enviar un rango de precio o una tarifa de acceso para sitios pagados"
        )

    if tiene_rango:
        if datos.precio.precio_min is None or datos.precio.precio_max is None:
            raise _bad_request("Debe enviar precio_min y precio_max para sitios con rango")
        if datos.precio.precio_min > datos.precio.precio_max:
            raise _bad_request("precio_min no puede ser mayor que precio_max")

    if tiene_tarifa and datos.precio.tarifa_acceso is not None and datos.precio.tarifa_acceso < 0:
        raise _bad_request("tarifa_acceso no puede ser negativo")


def listar_categorias(db: Session, incluir_inactivas: bool = False) -> list[CategoriaResponse]:
    filtro = "" if incluir_inactivas else "WHERE activo = TRUE"
    rows = db.execute(
        text(
            f"""
            SELECT id_categoria, nombre, activo
            FROM turismo.categoria
            {filtro}
            ORDER BY nombre ASC
            """
        )
    ).mappings().all()
    return [CategoriaResponse(**dict(row)) for row in rows]


def listar_categorias_detalle(
    db: Session,
    incluir_inactivas: bool = True,
) -> list[CategoriaDetalleResponse]:
    categoria_filter = "" if incluir_inactivas else "WHERE c.activo = TRUE"
    subcategoria_filter = "" if incluir_inactivas else "AND sc.activo = TRUE"

    categorias = db.execute(
        text(
            f"""
            SELECT
                c.id_categoria,
                c.nombre,
                c.activo,
                COUNT(DISTINCT s.id_sitio)::INT AS total_atractivos,
                COUNT(DISTINCT sc.id_subcategoria)::INT AS total_subcategorias
            FROM turismo.categoria c
            LEFT JOIN turismo.sitio s ON s.id_categoria = c.id_categoria
            LEFT JOIN turismo.subcategoria sc
                ON sc.id_categoria = c.id_categoria
                {subcategoria_filter}
            {categoria_filter}
            GROUP BY c.id_categoria, c.nombre, c.activo
            ORDER BY c.nombre ASC
            """
        )
    ).mappings().all()

    subcategorias = db.execute(
        text(
            f"""
            SELECT
                sc.id_subcategoria,
                sc.id_categoria,
                sc.nombre,
                sc.activo,
                COUNT(s.id_sitio)::INT AS total_atractivos
            FROM turismo.subcategoria sc
            LEFT JOIN turismo.sitio s ON s.id_subcategoria = sc.id_subcategoria
            WHERE (:incluir_inactivas = TRUE OR sc.activo = TRUE)
            GROUP BY sc.id_subcategoria, sc.id_categoria, sc.nombre, sc.activo
            ORDER BY sc.nombre ASC
            """
        ),
        {"incluir_inactivas": incluir_inactivas},
    ).mappings().all()

    subcategorias_por_categoria: dict[int, list[SubcategoriaDetalleResponse]] = {}
    for row in subcategorias:
        item = SubcategoriaDetalleResponse(**dict(row))
        subcategorias_por_categoria.setdefault(item.id_categoria, []).append(item)

    return [
        CategoriaDetalleResponse(
            **dict(row),
            subcategorias=subcategorias_por_categoria.get(row["id_categoria"], []),
        )
        for row in categorias
    ]


def crear_categoria(
    db: Session,
    datos: CategoriaCreate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> CategoriaResponse:
    existe = db.execute(
        text("SELECT 1 FROM turismo.categoria WHERE lower(nombre) = lower(:nombre)"),
        {"nombre": datos.nombre},
    ).first()
    if existe:
        raise _conflict("La categoria ya existe")

    row = db.execute(
        text(
            """
            INSERT INTO turismo.categoria (nombre, activo)
            VALUES (:nombre, :activo)
            RETURNING id_categoria, nombre, activo
            """
        ),
        {"nombre": datos.nombre, "activo": datos.activo},
    ).mappings().one()
    fila = dict(row)
    _trazar(
        db,
        actor,
        "INSERT",
        "categoria",
        fila["id_categoria"],
        nuevo=fila,
    )
    db.commit()
    return CategoriaResponse(**fila)


def actualizar_categoria(
    db: Session,
    id_categoria: int,
    datos: CategoriaUpdate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> CategoriaResponse:
    if not _existe_categoria(db, id_categoria):
        raise _not_found("La categoria no existe")

    anterior = db.execute(
        text("SELECT id_categoria, nombre, activo FROM turismo.categoria WHERE id_categoria = :id_categoria"),
        {"id_categoria": id_categoria},
    ).mappings().first()

    update_data = datos.model_dump(exclude_unset=True) if hasattr(datos, "model_dump") else datos.dict(exclude_unset=True)
    if not update_data:
        raise _bad_request("Debe enviar al menos un campo para actualizar")

    if "nombre" in update_data:
        existe = db.execute(
            text(
                """
                SELECT 1
                FROM turismo.categoria
                WHERE lower(nombre) = lower(:nombre)
                  AND id_categoria <> :id_categoria
                """
            ),
            {"nombre": update_data["nombre"], "id_categoria": id_categoria},
        ).first()
        if existe:
            raise _conflict("La categoria ya existe")

    set_sql = ", ".join(f"{key} = :{key}" for key in update_data)
    row = db.execute(
        text(
            f"""
            UPDATE turismo.categoria
            SET {set_sql}
            WHERE id_categoria = :id_categoria
            RETURNING id_categoria, nombre, activo
            """
        ),
        {**update_data, "id_categoria": id_categoria},
    ).mappings().one()
    fila = dict(row)
    _trazar(
        db,
        actor,
        "UPDATE",
        "categoria",
        id_categoria,
        anterior=dict(anterior) if anterior else None,
        nuevo=fila,
        referencia=fila["nombre"],
    )
    db.commit()
    return CategoriaResponse(**fila)


def eliminar_categoria(
    db: Session,
    id_categoria: int,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> CategoriaResponse:
    row = db.execute(
        text("SELECT id_categoria, nombre, activo FROM turismo.categoria WHERE id_categoria = :id_categoria"),
        {"id_categoria": id_categoria},
    ).mappings().first()
    if not row:
        raise _not_found("La categoria no existe")

    urls = [
        item["url"]
        for item in db.execute(
            text(
                """
                SELECT m.url
                FROM turismo.multimedia m
                JOIN turismo.sitio s ON s.id_sitio = m.id_sitio
                WHERE s.id_categoria = :id_categoria
                """
            ),
            {"id_categoria": id_categoria},
        ).mappings().all()
    ]
    sitio_ids = [
        int(item["id_sitio"])
        for item in db.execute(
            text("SELECT id_sitio FROM turismo.sitio WHERE id_categoria = :id_categoria"),
            {"id_categoria": id_categoria},
        ).mappings().all()
    ]
    repo_paths = []
    for id_sitio in sitio_ids:
        repo_paths.extend(eliminar_repositorios_de_vinculo(db, "sitio", id_sitio))
    db.execute(
        text(
            """
            DELETE FROM gis.ruta_puntos
            WHERE id_sitio IN (
                SELECT id_sitio FROM turismo.sitio WHERE id_categoria = :id_categoria
            )
            """
        ),
        {"id_categoria": id_categoria},
    )
    db.execute(text("DELETE FROM turismo.sitio WHERE id_categoria = :id_categoria"), {"id_categoria": id_categoria})
    db.execute(text("DELETE FROM turismo.subcategoria WHERE id_categoria = :id_categoria"), {"id_categoria": id_categoria})
    db.execute(text("DELETE FROM turismo.categoria WHERE id_categoria = :id_categoria"), {"id_categoria": id_categoria})
    _trazar(
        db,
        actor,
        "DELETE",
        "categoria",
        id_categoria,
        anterior=dict(row),
        referencia=row["nombre"],
    )
    db.commit()
    _eliminar_archivos_locales(urls)
    eliminar_directorios_repositorio(repo_paths)
    return CategoriaResponse(id_categoria=row["id_categoria"], nombre=row["nombre"], activo=False)


def desactivar_categoria(db: Session, id_categoria: int) -> CategoriaResponse:
    if not _existe_categoria(db, id_categoria):
        raise _not_found("La categoria no existe")

    row = db.execute(
        text(
            """
            UPDATE turismo.categoria
            SET activo = FALSE
            WHERE id_categoria = :id_categoria
            RETURNING id_categoria, nombre, activo
            """
        ),
        {"id_categoria": id_categoria},
    ).mappings().one()
    db.execute(
        text(
            """
            UPDATE turismo.subcategoria
            SET activo = FALSE
            WHERE id_categoria = :id_categoria
            """
        ),
        {"id_categoria": id_categoria},
    )
    db.commit()
    return CategoriaResponse(**dict(row))


def cambiar_estado_categoria(db: Session, id_categoria: int, activo: bool, actor: ActorTrazabilidad = ACTOR_SISTEMA) -> CategoriaResponse:
    anterior = db.execute(
        text("SELECT id_categoria, nombre, activo FROM turismo.categoria WHERE id_categoria = :id_categoria"),
        {"id_categoria": id_categoria},
    ).mappings().first()
    if not anterior:
        raise _not_found("La categoria no existe")
    row = db.execute(
        text(
            """
            UPDATE turismo.categoria
            SET activo = :activo
            WHERE id_categoria = :id_categoria
            RETURNING id_categoria, nombre, activo
            """
        ),
        {"id_categoria": id_categoria, "activo": activo},
    ).mappings().first()
    fila = dict(row)
    _trazar(
        db,
        actor,
        "UPDATE",
        "categoria",
        id_categoria,
        anterior=dict(anterior),
        nuevo=fila,
        referencia=fila["nombre"],
    )
    db.commit()
    return CategoriaResponse(**fila)


def listar_subcategorias(
    db: Session,
    id_categoria: int | None = None,
    incluir_inactivas: bool = False,
) -> list[SubcategoriaResponse]:
    params: dict[str, Any] = {}
    filtros = []

    if id_categoria:
        filtros.append("id_categoria = :id_categoria")
        params["id_categoria"] = id_categoria

    if not incluir_inactivas:
        filtros.append("activo = TRUE")

    where_sql = f"WHERE {' AND '.join(filtros)}" if filtros else ""

    rows = db.execute(
        text(
            f"""
            SELECT id_subcategoria, id_categoria, nombre, activo
            FROM turismo.subcategoria
            {where_sql}
            ORDER BY nombre ASC
            """
        ),
        params,
    ).mappings().all()
    return [SubcategoriaResponse(**dict(row)) for row in rows]


def crear_subcategoria(db: Session, datos: SubcategoriaCreate, actor: ActorTrazabilidad = ACTOR_SISTEMA) -> SubcategoriaResponse:
    if not _existe_categoria(db, datos.id_categoria):
        raise _not_found("La categoria no existe")

    existe = db.execute(
        text(
            """
            SELECT 1
            FROM turismo.subcategoria
            WHERE id_categoria = :id_categoria
              AND lower(nombre) = lower(:nombre)
            """
        ),
        {"id_categoria": datos.id_categoria, "nombre": datos.nombre},
    ).first()
    if existe:
        raise _conflict("La subcategoria ya existe para esta categoria")

    row = db.execute(
        text(
            """
            INSERT INTO turismo.subcategoria (id_categoria, nombre, activo)
            VALUES (:id_categoria, :nombre, :activo)
            RETURNING id_subcategoria, id_categoria, nombre, activo
            """
        ),
        {
            "id_categoria": datos.id_categoria,
            "nombre": datos.nombre,
            "activo": datos.activo,
        },
    ).mappings().one()
    fila = dict(row)
    _trazar(db, actor, "INSERT", "subcategoria", fila["id_subcategoria"], nuevo=fila)
    db.commit()
    return SubcategoriaResponse(**fila)


def actualizar_subcategoria(
    db: Session,
    id_subcategoria: int,
    datos: SubcategoriaUpdate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> SubcategoriaResponse:
    actual = db.execute(
        text(
            """
            SELECT id_subcategoria, id_categoria, nombre, activo
            FROM turismo.subcategoria
            WHERE id_subcategoria = :id_subcategoria
            """
        ),
        {"id_subcategoria": id_subcategoria},
    ).mappings().first()
    if not actual:
        raise _not_found("La subcategoria no existe")

    update_data = datos.model_dump(exclude_unset=True) if hasattr(datos, "model_dump") else datos.dict(exclude_unset=True)
    if not update_data:
        raise _bad_request("Debe enviar al menos un campo para actualizar")

    id_categoria = update_data.get("id_categoria", actual["id_categoria"])
    if not _existe_categoria(db, id_categoria):
        raise _not_found("La categoria no existe")

    nombre = update_data.get("nombre", actual["nombre"])
    existe = db.execute(
        text(
            """
            SELECT 1
            FROM turismo.subcategoria
            WHERE id_categoria = :id_categoria
              AND lower(nombre) = lower(:nombre)
              AND id_subcategoria <> :id_subcategoria
            """
        ),
        {
            "id_categoria": id_categoria,
            "nombre": nombre,
            "id_subcategoria": id_subcategoria,
        },
    ).first()
    if existe:
        raise _conflict("La subcategoria ya existe para esta categoria")

    set_sql = ", ".join(f"{key} = :{key}" for key in update_data)
    row = db.execute(
        text(
            f"""
            UPDATE turismo.subcategoria
            SET {set_sql}
            WHERE id_subcategoria = :id_subcategoria
            RETURNING id_subcategoria, id_categoria, nombre, activo
            """
        ),
        {**update_data, "id_subcategoria": id_subcategoria},
    ).mappings().one()
    fila = dict(row)
    _trazar(
        db,
        actor,
        "UPDATE",
        "subcategoria",
        id_subcategoria,
        anterior=dict(actual),
        nuevo=fila,
        referencia=fila["nombre"],
    )
    db.commit()
    return SubcategoriaResponse(**fila)


def eliminar_subcategoria(db: Session, id_subcategoria: int, actor: ActorTrazabilidad = ACTOR_SISTEMA) -> SubcategoriaResponse:
    row = db.execute(
        text("SELECT id_subcategoria, id_categoria, nombre, activo FROM turismo.subcategoria WHERE id_subcategoria = :id_subcategoria"),
        {"id_subcategoria": id_subcategoria},
    ).mappings().first()
    if not row:
        raise _not_found("La subcategoria no existe")

    urls = [
        item["url"]
        for item in db.execute(
            text(
                """
                SELECT m.url
                FROM turismo.multimedia m
                JOIN turismo.sitio s ON s.id_sitio = m.id_sitio
                WHERE s.id_subcategoria = :id_subcategoria
                """
            ),
            {"id_subcategoria": id_subcategoria},
        ).mappings().all()
    ]
    sitio_ids = [
        int(item["id_sitio"])
        for item in db.execute(
            text("SELECT id_sitio FROM turismo.sitio WHERE id_subcategoria = :id_subcategoria"),
            {"id_subcategoria": id_subcategoria},
        ).mappings().all()
    ]
    repo_paths = []
    for id_sitio in sitio_ids:
        repo_paths.extend(eliminar_repositorios_de_vinculo(db, "sitio", id_sitio))
    db.execute(
        text(
            """
            DELETE FROM gis.ruta_puntos
            WHERE id_sitio IN (
                SELECT id_sitio FROM turismo.sitio WHERE id_subcategoria = :id_subcategoria
            )
            """
        ),
        {"id_subcategoria": id_subcategoria},
    )
    db.execute(text("DELETE FROM turismo.sitio WHERE id_subcategoria = :id_subcategoria"), {"id_subcategoria": id_subcategoria})
    db.execute(text("DELETE FROM turismo.subcategoria WHERE id_subcategoria = :id_subcategoria"), {"id_subcategoria": id_subcategoria})
    _trazar(
        db,
        actor,
        "DELETE",
        "subcategoria",
        id_subcategoria,
        anterior=dict(row),
        referencia=row["nombre"],
    )
    db.commit()
    _eliminar_archivos_locales(urls)
    eliminar_directorios_repositorio(repo_paths)
    return SubcategoriaResponse(
        id_subcategoria=row["id_subcategoria"],
        id_categoria=row["id_categoria"],
        nombre=row["nombre"],
        activo=False,
    )


def cambiar_estado_subcategoria(
    db: Session,
    id_subcategoria: int,
    activo: bool,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> SubcategoriaResponse:
    anterior = db.execute(
        text("SELECT id_subcategoria, id_categoria, nombre, activo FROM turismo.subcategoria WHERE id_subcategoria = :id_subcategoria"),
        {"id_subcategoria": id_subcategoria},
    ).mappings().first()
    if not anterior:
        raise _not_found("La subcategoria no existe")
    row = db.execute(
        text(
            """
            UPDATE turismo.subcategoria
            SET activo = :activo
            WHERE id_subcategoria = :id_subcategoria
            RETURNING id_subcategoria, id_categoria, nombre, activo
            """
        ),
        {"id_subcategoria": id_subcategoria, "activo": activo},
    ).mappings().first()
    fila = dict(row)
    _trazar(
        db,
        actor,
        "UPDATE",
        "subcategoria",
        id_subcategoria,
        anterior=dict(anterior),
        nuevo=fila,
        referencia=fila["nombre"],
    )
    db.commit()
    return SubcategoriaResponse(**fila)


def listar_parroquias(db: Session) -> list[CatalogoSimpleResponse]:
    rows = db.execute(
        text(
            """
            SELECT id_parroquia AS id, nombre, activo, NULL::INT AS id_parroquia
            FROM turismo.parroquia
            WHERE activo = TRUE
            ORDER BY nombre ASC
            """
        )
    ).mappings().all()
    return [CatalogoSimpleResponse(**dict(row)) for row in rows]


def listar_plataformas(db: Session, id_parroquia: int | None = None) -> list[CatalogoSimpleResponse]:
    params: dict[str, Any] = {}
    filtro = "WHERE activo = TRUE"

    if id_parroquia:
        filtro += " AND id_parroquia = :id_parroquia"
        params["id_parroquia"] = id_parroquia

    rows = db.execute(
        text(
            f"""
            SELECT id_plataforma AS id, nombre, activo, id_parroquia
            FROM turismo.plataforma
            {filtro}
            ORDER BY nombre ASC
            """
        ),
        params,
    ).mappings().all()
    return [CatalogoSimpleResponse(**dict(row)) for row in rows]


def guardar_imagenes(nombre_sitio: str, archivos: list[UploadFile]) -> list[ImagenSubidaResponse]:
    if not archivos:
        raise _bad_request("Debe enviar al menos una imagen")

    site_dir = IMAGES_DIR / _slugify(nombre_sitio)
    site_dir.mkdir(parents=True, exist_ok=True)

    response: list[ImagenSubidaResponse] = []
    for archivo in archivos:
        content_type = archivo.content_type or ""
        if not content_type.startswith("image/"):
            raise _bad_request("Solo se permiten archivos de imagen")

        suffix = Path(archivo.filename or "").suffix.lower() or ".jpg"
        filename = f"{uuid4().hex}{suffix}"
        destination = site_dir / filename

        with destination.open("wb") as buffer:
            shutil.copyfileobj(archivo.file, buffer)

        response.append(
            ImagenSubidaResponse(
                nombre_archivo=filename,
                url=f"{IMAGE_URL_PREFIX}/{site_dir.name}/{filename}",
            )
        )

    return response


def listar_sitios(
    db: Session,
    q: str | None,
    id_categoria: int | None,
    id_subcategoria: int | None,
    estado: EstadoAtractivo,
    servicio: ServicioFiltro,
    precio: PrecioFiltro,
    page: int,
    page_size: int,
    usuario: dict | None = None,
) -> SitiosListResponse:
    params: dict[str, Any] = {}
    filtros = []

    if usuario is not None:
        sitios_permitidos = obtener_sitios_permitidos(db, usuario, "attractions", "ver")
        filtro_sql, filtro_params = aplicar_filtro_sitios_sql(sitios_permitidos)
        if filtro_sql:
            filtros.append(filtro_sql.removeprefix(" AND "))
            params.update(filtro_params)

    if q:
        filtros.append("s.nombre ILIKE :q")
        params["q"] = f"%{q.strip()}%"

    if id_categoria:
        filtros.append("s.id_categoria = :id_categoria")
        params["id_categoria"] = id_categoria

    if id_subcategoria:
        filtros.append("s.id_subcategoria = :id_subcategoria")
        params["id_subcategoria"] = id_subcategoria

    if estado == "activo":
        filtros.append("s.activo = TRUE")
    elif estado == "inactivo":
        filtros.append("s.activo = FALSE")

    servicio_columnas = {
        "wifi": "s.tiene_wifi",
        "parqueadero": "s.parqueadero",
        "mascotas": "s.permite_mascotas",
        "accesibilidad": "s.accesibilidad",
    }
    if servicio != "all":
        filtros.append(f"{servicio_columnas[servicio]} = TRUE")

    if precio == "gratis":
        filtros.append("s.es_gratuito = TRUE")
    elif precio == "pagado":
        filtros.append("s.es_gratuito = FALSE")

    where_sql = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size

    total = int(
        db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM turismo.sitio s
                {where_sql}
                """
            ),
            params,
        ).scalar()
        or 0
    )

    rows = db.execute(
        text(
            f"""
            {_sitio_select_sql()}
            {where_sql}
            ORDER BY s.nombre ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    return SitiosListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[_sitio_response(dict(row)) for row in rows],
    )


def obtener_sitio(db: Session, id_sitio: int) -> SitioResponse:
    row = db.execute(
        text(
            f"""
            {_sitio_select_sql()}
            WHERE s.id_sitio = :id_sitio
            """
        ),
        {"id_sitio": id_sitio},
    ).mappings().first()

    if not row:
        raise _not_found("El atractivo turistico no existe")

    return _sitio_response(dict(row))


def obtener_sitio_detalle(
    db: Session,
    id_sitio: int,
    usuario: dict | None = None,
) -> SitioDetalleResponse:
    if usuario is not None:
        validar_acceso_sitio(db, usuario, id_sitio, "attractions", "ver")
    row = db.execute(
        text(
            """
            SELECT
                s.id_sitio,
                s.id_parroquia,
                s.id_plataforma,
                s.id_categoria,
                c.nombre AS categoria,
                s.id_subcategoria,
                sc.nombre AS subcategoria,
                s.tipo::TEXT AS tipo,
                s.nombre,
                s.descripcion_corta,
                s.permite_mascotas,
                s.parqueadero,
                s.tiene_wifi,
                s.accesibilidad,
                s.activo,
                ST_Y(s.ubicacion::geometry) AS latitud,
                ST_X(s.ubicacion::geometry) AS longitud,
                d.direccion_texto,
                d.referencia_adicional,
                m.url AS imagen_url
            FROM turismo.sitio s
            JOIN turismo.categoria c ON c.id_categoria = s.id_categoria
            LEFT JOIN turismo.subcategoria sc ON sc.id_subcategoria = s.id_subcategoria
            LEFT JOIN turismo.direccion d ON d.id_sitio = s.id_sitio
            LEFT JOIN LATERAL (
                SELECT url
                FROM turismo.multimedia
                WHERE id_sitio = s.id_sitio AND activo = TRUE
                ORDER BY es_principal DESC, id_multimedia ASC
                LIMIT 1
            ) m ON TRUE
            WHERE s.id_sitio = :id_sitio
            """
        ),
        {"id_sitio": id_sitio},
    ).mappings().first()
    if not row:
        raise _not_found("El atractivo turistico no existe")

    contactos = db.execute(
        text(
            """
            SELECT nombre::TEXT AS nombre, contenido
            FROM turismo.contacto
            WHERE id_sitio = :id_sitio AND activo = TRUE
            ORDER BY id_contacto ASC
            """
        ),
        {"id_sitio": id_sitio},
    ).mappings().all()

    multimedia = db.execute(
        text(
            """
            SELECT url, es_principal
            FROM turismo.multimedia
            WHERE id_sitio = :id_sitio AND activo = TRUE
            ORDER BY es_principal DESC, id_multimedia ASC
            """
        ),
        {"id_sitio": id_sitio},
    ).mappings().all()

    horario_row = db.execute(
        text(
            """
            SELECT id_horario, abierto_24h, comentario
            FROM turismo.horario
            WHERE id_sitio = :id_sitio AND activo = TRUE
            ORDER BY id_horario DESC
            LIMIT 1
            """
        ),
        {"id_sitio": id_sitio},
    ).mappings().first()

    dias_semana: list[int] = []
    hora_inicio = None
    hora_fin = None
    abierto_24h = False
    detalles_response: list[dict] = []
    if horario_row:
        abierto_24h = bool(horario_row["abierto_24h"])
        detalles = db.execute(
            text(
                """
                SELECT dia_semana::INT AS dia_semana,
                       to_char(hora_inicio, 'HH24:MI') AS hora_inicio,
                       to_char(hora_fin, 'HH24:MI') AS hora_fin
                FROM turismo.horario_detalle
                WHERE id_horario = :id_horario AND activo = TRUE
                ORDER BY dia_semana ASC
                """
            ),
            {"id_horario": horario_row["id_horario"]},
        ).mappings().all()
        dias_con_detalle = {int(item["dia_semana"]) for item in detalles}
        detalles_response = [
            {
                "dia_semana": int(item["dia_semana"]),
                "cerrado": False,
                "hora_inicio": item["hora_inicio"],
                "hora_fin": item["hora_fin"],
            }
            for item in detalles
        ]
        if abierto_24h:
            dias_semana = sorted(dias_con_detalle)
        else:
            dias_semana = sorted(dias_con_detalle)
            if detalles and not abierto_24h:
                hora_inicio = detalles[0]["hora_inicio"]
                hora_fin = detalles[0]["hora_fin"]

    precio_row = db.execute(
        text(
            """
            SELECT
                s.es_gratuito,
                rp.precio_min,
                rp.precio_max,
                COALESCE(rp.etiqueta_precio::TEXT, 'desconocido') AS etiqueta_precio,
                ta.precio AS tarifa_acceso,
                ta.condicion AS condicion_tarifa
            FROM turismo.sitio s
            LEFT JOIN LATERAL (
                SELECT precio_min, precio_max, etiqueta_precio
                FROM turismo.rango_precio
                WHERE id_sitio = s.id_sitio AND activo = TRUE
                ORDER BY id_rango_precio DESC
                LIMIT 1
            ) rp ON TRUE
            LEFT JOIN LATERAL (
                SELECT precio, condicion
                FROM turismo.tarifa_acceso
                WHERE id_sitio = s.id_sitio AND activo = TRUE
                ORDER BY id_tarifa_acceso DESC
                LIMIT 1
            ) ta ON TRUE
            WHERE s.id_sitio = :id_sitio
            """
        ),
        {"id_sitio": id_sitio},
    ).mappings().one()

    data = dict(row)
    return SitioDetalleResponse(
        id_sitio=data["id_sitio"],
        id_parroquia=data["id_parroquia"],
        id_plataforma=data["id_plataforma"],
        id_categoria=data["id_categoria"],
        categoria=data["categoria"],
        id_subcategoria=data["id_subcategoria"],
        subcategoria=data["subcategoria"],
        tipo=data["tipo"],
        nombre=data["nombre"],
        descripcion_corta=data["descripcion_corta"],
        permite_mascotas=data["permite_mascotas"],
        parqueadero=data["parqueadero"],
        tiene_wifi=data["tiene_wifi"],
        accesibilidad=data["accesibilidad"],
        activo=data["activo"],
        imagen_url=data["imagen_url"],
        direccion={
            "direccion_texto": data["direccion_texto"] or "",
            "referencia_adicional": data["referencia_adicional"],
            "latitud": data["latitud"],
            "longitud": data["longitud"],
        },
        horario={
            "abierto_24h": abierto_24h,
            "dias_semana": dias_semana,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "comentario": horario_row["comentario"] if horario_row else None,
            "detalles": detalles_response,
        },
        contactos=[dict(item) for item in contactos],
        multimedia=[dict(item) for item in multimedia],
        precio=dict(precio_row),
    )


def crear_sitio(
    db: Session,
    datos: SitioCreate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> SitioResponse:
    _validar_catalogos_sitio(db, datos)
    params = datos.model_dump() if hasattr(datos, "model_dump") else datos.dict()
    params["es_gratuito"] = datos.precio.es_gratuito

    row = db.execute(
        text(
            """
            INSERT INTO turismo.sitio (
                id_parroquia,
                id_plataforma,
                id_categoria,
                id_subcategoria,
                tipo,
                nombre,
                descripcion_corta,
                ubicacion,
                es_gratuito,
                permite_mascotas,
                parqueadero,
                tiene_wifi,
                accesibilidad,
                activo
            )
            VALUES (
                :id_parroquia,
                :id_plataforma,
                :id_categoria,
                :id_subcategoria,
                :tipo,
                :nombre,
                :descripcion_corta,
                ST_SetSRID(ST_MakePoint(:longitud, :latitud), 4326)::geography,
                :es_gratuito,
                :permite_mascotas,
                :parqueadero,
                :tiene_wifi,
                :accesibilidad,
                :activo
            )
            RETURNING id_sitio
            """
        ),
        params,
    ).mappings().one()

    id_sitio = int(row["id_sitio"])

    db.execute(
        text(
            """
            INSERT INTO turismo.direccion (
                id_sitio,
                direccion_texto,
                referencia_adicional
            )
            VALUES (:id_sitio, :direccion_texto, :referencia_adicional)
            """
        ),
        {
            "id_sitio": id_sitio,
            "direccion_texto": datos.direccion_texto,
            "referencia_adicional": datos.referencia_adicional,
        },
    )

    principal_asignado = any(item.es_principal for item in datos.multimedia)
    for index, imagen in enumerate(datos.multimedia):
        db.execute(
            text(
                """
                INSERT INTO turismo.multimedia (id_sitio, url, es_principal, activo)
                VALUES (:id_sitio, :url, :es_principal, TRUE)
                """
            ),
            {
                "id_sitio": id_sitio,
                "url": imagen.url,
                "es_principal": imagen.es_principal or (not principal_asignado and index == 0),
            },
        )

    horario = db.execute(
        text(
            """
            INSERT INTO turismo.horario (id_sitio, abierto_24h, comentario, activo)
            VALUES (:id_sitio, :abierto_24h, :comentario, TRUE)
            RETURNING id_horario
            """
        ),
        {
            "id_sitio": id_sitio,
            "abierto_24h": datos.horario.abierto_24h,
            "comentario": (datos.horario.comentario or "").strip() or None,
        },
    ).mappings().one()

    for dia, h_ini, h_fin in _resolver_detalles_horario(datos.horario):
        db.execute(
            text(
                """
                INSERT INTO turismo.horario_detalle (
                    id_horario,
                    dia_semana,
                    hora_inicio,
                    hora_fin,
                    activo
                )
                VALUES (:id_horario, :dia_semana, :hora_inicio, :hora_fin, TRUE)
                """
            ),
            {
                "id_horario": horario["id_horario"],
                "dia_semana": dia,
                "hora_inicio": h_ini,
                "hora_fin": h_fin,
            },
        )

    for contacto in datos.contactos:
        db.execute(
            text(
                """
                INSERT INTO turismo.contacto (id_sitio, nombre, contenido, activo)
                VALUES (:id_sitio, :nombre, :contenido, TRUE)
                """
            ),
            {
                "id_sitio": id_sitio,
                "nombre": contacto.nombre,
                "contenido": contacto.contenido,
            },
        )

    if not datos.precio.es_gratuito:
        tiene_rango = (
            datos.precio.precio_min is not None
            and datos.precio.precio_max is not None
        )
        if tiene_rango:
            db.execute(
                text(
                    """
                    INSERT INTO turismo.rango_precio (
                        id_sitio,
                        precio_min,
                        precio_max,
                        etiqueta_precio,
                        activo
                    )
                    VALUES (
                        :id_sitio,
                        :precio_min,
                        :precio_max,
                        :etiqueta_precio,
                        TRUE
                    )
                    """
                ),
                {
                    "id_sitio": id_sitio,
                    "precio_min": datos.precio.precio_min,
                    "precio_max": datos.precio.precio_max,
                    "etiqueta_precio": datos.precio.etiqueta_precio,
                },
            )

        if datos.precio.tarifa_acceso is not None:
            db.execute(
                text(
                    """
                    INSERT INTO turismo.tarifa_acceso (
                        id_sitio,
                        precio,
                        condicion,
                        activo
                    )
                    VALUES (:id_sitio, :precio, :condicion, TRUE)
                    """
                ),
                {
                    "id_sitio": id_sitio,
                    "precio": datos.precio.tarifa_acceso,
                    "condicion": datos.precio.condicion_tarifa,
                },
            )

    _trazar(
        db,
        actor,
        "INSERT",
        "sitio",
        id_sitio,
        nuevo={"id_sitio": id_sitio, "nombre": datos.nombre, "tipo": datos.tipo},
    )
    regenerar_chunk_descripcion(db, "sitio", id_sitio)
    db.commit()
    return obtener_sitio(db, id_sitio)


def actualizar_sitio(
    db: Session,
    id_sitio: int,
    datos: SitioCreate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
    usuario: dict | None = None,
) -> SitioResponse:
    if usuario is not None:
        validar_acceso_sitio(db, usuario, id_sitio, "attractions", "actualizar")
    if db.execute(text("SELECT 1 FROM turismo.sitio WHERE id_sitio = :id_sitio"), {"id_sitio": id_sitio}).first() is None:
        raise _not_found("El atractivo turistico no existe")

    sitio_anterior = obtener_sitio(db, id_sitio).model_dump(mode="json")
    _validar_catalogos_sitio(db, datos)
    urls_anteriores = [
        row["url"]
        for row in db.execute(
            text("SELECT url FROM turismo.multimedia WHERE id_sitio = :id_sitio"),
            {"id_sitio": id_sitio},
        ).mappings().all()
    ]
    urls_nuevas = [item.url for item in datos.multimedia]

    params = datos.model_dump() if hasattr(datos, "model_dump") else datos.dict()
    params.update(
        {
            "id_sitio": id_sitio,
            "es_gratuito": datos.precio.es_gratuito,
        }
    )

    db.execute(
        text(
            """
            UPDATE turismo.sitio
            SET id_parroquia = :id_parroquia,
                id_plataforma = :id_plataforma,
                id_categoria = :id_categoria,
                id_subcategoria = :id_subcategoria,
                tipo = :tipo,
                nombre = :nombre,
                descripcion_corta = :descripcion_corta,
                ubicacion = ST_SetSRID(ST_MakePoint(:longitud, :latitud), 4326)::geography,
                es_gratuito = :es_gratuito,
                permite_mascotas = :permite_mascotas,
                parqueadero = :parqueadero,
                tiene_wifi = :tiene_wifi,
                accesibilidad = :accesibilidad,
                activo = :activo
            WHERE id_sitio = :id_sitio
            """
        ),
        params,
    )

    db.execute(
        text(
            """
            INSERT INTO turismo.direccion (id_sitio, direccion_texto, referencia_adicional)
            VALUES (:id_sitio, :direccion_texto, :referencia_adicional)
            ON CONFLICT (id_sitio)
            DO UPDATE SET direccion_texto = EXCLUDED.direccion_texto,
                          referencia_adicional = EXCLUDED.referencia_adicional
            """
        ),
        {
            "id_sitio": id_sitio,
            "direccion_texto": datos.direccion_texto,
            "referencia_adicional": datos.referencia_adicional,
        },
    )

    db.execute(text("DELETE FROM turismo.multimedia WHERE id_sitio = :id_sitio"), {"id_sitio": id_sitio})
    principal_asignado = any(item.es_principal for item in datos.multimedia)
    for index, imagen in enumerate(datos.multimedia):
        db.execute(
            text("INSERT INTO turismo.multimedia (id_sitio, url, es_principal, activo) VALUES (:id_sitio, :url, :es_principal, TRUE)"),
            {
                "id_sitio": id_sitio,
                "url": imagen.url,
                "es_principal": imagen.es_principal or (not principal_asignado and index == 0),
            },
        )

    db.execute(text("DELETE FROM turismo.contacto WHERE id_sitio = :id_sitio"), {"id_sitio": id_sitio})
    for contacto in datos.contactos:
        db.execute(
            text("INSERT INTO turismo.contacto (id_sitio, nombre, contenido, activo) VALUES (:id_sitio, :nombre, :contenido, TRUE)"),
            {"id_sitio": id_sitio, "nombre": contacto.nombre, "contenido": contacto.contenido},
        )

    db.execute(text("DELETE FROM turismo.horario WHERE id_sitio = :id_sitio"), {"id_sitio": id_sitio})
    horario = db.execute(
        text(
            "INSERT INTO turismo.horario (id_sitio, abierto_24h, comentario, activo) "
            "VALUES (:id_sitio, :abierto_24h, :comentario, TRUE) RETURNING id_horario"
        ),
        {
            "id_sitio": id_sitio,
            "abierto_24h": datos.horario.abierto_24h,
            "comentario": (datos.horario.comentario or "").strip() or None,
        },
    ).mappings().one()
    for dia, h_ini, h_fin in _resolver_detalles_horario(datos.horario):
        db.execute(
            text(
                """
                INSERT INTO turismo.horario_detalle (id_horario, dia_semana, hora_inicio, hora_fin, activo)
                VALUES (:id_horario, :dia_semana, :hora_inicio, :hora_fin, TRUE)
                """
            ),
            {"id_horario": horario["id_horario"], "dia_semana": dia, "hora_inicio": h_ini, "hora_fin": h_fin},
        )

    db.execute(text("DELETE FROM turismo.rango_precio WHERE id_sitio = :id_sitio"), {"id_sitio": id_sitio})
    db.execute(text("DELETE FROM turismo.tarifa_acceso WHERE id_sitio = :id_sitio"), {"id_sitio": id_sitio})
    if not datos.precio.es_gratuito:
        tiene_rango = (
            datos.precio.precio_min is not None
            and datos.precio.precio_max is not None
        )
        if tiene_rango:
            db.execute(
                text(
                    """
                    INSERT INTO turismo.rango_precio (id_sitio, precio_min, precio_max, etiqueta_precio, activo)
                    VALUES (:id_sitio, :precio_min, :precio_max, :etiqueta_precio, TRUE)
                    """
                ),
                {
                    "id_sitio": id_sitio,
                    "precio_min": datos.precio.precio_min,
                    "precio_max": datos.precio.precio_max,
                    "etiqueta_precio": datos.precio.etiqueta_precio,
                },
            )
        if datos.precio.tarifa_acceso is not None:
            db.execute(
                text("INSERT INTO turismo.tarifa_acceso (id_sitio, precio, condicion, activo) VALUES (:id_sitio, :precio, :condicion, TRUE)"),
                {"id_sitio": id_sitio, "precio": datos.precio.tarifa_acceso, "condicion": datos.precio.condicion_tarifa},
            )

    sitio_nuevo = obtener_sitio(db, id_sitio).model_dump(mode="json")
    _trazar(
        db,
        actor,
        "UPDATE",
        "sitio",
        id_sitio,
        anterior=sitio_anterior,
        nuevo=sitio_nuevo,
        referencia=sitio_nuevo.get("nombre") or sitio_anterior.get("nombre"),
    )
    regenerar_chunk_descripcion(db, "sitio", id_sitio)
    db.commit()
    _eliminar_archivos_locales([url for url in urls_anteriores if url not in set(urls_nuevas)])
    return obtener_sitio(db, id_sitio)


def eliminar_sitio(
    db: Session,
    id_sitio: int,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
    usuario: dict | None = None,
) -> SitioResponse:
    if usuario is not None:
        validar_acceso_sitio(db, usuario, id_sitio, "attractions", "eliminar")
    sitio = obtener_sitio(db, id_sitio)
    urls = [
        row["url"]
        for row in db.execute(
            text("SELECT url FROM turismo.multimedia WHERE id_sitio = :id_sitio"),
            {"id_sitio": id_sitio},
        ).mappings().all()
    ]
    repo_paths = eliminar_repositorios_de_vinculo(db, "sitio", id_sitio)
    db.execute(text("DELETE FROM gis.ruta_puntos WHERE id_sitio = :id_sitio"), {"id_sitio": id_sitio})
    db.execute(text("DELETE FROM turismo.sitio WHERE id_sitio = :id_sitio"), {"id_sitio": id_sitio})
    _trazar(
        db,
        actor,
        "DELETE",
        "sitio",
        id_sitio,
        anterior={"id_sitio": sitio.id_sitio, "nombre": sitio.nombre},
        referencia=sitio.nombre,
    )
    db.commit()
    _eliminar_archivos_locales(urls)
    eliminar_directorios_repositorio(repo_paths)
    sitio.activo = False
    sitio.imagen_url = None
    return sitio


def cambiar_estado_sitio(
    db: Session,
    id_sitio: int,
    activo: bool,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
    usuario: dict | None = None,
) -> SitioResponse:
    if usuario is not None:
        validar_acceso_sitio(db, usuario, id_sitio, "attractions", "actualizar")
    anterior = db.execute(
        text("SELECT nombre, activo FROM turismo.sitio WHERE id_sitio = :id_sitio"),
        {"id_sitio": id_sitio},
    ).mappings().first()
    if not anterior:
        raise _not_found("El atractivo turistico no existe")
    row = db.execute(
        text(
            """
            UPDATE turismo.sitio
            SET activo = :activo
            WHERE id_sitio = :id_sitio
            RETURNING id_sitio, nombre, activo
            """
        ),
        {"id_sitio": id_sitio, "activo": activo},
    ).mappings().first()
    if not row:
        raise _not_found("El atractivo turistico no existe")
    _trazar(
        db,
        actor,
        "UPDATE",
        "sitio",
        id_sitio,
        anterior={"activo": anterior["activo"]},
        nuevo={"activo": activo},
        referencia=anterior["nombre"],
    )
    db.commit()
    return obtener_sitio(db, id_sitio)
