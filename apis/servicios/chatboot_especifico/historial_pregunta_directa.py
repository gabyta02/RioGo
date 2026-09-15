from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.embeddings.embeddings import generar_embedding
from esquemas.chatboot_especifico.historial_pregunta_directa import (
    HistorialPreguntaDirectaEntrada,
    HistorialPreguntaDirectaSalida,
)

ROL_USUARIO = "usuario"
ROL_RESPUESTA_SITIO = "conversacion_sitio_especifico"


def _obtener_o_crear_conversacion(
    db: Session,
    *,
    id_usuario: int,
    sesion_id: str,
    titulo: str,
) -> int:
    row = (
        db.execute(
            text(
                """
                SELECT id_conversacion
                FROM conversacion.conversacion
                WHERE id_usuario = :id_usuario
                  AND sesion_id = :sesion_id
                ORDER BY id_conversacion ASC
                LIMIT 1
                """
            ),
            {"id_usuario": id_usuario, "sesion_id": sesion_id},
        )
        .mappings()
        .first()
    )
    if row:
        return int(row["id_conversacion"])

    nuevo = (
        db.execute(
            text(
                """
                INSERT INTO conversacion.conversacion (id_usuario, sesion_id, titulo)
                VALUES (:id_usuario, :sesion_id, :titulo)
                RETURNING id_conversacion
                """
            ),
            {
                "id_usuario": id_usuario,
                "sesion_id": sesion_id,
                "titulo": titulo[:200] or None,
            },
        )
        .mappings()
        .one()
    )
    return int(nuevo["id_conversacion"])


def _existe_mensaje(
    db: Session,
    *,
    id_conversacion: int,
    client_message_id: str,
    rol: str,
) -> bool:
    row = (
        db.execute(
            text(
                """
                SELECT id_mensaje_pd
                FROM conversacion.mensaje_detalle
                WHERE id_conversacion = :id_conversacion
                  AND client_mensaje_id = :client_message_id
                  AND rol = :rol
                LIMIT 1
                """
            ),
            {
                "id_conversacion": id_conversacion,
                "client_message_id": client_message_id,
                "rol": rol,
            },
        )
        .mappings()
        .first()
    )
    return row is not None


def _insertar_mensaje(
    db: Session,
    *,
    id_conversacion: int,
    client_message_id: str,
    entidad_asociada: str,
    contenido: str,
    rol: str,
    embedding: str | None,
) -> bool:
    if _existe_mensaje(
        db,
        id_conversacion=id_conversacion,
        client_message_id=client_message_id,
        rol=rol,
    ):
        return False

    db.execute(
        text(
            """
            INSERT INTO conversacion.mensaje_detalle (
                id_conversacion,
                client_mensaje_id,
                entidad_asociada,
                contenido,
                embedding,
                rol
            )
            VALUES (
                :id_conversacion,
                :client_message_id,
                :entidad_asociada,
                :contenido,
                CASE
                    WHEN :embedding IS NULL THEN NULL
                    ELSE CAST(:embedding AS vector)
                END,
                :rol
            )
            """
        ),
        {
            "id_conversacion": id_conversacion,
            "client_message_id": client_message_id,
            "entidad_asociada": entidad_asociada[:100] or None,
            "contenido": contenido,
            "embedding": embedding,
            "rol": rol,
        },
    )
    return True


def guardar_historial_pregunta_directa(
    db: Session,
    payload: HistorialPreguntaDirectaEntrada,
) -> HistorialPreguntaDirectaSalida:
    if not payload.id_usuario:
        return HistorialPreguntaDirectaSalida(
            client_message_id=payload.client_message_id,
            usuario_guardado=False,
            respuesta_guardada=False,
            mensaje="No se guardó historial porque falta id_usuario.",
        )

    sesion_id = str(payload.sesion_id or "").strip()
    client_message_id = str(payload.client_message_id or "").strip()
    texto_usuario = str(payload.texto_usuario or "").strip()
    entidad_asociada = str(payload.entidad_asociada or "").strip()
    respuesta_json: dict[str, Any] = dict(payload.respuesta_json or {})
    if not sesion_id or not client_message_id or not texto_usuario or not respuesta_json:
        return HistorialPreguntaDirectaSalida(
            client_message_id=client_message_id,
            usuario_guardado=False,
            respuesta_guardada=False,
            mensaje=(
                "Debe enviar sesion_id, client_message_id, texto_usuario "
                "y respuesta_json."
            ),
        )

    respuesta_serializada = json.dumps(
        respuesta_json,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    try:
        id_conversacion = _obtener_o_crear_conversacion(
            db,
            id_usuario=int(payload.id_usuario),
            sesion_id=sesion_id,
            titulo=texto_usuario,
        )
        usuario_guardado = _insertar_mensaje(
            db,
            id_conversacion=id_conversacion,
            client_message_id=client_message_id,
            entidad_asociada=entidad_asociada,
            contenido=texto_usuario,
            embedding=generar_embedding(texto_usuario),
            rol=ROL_USUARIO,
        )
        respuesta_guardada = _insertar_mensaje(
            db,
            id_conversacion=id_conversacion,
            client_message_id=client_message_id,
            entidad_asociada=entidad_asociada,
            contenido=respuesta_serializada,
            embedding=None,
            rol=ROL_RESPUESTA_SITIO,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return HistorialPreguntaDirectaSalida(
        id_conversacion=id_conversacion,
        client_message_id=client_message_id,
        usuario_guardado=usuario_guardado,
        respuesta_guardada=respuesta_guardada,
        mensaje="Historial de pregunta directa procesado.",
    )
