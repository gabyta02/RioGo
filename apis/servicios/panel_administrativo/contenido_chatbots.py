from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
import json
import re
import shutil
import time
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.embeddings.embeddings import generar_embedding
from core.autenticacion.permisos import obtener_sitios_permitidos, validar_acceso_vinculo
from core.infra.texto_limpieza import limpiar_texto_chunk, limpiar_texto_para_embedding, texto_tiene_contenido_util
from core.infra.trazabilidad import ACTOR_SISTEMA, ActorTrazabilidad, registrar_evento_actor
from esquemas.panel_administrativo.contenido_chatbots import (
    DocumentoChatbotContenidoUpdate,
    DocumentoChatbotContenidoResponse,
    DocumentoChatbotCreate,
    DocumentoChatbotResponse,
    DocumentoChatbotUpdate,
    EntidadChatbotResponse,
    RepositorioChatbotCreate,
    RepositorioChatbotResponse,
    RepositorioChatbotUpdate,
    TipoOrigen,
)

MARKDOWN_DIR = Path("fuente_datos/mardowks")
METADATA_FILE = "_metadata.json"
LEGACY_DOCUMENTS_FILE = "_documents.json"
LIMPIEZA_REPOS_INTERVALO_SEG = 300
_ultima_limpieza_repos: float | None = None
SECTION_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
HASH_WRAPPED_HEADING_RE = re.compile(r"^#{1,6}\s*(.+?)\s*#{1,6}$")
BOLD_HEADING_RE = re.compile(r"^\*\*(.+?)\*\*$")


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
    return slug or "documento"


def _repo_dir(origen: TipoOrigen, slug: str) -> Path:
    return MARKDOWN_DIR / f"{origen}s" / slug


