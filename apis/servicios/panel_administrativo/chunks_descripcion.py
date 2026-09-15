from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.autenticacion.permisos import validar_acceso_vinculo
from core.embeddings.embeddings import generar_embedding
from core.infra.texto_limpieza import limpiar_texto_para_embedding, texto_tiene_contenido_util
from esquemas.panel_administrativo.chunks_descripcion import ChunkDescripcionRegenerarResponse
from esquemas.panel_administrativo.contenido_chatbots import TipoOrigen


def _obtener_descripcion_base(db: Session, origen: TipoOrigen, id_vinculo: int) -> dict[str, Any] | None:
    if origen == "sitio":
        row = db.execute(
            text(
                """
                SELECT id_sitio AS id_vinculo, descripcion_corta AS contenido
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
                SELECT id_ruta AS id_vinculo, descripcion AS contenido
                FROM gis.rutas_turistica
                WHERE id_ruta = :id_vinculo
                """
            ),
            {"id_vinculo": id_vinculo},
        ).mappings().first()
    return dict(row) if row else None


def regenerar_chunk_descripcion(
    db: Session,
    origen: TipoOrigen,
    id_vinculo: int,
    usuario: dict | None = None,
) -> ChunkDescripcionRegenerarResponse:
    if usuario is not None:
        validar_acceso_vinculo(
            db,
            usuario,
            origen,
            id_vinculo,
            "chatbot_content",
            "exportar",
        )
    base = _obtener_descripcion_base(db, origen, id_vinculo)
    if not base:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontro la entidad vinculada para regenerar la descripcion.",
        )

    contenido = limpiar_texto_para_embedding(base.get("contenido"))
    db.execute(
        text(
            """
            DELETE FROM turismo.chunk_fuente
            WHERE origen = CAST(:origen AS turismo.origen_chunk_t)
              AND id_vinculo = :id_vinculo
              AND tipo_chunk = 'descripcion'
            """
        ),
        {"origen": origen, "id_vinculo": id_vinculo},
    )

    if not texto_tiene_contenido_util(contenido):
        return ChunkDescripcionRegenerarResponse(
            origen=origen,
            id_vinculo=id_vinculo,
            total_chunks=0,
            contenido="",
        )

    embedding = generar_embedding(contenido)
    if not embedding:
        return ChunkDescripcionRegenerarResponse(
            origen=origen,
            id_vinculo=id_vinculo,
            total_chunks=0,
            contenido="",
        )

    fuente = db.execute(
        text(
            """
            INSERT INTO turismo.chunk_fuente (tipo_chunk, origen, id_vinculo, id_documento)
            VALUES ('descripcion', CAST(:origen AS turismo.origen_chunk_t), :id_vinculo, NULL)
            RETURNING id_fuente
            """
        ),
        {"origen": origen, "id_vinculo": id_vinculo},
    ).mappings().one()

    db.execute(
        text(
            """
            INSERT INTO turismo.chunk (id_fuente, contenido, embedding)
            VALUES (:id_fuente, :contenido, CAST(:embedding AS vector))
            """
        ),
        {
            "id_fuente": fuente["id_fuente"],
            "contenido": contenido,
            "embedding": embedding,
        },
    )

    return ChunkDescripcionRegenerarResponse(
        origen=origen,
        id_vinculo=id_vinculo,
        id_fuente=fuente["id_fuente"],
        total_chunks=1,
        contenido=contenido,
    )
