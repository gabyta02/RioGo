from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.embeddings.embeddings import generar_embedding
from esquemas.chatboot_exploracion.historial_exploracion import (
    HistorialExploracionEntrada,
    HistorialExploracionSalida,
)


ROL_USUARIO = "usuario"
ROL_RESPUESTA_EXPLORACION = "conversacion_general"


def _normalizar_lista_texto(valores: list[str] | None) -> list[str] | None:
    if not valores:
        return None

    resultado: list[str] = []
    vistos: set[str] = set()
    for valor in valores:
        texto = str(valor or "").strip()
        if not texto:
            continue
        clave = texto.casefold()
        if clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(texto[:100])

    return resultado or None


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
                INSERT INTO conversacion.conversacion (
                    id_usuario,
                    sesion_id,
                    titulo
                )
                VALUES (
                    :id_usuario,
                    :sesion_id,
                    :titulo
                )
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
                SELECT id_mensaje_ex
                FROM conversacion.mensaje_explorador
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
    categorias: list[str] | None,
    subcategorias: list[str] | None,
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
            INSERT INTO conversacion.mensaje_explorador (
                id_conversacion,
                client_mensaje_id,
                categoria,
                subcategoria,
                contenido,
                embedding,
                rol
            )
            VALUES (
                :id_conversacion,
                :client_message_id,
                CAST(:categorias AS VARCHAR(100)[]),
                CAST(:subcategorias AS VARCHAR(100)[]),
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
            "categorias": categorias,
            "subcategorias": subcategorias,
            "contenido": contenido,
            "embedding": embedding,
            "rol": rol,
        },
    )
    return True


def guardar_historial_exploracion(
    db: Session,
    payload: HistorialExploracionEntrada,
) -> HistorialExploracionSalida:
    if not payload.id_usuario:
        return HistorialExploracionSalida(
            client_message_id=payload.client_message_id,
            usuario_guardado=False,
            respuesta_guardada=False,
            mensaje="No se guardó historial porque falta id_usuario.",
        )

    sesion_id = str(payload.sesion_id or "").strip()
    client_message_id = str(payload.client_message_id or "").strip()
    texto_usuario = str(payload.texto_usuario or "").strip()
    if not sesion_id or not client_message_id or not texto_usuario:
        return HistorialExploracionSalida(
            client_message_id=client_message_id,
            usuario_guardado=False,
            respuesta_guardada=False,
            mensaje="Debe enviar sesion_id, client_message_id y texto_usuario.",
        )

    respuesta_json: dict[str, Any] = dict(payload.respuesta_json or {})
    if not respuesta_json:
        return HistorialExploracionSalida(
            client_message_id=client_message_id,
            usuario_guardado=False,
            respuesta_guardada=False,
            mensaje="Debe enviar respuesta_json.",
        )

    categorias = _normalizar_lista_texto(payload.categorias)
    subcategorias = _normalizar_lista_texto(payload.subcategorias)
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
        if _existe_mensaje(
            db,
            id_conversacion=id_conversacion,
            client_message_id=client_message_id,
            rol=ROL_USUARIO,
        ):
            usuario_guardado = False
        else:
            usuario_guardado = _insertar_mensaje(
                db,
                id_conversacion=id_conversacion,
                client_message_id=client_message_id,
                categorias=categorias,
                subcategorias=subcategorias,
                contenido=texto_usuario,
                embedding=generar_embedding(texto_usuario),
                rol=ROL_USUARIO,
            )
        respuesta_guardada = _insertar_mensaje(
            db,
            id_conversacion=id_conversacion,
            client_message_id=client_message_id,
            categorias=categorias,
            subcategorias=subcategorias,
            contenido=respuesta_serializada,
            embedding=None,
            rol=ROL_RESPUESTA_EXPLORACION,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return HistorialExploracionSalida(
        id_conversacion=id_conversacion,
        client_message_id=client_message_id,
        usuario_guardado=usuario_guardado,
        respuesta_guardada=respuesta_guardada,
        mensaje="Historial de exploración procesado.",
    )