def _is_path_inside(path: Path, base: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_base = base.resolve()
    except OSError:
        return False
    return resolved == resolved_base or resolved_base in resolved.parents


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _delete_directory(path: Path) -> None:
    if not _is_path_inside(path, MARKDOWN_DIR) or not path.exists() or not path.is_dir():
        return
    shutil.rmtree(path)


def _metadata_by_slug(slug: str) -> tuple[Path, dict[str, Any]]:
    matches = list(MARKDOWN_DIR.glob(f"*s/{slug}/{METADATA_FILE}"))
    if not matches:
        raise _not_found("No se encontro el repositorio de contenido")

    repo_path = matches[0].parent
    metadata = _ensure_metadata_defaults(_read_json(repo_path / METADATA_FILE, None), repo_path)
    if not metadata:
        raise _bad_request("El repositorio no tiene metadatos validos")
    return repo_path, metadata


def _ensure_metadata_defaults(metadata: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    metadata = dict(metadata)
    if "origen" not in metadata and metadata.get("tipo_vinculo"):
        metadata["origen"] = metadata["tipo_vinculo"]
    metadata.setdefault("slug", repo_path.name)
    metadata.setdefault("nombre", repo_path.name)
    return metadata


def _metadata_by_vinculo(origen: TipoOrigen, id_vinculo: int) -> tuple[Path, dict[str, Any]] | None:
    for metadata_path in MARKDOWN_DIR.glob(f"{origen}s/*/{METADATA_FILE}"):
        metadata = _ensure_metadata_defaults(_read_json(metadata_path, None), metadata_path.parent)
        if (
            metadata.get("origen") == origen
            and int(metadata.get("id_vinculo") or 0) == id_vinculo
        ):
            return metadata_path.parent, metadata
    return None


def _metadata_paths_by_vinculo(origen: TipoOrigen, id_vinculo: int) -> list[Path]:
    matches: list[Path] = []
    for metadata_path in MARKDOWN_DIR.glob(f"{origen}s/*/{METADATA_FILE}"):
        metadata = _ensure_metadata_defaults(_read_json(metadata_path, None), metadata_path.parent)
        if (
            metadata.get("origen") == origen
            and int(metadata.get("id_vinculo") or 0) == id_vinculo
        ):
            matches.append(metadata_path)
    return matches


def _entity_exists(db: Session, origen: TipoOrigen, id_vinculo: int) -> bool:
    table = "turismo.sitio" if origen == "sitio" else "gis.rutas_turistica"
    column = "id_sitio" if origen == "sitio" else "id_ruta"
    return bool(
        db.execute(
            text(f"SELECT 1 FROM {table} WHERE {column} = :id_vinculo"),
            {"id_vinculo": id_vinculo},
        ).scalar()
    )


def _limpiar_documentos_huerfanos(db: Session) -> None:
    db.execute(
        text(
            """
            DELETE FROM turismo.sitio_documento d
            WHERE d.origen = 'sitio'
              AND NOT EXISTS (
                  SELECT 1
                  FROM turismo.sitio s
                  WHERE s.id_sitio = d.id_vinculo
              )
            """
        )
    )
    db.execute(
        text(
            """
            DELETE FROM turismo.sitio_documento d
            WHERE d.origen = 'ruta'
              AND NOT EXISTS (
                  SELECT 1
                  FROM gis.rutas_turistica r
                  WHERE r.id_ruta = d.id_vinculo
              )
            """
        )
    )


def _get_entity(db: Session, origen: TipoOrigen, id_vinculo: int) -> dict[str, Any]:
    if origen == "sitio":
        row = db.execute(
            text(
                """
                SELECT
                    id_sitio AS id_vinculo,
                    nombre,
                    descripcion_corta AS descripcion,
                    activo
                FROM turismo.sitio
                WHERE id_sitio = :id_vinculo
                """
            ),
            {"id_vinculo": id_vinculo},
        ).mappings().first()
    else:
        row = db.execute(
            text(
                """
                SELECT
                    id_ruta AS id_vinculo,
                    titulo AS nombre,
                    descripcion,
                    activo
                FROM gis.rutas_turistica
                WHERE id_ruta = :id_vinculo
                """
            ),
            {"id_vinculo": id_vinculo},
        ).mappings().first()

    if not row:
        raise _not_found("No se encontro la entidad seleccionada")
    return dict(row)


def _document_response(row: dict[str, Any]) -> DocumentoChatbotResponse:
    return DocumentoChatbotResponse(
        id_documento=row["id_documento"],
        origen=row["origen"],
        id_vinculo=row["id_vinculo"],
        titulo=row["titulo"],
        descripcion=row["descripcion"],
        ruta_archivo=row.get("ruta_archivo"),
        activo=row["activo"],
        total_secciones=int(row.get("total_secciones") or 0),
    )


def _titulo_seccion_desde_linea(linea: str) -> str | None:
    text_line = linea.strip()
    for pattern in (SECTION_HEADING_RE, HASH_WRAPPED_HEADING_RE, BOLD_HEADING_RE):
        match = pattern.match(text_line)
        if match:
            title = match.group(2 if pattern is SECTION_HEADING_RE else 1).strip()
            title = title.strip("#").strip("*").strip()
            return title or None
    return None


def _extraer_secciones_markdown(contenido: str) -> list[dict[str, str]]:
    markdown = contenido.strip()
    sections: list[dict[str, str]] = []
    current: dict[str, Any] | None = None

    for line in markdown.splitlines():
        title = _titulo_seccion_desde_linea(line)
        if title:
            if current and "\n".join(current["contenido"]).strip():
                sections.append(
                    {
                        "titulo": current["titulo"][:220],
                        "contenido": "\n".join(current["contenido"]).strip(),
                    }
                )
            current = {"titulo": title, "contenido": []}
            continue

        if current is not None:
            current["contenido"].append(line)

    if current and "\n".join(current["contenido"]).strip():
        sections.append(
            {
                "titulo": current["titulo"][:220],
                "contenido": "\n".join(current["contenido"]).strip(),
            }
        )

    if not sections:
        raise _bad_request(
            "Agrega al menos una seccion valida con un encabezado, una linea en negrita o la herramienta Insertar seccion."
        )

    return sections


def _documentos_de_repositorio(
    db: Session,
    origen: TipoOrigen,
    id_vinculo: int,
) -> list[DocumentoChatbotResponse]:
    rows = db.execute(
        text(
            """
            SELECT
                d.id_documento,
                d.origen::TEXT AS origen,
                d.id_vinculo,
                d.titulo,
                d.repositorio_nombre,
                d.descripcion,
                d.ruta_archivo,
                d.activo,
                COUNT(c.id_chunk)::INT AS total_secciones
            FROM turismo.sitio_documento d
            LEFT JOIN turismo.chunk_fuente cf ON cf.id_documento = d.id_documento
            LEFT JOIN turismo.chunk c ON c.id_fuente = cf.id_fuente
            WHERE d.origen = CAST(:origen AS turismo.tipo_documento_t)
              AND d.id_vinculo = :id_vinculo
            GROUP BY d.id_documento, d.origen, d.id_vinculo, d.titulo, d.repositorio_nombre, d.descripcion, d.ruta_archivo, d.activo
            ORDER BY d.id_documento DESC
            """
        ),
        {"origen": origen, "id_vinculo": id_vinculo},
    ).mappings().all()
    return [_document_response(dict(row)) for row in rows]


def _migrar_documentos_legacy(db: Session, repo_path: Path, metadata: dict[str, Any]) -> None:
    legacy_path = repo_path / LEGACY_DOCUMENTS_FILE
    legacy_documents = _read_json(legacy_path, [])
    if not isinstance(legacy_documents, list) or not legacy_documents:
        return

    for item in legacy_documents:
        if not isinstance(item, dict) or not item.get("descripcion"):
            continue

        exists = db.execute(
            text(
                """
                SELECT 1
                FROM turismo.sitio_documento
                WHERE origen = CAST(:origen AS turismo.tipo_documento_t)
                  AND id_vinculo = :id_vinculo
                  AND descripcion = :descripcion
                LIMIT 1
                """
            ),
            {
                "origen": metadata["origen"],
                "id_vinculo": metadata["id_vinculo"],
                "descripcion": item["descripcion"],
            },
        ).scalar()
        if exists:
            continue

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
                    CAST(:origen AS turismo.tipo_documento_t),
                    :titulo,
                    :id_vinculo,
                    :repositorio_nombre,
                    :descripcion,
                    :ruta_archivo,
                    :activo
                )
                """
            ),
            {
                "origen": metadata["origen"],
                "titulo": (item.get("titulo") or metadata.get("nombre") or item["descripcion"])[:500],
                "id_vinculo": metadata["id_vinculo"],
                "repositorio_nombre": metadata.get("nombre"),
                "descripcion": item["descripcion"],
                "ruta_archivo": item.get("ruta_archivo"),
                "activo": bool(item.get("activo")) and bool(item.get("ruta_archivo")),
            },
        )
    db.commit()


def _repo_response(db: Session, repo_path: Path, metadata: dict[str, Any]) -> RepositorioChatbotResponse:
    metadata = _ensure_metadata_defaults(metadata, repo_path)
    documents = _documentos_de_repositorio(
        db,
        metadata["origen"],
        metadata["id_vinculo"],
    )
    persisted_name = db.execute(
        text(
            """
            SELECT repositorio_nombre
            FROM turismo.sitio_documento
            WHERE origen = CAST(:origen AS turismo.tipo_documento_t)
              AND id_vinculo = :id_vinculo
              AND repositorio_nombre IS NOT NULL
            ORDER BY id_documento DESC
            LIMIT 1
            """
        ),
        {
            "origen": metadata["origen"],
            "id_vinculo": metadata["id_vinculo"],
        },
    ).scalar()
    return RepositorioChatbotResponse(
        origen=metadata["origen"],
        id_vinculo=metadata["id_vinculo"],
        nombre=persisted_name or metadata["nombre"],
        slug=metadata["slug"],
        ruta_directorio=str(repo_path),
        total_documentos=len(documents),
        documentos=documents,
    )


def _obtener_documento(db: Session, id_documento: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT
                d.id_documento,
                d.origen::TEXT AS origen,
                d.id_vinculo,
                d.titulo,
                d.repositorio_nombre,
                d.descripcion,
                d.ruta_archivo,
                d.activo,
                COUNT(c.id_chunk)::INT AS total_secciones
            FROM turismo.sitio_documento d
            LEFT JOIN turismo.chunk_fuente cf ON cf.id_documento = d.id_documento
            LEFT JOIN turismo.chunk c ON c.id_fuente = cf.id_fuente
            WHERE d.id_documento = :id_documento
            GROUP BY d.id_documento, d.origen, d.id_vinculo, d.titulo, d.repositorio_nombre, d.descripcion, d.ruta_archivo, d.activo
            """
        ),
        {"id_documento": id_documento},
    ).mappings().first()
    if not row:
        raise _not_found("No se encontro el documento")
    return dict(row)


