from datetime import date
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
from esquemas.panel_administrativo.noticias import (
    EstadoNoticia,
    EstadoVisualNoticia,
    ImagenNoticiaResponse,
    NoticiaCreate,
    NoticiaResponse,
    NoticiasListResponse,
    NoticiaUpdate,
    NoticiaUsuarioResponse,
    NoticiasUsuarioEstadoResponse,
    NoticiasUsuarioListResponse,
)

IMAGES_DIR = Path("fuente_datos/imagenes/noticias")
IMAGE_URL_PREFIX = "/api/v1/imagenes/noticias"


def _trazar(
    db: Session,
    actor: ActorTrazabilidad,
    accion: str,
    tabla: str,
    entidad: str | int | None = None,
    anterior: dict | None = None,
    nuevo: dict | None = None,
    referencia: str | None = None,
) -> None:
    registrar_evento_actor(
        db,
        actor,
        accion=accion,
        esquema_modificado="turismo",
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


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "noticia"


def _local_image_path(url: str | None) -> Path | None:
    if not url or not url.startswith(f"{IMAGE_URL_PREFIX}/"):
        return None
    relative = url.removeprefix(f"{IMAGE_URL_PREFIX}/").lstrip("/")
    path = (IMAGES_DIR / relative).resolve()
    base = IMAGES_DIR.resolve()
    if base not in path.parents and path != base:
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


def _estado_visual(activa: bool, fecha_fin: date | None, hoy: date | None = None) -> EstadoVisualNoticia:
    referencia = hoy or date.today()
    if not activa:
        return "inactiva"
    if fecha_fin is not None and fecha_fin < referencia:
        return "vencida"
    return "publicada"


def _noticia_response(row: dict[str, Any]) -> NoticiaResponse:
    return NoticiaResponse(
        id_noticia=int(row["id_noticia"]),
        titulo=row["titulo"],
        imagen_url=row.get("imagen_url"),
        fecha_inicio=row["fecha_inicio"],
        fecha_fin=row.get("fecha_fin"),
        activa=bool(row["activa"]),
        estado_visual=_estado_visual(bool(row["activa"]), row.get("fecha_fin")),
    )


def guardar_imagen_noticia(titulo_noticia: str, archivo: UploadFile) -> ImagenNoticiaResponse:
    if not titulo_noticia.strip():
        raise _bad_request("Debe enviar el titulo de la noticia para guardar la imagen")
    if not archivo.content_type or not archivo.content_type.startswith("image/"):
        raise _bad_request("El archivo debe ser una imagen")

    extension = Path(archivo.filename or "").suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".jpg"

    noticia_dir = IMAGES_DIR / _slugify(titulo_noticia)
    noticia_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    destination = noticia_dir / filename

    with destination.open("wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    return ImagenNoticiaResponse(
        url=f"{IMAGE_URL_PREFIX}/{noticia_dir.name}/{filename}",
        nombre_archivo=filename,
    )


def listar_noticias_usuario(db: Session) -> NoticiasUsuarioListResponse:
    rows = db.execute(
        text(
            """
            SELECT
                n.id_noticia,
                n.titulo,
                n.imagen_url,
                n.fecha_inicio,
                n.fecha_fin
            FROM turismo.noticia n
            WHERE n.activa = TRUE
              AND n.fecha_inicio <= CURRENT_DATE
              AND (n.fecha_fin IS NULL OR n.fecha_fin >= CURRENT_DATE)
            ORDER BY n.fecha_inicio DESC, n.id_noticia DESC
            """
        )
    ).mappings().all()

    noticias = [
        NoticiaUsuarioResponse(
            id_noticia=int(row["id_noticia"]),
            titulo=row["titulo"],
            imagen_url=row.get("imagen_url"),
            fecha_inicio=row["fecha_inicio"],
            fecha_fin=row.get("fecha_fin"),
        )
        for row in rows
    ]
    return NoticiasUsuarioListResponse(total=len(noticias), noticias=noticias)


def obtener_estado_noticias_usuario(db: Session) -> NoticiasUsuarioEstadoResponse:
    row = db.execute(
        text(
            """
            SELECT
                COALESCE(MAX(n.id_noticia), 0) AS ultimo_id,
                COUNT(*) AS total
            FROM turismo.noticia n
            WHERE n.activa = TRUE
              AND n.fecha_inicio <= CURRENT_DATE
              AND (n.fecha_fin IS NULL OR n.fecha_fin >= CURRENT_DATE)
            """
        )
    ).mappings().one()

    return NoticiasUsuarioEstadoResponse(
        ultimo_id=int(row["ultimo_id"] or 0),
        total=int(row["total"] or 0),
    )


def listar_noticias(
    db: Session,
    q: str | None,
    estado: EstadoNoticia,
    page: int,
    page_size: int,
) -> NoticiasListResponse:
    params: dict[str, Any] = {}
    filtros = []

    if q:
        filtros.append("n.titulo ILIKE :q")
        params["q"] = f"%{q.strip()}%"
    if estado == "activo":
        filtros.append("n.activa = TRUE")
    elif estado == "inactivo":
        filtros.append("n.activa = FALSE")
    elif estado == "publicada":
        filtros.append("n.activa = TRUE AND (n.fecha_fin IS NULL OR n.fecha_fin >= CURRENT_DATE)")
    elif estado == "vencida":
        filtros.append("n.fecha_fin IS NOT NULL AND n.fecha_fin < CURRENT_DATE")

    where_sql = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size

    total = int(
        db.execute(
            text(f"SELECT COUNT(*) FROM turismo.noticia n {where_sql}"),
            params,
        ).scalar()
        or 0
    )

    rows = db.execute(
        text(
            f"""
            SELECT
                n.id_noticia,
                n.titulo,
                n.imagen_url,
                n.fecha_inicio,
                n.fecha_fin,
                n.activa
            FROM turismo.noticia n
            {where_sql}
            ORDER BY n.fecha_inicio DESC, n.id_noticia DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    return NoticiasListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[_noticia_response(dict(row)) for row in rows],
    )


def obtener_noticia(db: Session, id_noticia: int) -> NoticiaResponse:
    row = db.execute(
        text(
            """
            SELECT
                id_noticia,
                titulo,
                imagen_url,
                fecha_inicio,
                fecha_fin,
                activa
            FROM turismo.noticia
            WHERE id_noticia = :id_noticia
            """
        ),
        {"id_noticia": id_noticia},
    ).mappings().first()
    if not row:
        raise _not_found("La noticia no existe")
    return _noticia_response(dict(row))


def crear_noticia(
    db: Session,
    datos: NoticiaCreate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> NoticiaResponse:
    row = db.execute(
        text(
            """
            INSERT INTO turismo.noticia (
                titulo,
                imagen_url,
                fecha_inicio,
                fecha_fin,
                activa
            )
            VALUES (
                :titulo,
                :imagen_url,
                :fecha_inicio,
                :fecha_fin,
                :activa
            )
            RETURNING id_noticia
            """
        ),
        {
            "titulo": datos.titulo.strip(),
            "imagen_url": datos.imagen_url,
            "fecha_inicio": datos.fecha_inicio,
            "fecha_fin": datos.fecha_fin,
            "activa": datos.activa,
        },
    ).mappings().one()

    id_noticia = int(row["id_noticia"])
    _trazar(
        db,
        actor,
        "INSERT",
        "noticia",
        id_noticia,
        nuevo={"titulo": datos.titulo},
    )
    db.commit()
    return obtener_noticia(db, id_noticia)


def actualizar_noticia(
    db: Session,
    id_noticia: int,
    datos: NoticiaUpdate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> NoticiaResponse:
    anterior = db.execute(
        text(
            """
            SELECT id_noticia, titulo, imagen_url, fecha_inicio, fecha_fin, activa
            FROM turismo.noticia
            WHERE id_noticia = :id_noticia
            """
        ),
        {"id_noticia": id_noticia},
    ).mappings().first()
    if not anterior:
        raise _not_found("La noticia no existe")
    old_imagen_url = anterior["imagen_url"]

    update_data = datos.model_dump(exclude_unset=True)
    if not update_data:
        return obtener_noticia(db, id_noticia)

    if "titulo" in update_data and update_data["titulo"] is not None:
        update_data["titulo"] = update_data["titulo"].strip()

    assignments = []
    params: dict[str, Any] = {"id_noticia": id_noticia}
    for key, value in update_data.items():
        assignments.append(f"{key} = :{key}")
        params[key] = value

    db.execute(
        text(
            f"""
            UPDATE turismo.noticia
            SET {', '.join(assignments)}
            WHERE id_noticia = :id_noticia
            """
        ),
        params,
    )
    _trazar(
        db,
        actor,
        "UPDATE",
        "noticia",
        id_noticia,
        anterior=dict(anterior),
        nuevo=update_data,
        referencia=update_data.get("titulo") or anterior["titulo"],
    )
    db.commit()

    if "imagen_url" in update_data and old_imagen_url != update_data["imagen_url"]:
        _eliminar_archivo_local(old_imagen_url)

    return obtener_noticia(db, id_noticia)


def cambiar_estado_noticia(
    db: Session,
    id_noticia: int,
    activa: bool,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> NoticiaResponse:
    anterior = db.execute(
        text("SELECT titulo, activa FROM turismo.noticia WHERE id_noticia = :id_noticia"),
        {"id_noticia": id_noticia},
    ).mappings().first()
    if not anterior:
        raise _not_found("La noticia no existe")
    row = db.execute(
        text(
            """
            UPDATE turismo.noticia
            SET activa = :activa
            WHERE id_noticia = :id_noticia
            RETURNING id_noticia
            """
        ),
        {"id_noticia": id_noticia, "activa": activa},
    ).first()
    _trazar(
        db,
        actor,
        "UPDATE",
        "noticia",
        id_noticia,
        anterior={"activa": anterior["activa"]},
        nuevo={"activa": activa},
        referencia=anterior["titulo"],
    )
    db.commit()
    return obtener_noticia(db, id_noticia)


def eliminar_noticia(
    db: Session,
    id_noticia: int,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
) -> NoticiaResponse:
    row = db.execute(
        text(
            """
            SELECT
                id_noticia,
                titulo,
                imagen_url,
                fecha_inicio,
                fecha_fin,
                activa
            FROM turismo.noticia
            WHERE id_noticia = :id_noticia
            """
        ),
        {"id_noticia": id_noticia},
    ).mappings().first()
    if not row:
        raise _not_found("La noticia no existe")

    response = _noticia_response(dict(row))
    db.execute(
        text("DELETE FROM turismo.noticia WHERE id_noticia = :id_noticia"),
        {"id_noticia": id_noticia},
    )
    _trazar(
        db,
        actor,
        "DELETE",
        "noticia",
        id_noticia,
        anterior=dict(row),
        referencia=row["titulo"],
    )
    db.commit()
    _eliminar_archivo_local(row["imagen_url"])
    return response