def _slug_documento(documento: dict[str, Any]) -> str:
    slug = _slugify(documento["titulo"])[:80].strip("-") or "documento"
    return f"{documento['id_documento']}-{slug}.md"


def _puede_acceder_vinculo(
    db: Session,
    usuario: dict | None,
    origen: TipoOrigen,
    id_vinculo: int,
    accion: str,
) -> bool:
    if usuario is None:
        return True
    try:
        validar_acceso_vinculo(db, usuario, origen, id_vinculo, "chatbot_content", accion)
    except HTTPException:
        return False
    return True


def _validar_documento_acceso(
    db: Session,
    usuario: dict | None,
    documento: dict[str, Any],
    accion: str,
) -> None:
    if usuario is None:
        return
    validar_acceso_vinculo(
        db,
        usuario,
        documento["origen"],
        int(documento["id_vinculo"]),
        "chatbot_content",
        accion,
    )


def _usuario_tiene_alcance_sitio(
    db: Session,
    usuario: dict | None,
) -> bool:
    if usuario is None or usuario.get("rol") == "super-admin":
        return False
    return obtener_sitios_permitidos(db, usuario, "chatbot_content", "ver") is not None


def _bloquear_gestion_repositorio_si_alcance_sitio(
    db: Session,
    usuario: dict | None,
) -> None:
    # Los usuarios con alcance por sitio solo gestionan documentos; el repositorio
    # del sitio se crea y mantiene automáticamente para evitar cambios de contenedor.
    if _usuario_tiene_alcance_sitio(db, usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "El repositorio del sitio es administrado por el sistema. "
                "Puedes crear, editar y eliminar documentos."
            ),
        )


def buscar_entidades_para_contenido(
    db: Session,
    q: str | None,
    tipo: TipoOrigen | Literal["all"],
    limit: int,
    usuario: dict | None = None,
) -> list[EntidadChatbotResponse]:
    query = f"%{(q or '').strip()}%"
    rows: list[dict[str, Any]] = []

    if tipo in ("all", "sitio"):
        sitio_sql = """
                SELECT
                    'sitio' AS origen,
                    id_sitio AS id_vinculo,
                    nombre,
                    descripcion_corta AS descripcion,
                    activo
                FROM turismo.sitio
                WHERE (:q = '%%' OR nombre ILIKE :q OR descripcion_corta ILIKE :q)
        """
        sitio_params: dict[str, Any] = {"q": query, "limit": limit}
        if usuario is not None:
            sitios_permitidos = obtener_sitios_permitidos(db, usuario, "chatbot_content", "ver")
            if sitios_permitidos is not None:
                if not sitios_permitidos:
                    sitio_rows = []
                else:
                    sitio_sql += " AND id_sitio = ANY(:sitios_permitidos)"
                    sitio_params["sitios_permitidos"] = sitios_permitidos
                    sitio_sql += " ORDER BY nombre ASC LIMIT :limit"
                    sitio_rows = db.execute(text(sitio_sql), sitio_params).mappings().all()
            else:
                sitio_sql += " ORDER BY nombre ASC LIMIT :limit"
                sitio_rows = db.execute(text(sitio_sql), sitio_params).mappings().all()
        else:
            sitio_sql += " ORDER BY nombre ASC LIMIT :limit"
            sitio_rows = db.execute(text(sitio_sql), sitio_params).mappings().all()
        rows.extend(dict(row) for row in sitio_rows)

    if tipo in ("all", "ruta"):
        if usuario is None or obtener_sitios_permitidos(db, usuario, "chatbot_content", "ver") is None:
            route_rows = db.execute(
            text(
                """
                SELECT
                    'ruta' AS origen,
                    id_ruta AS id_vinculo,
                    titulo AS nombre,
                    descripcion,
                    activo
                FROM gis.rutas_turistica
                WHERE (:q = '%%' OR titulo ILIKE :q OR descripcion ILIKE :q)
                ORDER BY titulo ASC
                LIMIT :limit
                """
            ),
            {"q": query, "limit": limit},
            ).mappings().all()
            rows.extend(dict(row) for row in route_rows)

    return [EntidadChatbotResponse(**row) for row in rows[:limit]]


def asegurar_repositorio_sitio_chatbot(
    db: Session,
    id_sitio: int,
) -> RepositorioChatbotResponse:
    return crear_repositorio_chatbot(
        db,
        RepositorioChatbotCreate(origen="sitio", id_vinculo=int(id_sitio)),
        usuario=None,
    )


def _asegurar_repositorios_sitios_permitidos(
    db: Session,
    usuario: dict | None,
) -> None:
    if usuario is None:
        return
    sitios_permitidos = obtener_sitios_permitidos(
        db,
        usuario,
        "chatbot_content",
        "ver",
    )
    if not sitios_permitidos:
        return
    # Backfill idempotente: al listar, cualquier dueño con sitios asignados obtiene
    # el repositorio de cada sitio aunque la asignación haya ocurrido antes.
    for id_sitio in sitios_permitidos:
        asegurar_repositorio_sitio_chatbot(db, int(id_sitio))


def listar_repositorios_chatbot(
    db: Session,
    usuario: dict | None = None,
) -> list[RepositorioChatbotResponse]:
    global _ultima_limpieza_repos
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    _asegurar_repositorios_sitios_permitidos(db, usuario)
    ahora = time.time()
    if (
        _ultima_limpieza_repos is None
        or ahora - _ultima_limpieza_repos >= LIMPIEZA_REPOS_INTERVALO_SEG
    ):
        _limpiar_documentos_huerfanos(db)
        db.commit()
        _ultima_limpieza_repos = ahora
    repositories: list[RepositorioChatbotResponse] = []
    for metadata_path in sorted(MARKDOWN_DIR.glob(f"*/*/{METADATA_FILE}")):
        metadata = _read_json(metadata_path, None)
        if not isinstance(metadata, dict):
            continue
        try:
            metadata = _ensure_metadata_defaults(metadata, metadata_path.parent)
            if not _entity_exists(db, metadata["origen"], metadata["id_vinculo"]):
                paths = eliminar_repositorios_de_vinculo(
                    db,
                    metadata["origen"],
                    metadata["id_vinculo"],
                )
                db.commit()
                eliminar_directorios_repositorio(paths)
                continue
            _migrar_documentos_legacy(db, metadata_path.parent, metadata)
            if not _puede_acceder_vinculo(
                db,
                usuario,
                metadata["origen"],
                int(metadata["id_vinculo"]),
                "ver",
            ):
                continue
            repositories.append(_repo_response(db, metadata_path.parent, metadata))
        except (KeyError, TypeError):
            continue
    return repositories


def crear_repositorio_chatbot(
    db: Session,
    datos: RepositorioChatbotCreate,
    usuario: dict | None = None,
) -> RepositorioChatbotResponse:
    _bloquear_gestion_repositorio_si_alcance_sitio(db, usuario)
    if usuario is not None:
        validar_acceso_vinculo(
            db,
            usuario,
            datos.origen,
            datos.id_vinculo,
            "chatbot_content",
            "crear",
        )
    entity = _get_entity(db, datos.origen, datos.id_vinculo)
    slug = f"{datos.id_vinculo}-{_slugify(entity['nombre'])}"
    repo_path = _repo_dir(datos.origen, slug)
    metadata_path = repo_path / METADATA_FILE

    if metadata_path.exists():
        metadata = _ensure_metadata_defaults(_read_json(metadata_path, None), repo_path)
        if metadata:
            return _repo_response(db, repo_path, metadata)

    metadata = {
        "origen": datos.origen,
        "id_vinculo": datos.id_vinculo,
        "nombre": entity["nombre"],
        "slug": slug,
        "creado_en": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(metadata_path, metadata)
    return _repo_response(db, repo_path, metadata)


def crear_documento_chatbot(
    db: Session,
    slug: str,
    datos: DocumentoChatbotCreate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
    usuario: dict | None = None,
) -> RepositorioChatbotResponse:
    repo_path, metadata = _metadata_by_slug(slug)
    if usuario is not None:
        validar_acceso_vinculo(
            db,
            usuario,
            metadata["origen"],
            int(metadata["id_vinculo"]),
            "chatbot_content",
            "crear",
        )
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
                    CAST(:origen AS turismo.tipo_documento_t),
                    :titulo,
                    :id_vinculo,
                    :repositorio_nombre,
                    :descripcion,
                    NULL,
                    FALSE
            )
            """
        ),
        {
            "origen": metadata["origen"],
            "titulo": datos.titulo.strip(),
            "id_vinculo": metadata["id_vinculo"],
            "repositorio_nombre": metadata.get("nombre"),
            "descripcion": datos.descripcion.strip(),
        },
    )
    _trazar(
        db,
        actor,
        "INSERT",
        "sitio_documento",
        nuevo={"slug": slug, "titulo": datos.titulo.strip(), "descripcion": datos.descripcion.strip()},
    )
    db.commit()
    return _repo_response(db, repo_path, metadata)


def _replace_document_paths(db: Session, origen: TipoOrigen, id_vinculo: int, old_dir: Path, new_dir: Path) -> None:
    old_prefix = str(old_dir)
    new_prefix = str(new_dir)
    db.execute(
        text(
            """
            UPDATE turismo.sitio_documento
            SET ruta_archivo = REPLACE(ruta_archivo, :old_prefix, :new_prefix)
            WHERE origen = CAST(:origen AS turismo.tipo_documento_t)
              AND id_vinculo = :id_vinculo
              AND ruta_archivo LIKE :old_like
            """
        ),
        {
            "origen": origen,
            "id_vinculo": id_vinculo,
            "old_prefix": old_prefix,
            "new_prefix": new_prefix,
            "old_like": f"{old_prefix}%",
        },
    )


def renombrar_repositorio_chatbot(
    db: Session,
    slug: str,
    datos: RepositorioChatbotUpdate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
    usuario: dict | None = None,
) -> RepositorioChatbotResponse:
    repo_path, metadata = _metadata_by_slug(slug)
    metadata = _ensure_metadata_defaults(metadata, repo_path)
    _bloquear_gestion_repositorio_si_alcance_sitio(db, usuario)
    if usuario is not None:
        validar_acceso_vinculo(
            db,
            usuario,
            metadata["origen"],
            int(metadata["id_vinculo"]),
            "chatbot_content",
            "actualizar",
        )
    nombre = datos.nombre.strip()
    new_slug = f"{metadata['id_vinculo']}-{_slugify(nombre)}"
    new_repo_path = _repo_dir(metadata["origen"], new_slug)

    if new_repo_path.exists() and new_repo_path.resolve() != repo_path.resolve():
        raise _bad_request("Ya existe un repositorio con ese nombre")

    metadata.update(
        {
            "nombre": nombre,
            "slug": new_slug,
            "actualizado_en": datetime.now(timezone.utc).isoformat(),
        }
    )

    try:
        db.execute(
            text(
                """
                UPDATE turismo.sitio_documento
                SET repositorio_nombre = :nombre
                WHERE origen = CAST(:origen AS turismo.tipo_documento_t)
                  AND id_vinculo = :id_vinculo
                """
            ),
            {
                "nombre": nombre,
                "origen": metadata["origen"],
                "id_vinculo": metadata["id_vinculo"],
            },
        )
        if new_repo_path.resolve() != repo_path.resolve():
            new_repo_path.parent.mkdir(parents=True, exist_ok=True)
            repo_path.rename(new_repo_path)
            _replace_document_paths(
                db,
                metadata["origen"],
                metadata["id_vinculo"],
                repo_path,
                new_repo_path,
            )
        _write_json(new_repo_path / METADATA_FILE, metadata)
        _trazar(
            db,
            actor,
            "UPDATE",
            "sitio_documento",
            metadata["id_vinculo"],
            anterior={"slug": slug, "nombre": metadata.get("nombre")},
            nuevo={"slug": new_slug, "nombre": nombre},
            referencia=nombre,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _repo_response(db, new_repo_path, metadata)


def eliminar_directorios_repositorio(paths: list[Path]) -> None:
    for path in paths:
        _delete_directory(path)


def eliminar_repositorios_de_vinculo(db: Session, origen: TipoOrigen, id_vinculo: int) -> list[Path]:
    paths = [metadata_path.parent for metadata_path in _metadata_paths_by_vinculo(origen, id_vinculo)]
    db.execute(
        text(
            """
            DELETE FROM turismo.sitio_documento
            WHERE origen = CAST(:origen AS turismo.tipo_documento_t)
              AND id_vinculo = :id_vinculo
            """
        ),
        {"origen": origen, "id_vinculo": id_vinculo},
    )
    return paths


def eliminar_repositorio_chatbot(
    db: Session,
    slug: str,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
    usuario: dict | None = None,
) -> RepositorioChatbotResponse:
    repo_path, metadata = _metadata_by_slug(slug)
    metadata = _ensure_metadata_defaults(metadata, repo_path)
    _bloquear_gestion_repositorio_si_alcance_sitio(db, usuario)
    if usuario is not None:
        validar_acceso_vinculo(
            db,
            usuario,
            metadata["origen"],
            int(metadata["id_vinculo"]),
            "chatbot_content",
            "eliminar",
        )
    response = _repo_response(db, repo_path, metadata)
    paths = eliminar_repositorios_de_vinculo(
        db,
        metadata["origen"],
        metadata["id_vinculo"],
    )
    if repo_path not in paths:
        paths.append(repo_path)
    _trazar(
        db,
        actor,
        "DELETE",
        "sitio_documento",
        metadata["id_vinculo"],
        anterior={"slug": slug, "nombre": metadata.get("nombre")},
        referencia=metadata.get("nombre"),
    )
    db.commit()
    eliminar_directorios_repositorio(paths)
    return response


def actualizar_documento_chatbot(
    db: Session,
    id_documento: int,
    datos: DocumentoChatbotUpdate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
    usuario: dict | None = None,
) -> DocumentoChatbotResponse:
    documento = _obtener_documento(db, id_documento)
    _validar_documento_acceso(db, usuario, documento, "actualizar")
    titulo = datos.titulo.strip()
    descripcion = datos.descripcion.strip()
    db.execute(
        text(
            """
            UPDATE turismo.sitio_documento
            SET titulo = :titulo,
                descripcion = :descripcion
            WHERE id_documento = :id_documento
            """
        ),
        {"id_documento": id_documento, "titulo": titulo, "descripcion": descripcion},
    )
    _trazar(
        db,
        actor,
        "UPDATE",
        "sitio_documento",
        id_documento,
        anterior={"titulo": documento.get("titulo"), "descripcion": documento.get("descripcion")},
        nuevo={"titulo": titulo, "descripcion": descripcion},
        referencia=titulo,
    )
    db.commit()
    return _document_response(_obtener_documento(db, id_documento))


def obtener_contenido_documento_chatbot(
    db: Session,
    id_documento: int,
    usuario: dict | None = None,
) -> DocumentoChatbotContenidoResponse:
    documento = _obtener_documento(db, id_documento)
    _validar_documento_acceso(db, usuario, documento, "ver")
    ruta_archivo = documento.get("ruta_archivo")
    if not ruta_archivo:
        return DocumentoChatbotContenidoResponse(id_documento=id_documento, contenido="")

    path = Path(ruta_archivo)
    if not path.exists() or not path.is_file():
        return DocumentoChatbotContenidoResponse(id_documento=id_documento, contenido="")

    return DocumentoChatbotContenidoResponse(
        id_documento=id_documento,
        contenido=path.read_text(encoding="utf-8"),
    )


def agregar_contenido_documento_chatbot(
    db: Session,
    id_documento: int,
    datos: DocumentoChatbotContenidoUpdate,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
    usuario: dict | None = None,
) -> DocumentoChatbotResponse:
    documento = _obtener_documento(db, id_documento)
    _validar_documento_acceso(db, usuario, documento, "exportar")
    markdown = datos.contenido.strip()
    secciones = _extraer_secciones_markdown(markdown)
    chunks_con_embedding = []
    for seccion in secciones:
        contenido_limpio = limpiar_texto_chunk(seccion["contenido"])
        if not contenido_limpio:
            continue

        titulo_limpio = limpiar_texto_chunk(seccion["titulo"])
        embedding_text = limpiar_texto_chunk(f"{titulo_limpio}. {contenido_limpio}")
        chunks_con_embedding.append(
            {
                "titulo": titulo_limpio[:200],
                "contenido": contenido_limpio,
                "embedding": generar_embedding(embedding_text),
            }
        )

    if not chunks_con_embedding:
        raise _bad_request("Cada seccion debe tener contenido util antes de generar embeddings.")

    metadata_match = _metadata_by_vinculo(documento["origen"], documento["id_vinculo"])
    if metadata_match:
        repo_path, metadata = metadata_match
        repo_slug = metadata["slug"]
    else:
        entity = _get_entity(db, documento["origen"], documento["id_vinculo"])
        repo_slug = f"{documento['id_vinculo']}-{_slugify(entity['nombre'])}"
        repo_path = _repo_dir(documento["origen"], repo_slug)
        metadata = {
            "origen": documento["origen"],
            "id_vinculo": documento["id_vinculo"],
            "nombre": entity["nombre"],
            "slug": repo_slug,
            "creado_en": datetime.now(timezone.utc).isoformat(),
        }
    repo_path.mkdir(parents=True, exist_ok=True)

    metadata_path = repo_path / METADATA_FILE
    if not metadata_path.exists():
        _write_json(metadata_path, metadata)

    file_path = repo_path / _slug_documento(documento)
    file_path.write_text(markdown + "\n", encoding="utf-8")

    try:
        db.execute(
            text(
                """
                UPDATE turismo.sitio_documento
                SET ruta_archivo = :ruta_archivo,
                    repositorio_nombre = :repositorio_nombre,
                    activo = TRUE
                WHERE id_documento = :id_documento
                """
            ),
            {
                "id_documento": id_documento,
                "ruta_archivo": str(file_path),
                "repositorio_nombre": metadata.get("nombre"),
            },
        )
        db.execute(
            text("DELETE FROM turismo.chunk_fuente WHERE id_documento = :id_documento"),
            {"id_documento": id_documento},
        )
        fuente = db.execute(
            text(
                """
                INSERT INTO turismo.chunk_fuente (tipo_chunk, origen, id_vinculo, id_documento)
                VALUES ('seccion', CAST(:origen AS turismo.origen_chunk_t), :id_vinculo, :id_documento)
                RETURNING id_fuente
                """
            ),
            {
                "origen": documento["origen"],
                "id_vinculo": documento["id_vinculo"],
                "id_documento": id_documento,
            },
        ).mappings().one()
        for chunk in chunks_con_embedding:
            if not chunk["embedding"]:
                continue
            db.execute(
                text(
                    """
                    INSERT INTO turismo.chunk (
                        id_fuente,
                        contenido,
                        embedding
                    )
                    VALUES (
                        :id_fuente,
                        :contenido,
                        CAST(:embedding AS vector)
                    )
                    """
                ),
                {
                    "id_fuente": fuente["id_fuente"],
                    "contenido": chunk["contenido"],
                    "embedding": chunk["embedding"],
                },
            )
        _trazar(
            db,
            actor,
            "UPDATE",
            "sitio_documento",
            id_documento,
            anterior={"contenido": "anterior"},
            nuevo={"contenido": "actualizado"},
            referencia=documento.get("titulo"),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _document_response(_obtener_documento(db, id_documento))


def eliminar_documento_chatbot(
    db: Session,
    id_documento: int,
    actor: ActorTrazabilidad = ACTOR_SISTEMA,
    usuario: dict | None = None,
) -> DocumentoChatbotResponse:
    documento = _obtener_documento(db, id_documento)
    _validar_documento_acceso(db, usuario, documento, "eliminar")
    ruta_archivo = documento.get("ruta_archivo")
    if ruta_archivo:
        path = Path(ruta_archivo)
        if path.exists() and path.is_file():
            path.unlink()

    db.execute(
        text("DELETE FROM turismo.sitio_documento WHERE id_documento = :id_documento"),
        {"id_documento": id_documento},
    )
    _trazar(
        db,
        actor,
        "DELETE",
        "sitio_documento",
        id_documento,
        anterior=dict(documento),
        referencia=documento.get("titulo") or documento.get("repositorio_nombre"),
    )
    db.commit()
    return _document_response(documento)
