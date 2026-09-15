from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.catalogo_trgm import normalizar_texto, sin_acentos
from esquemas.historial_usuario import EntidadAsociadaHistorial


TipoConversacion = Literal["general", "detalle", "mixto"]
TipoFiltroLista = Literal["general", "detalle", "sitio", "todos"]


_SQL_NORMALIZAR_NOMBRE_SITIO = (
    "translate(lower(trim(s.nombre)), "
    "'áéíóúüñàèìòùâêîôûãõç', "
    "'aeiouunaeiouaeiouaoc')"
)


def _resolver_entidad_sitio(
    db: Session, nombre_entidad: str | None
) -> EntidadAsociadaHistorial | None:
    nombre_limpio = normalizar_texto(nombre_entidad or "")
    if not nombre_limpio:
        return None

    nombre_ascii = sin_acentos(nombre_limpio)
    fila = db.execute(
        text(
            f"""
            SELECT s.id_sitio, s.nombre
            FROM turismo.sitio s
            WHERE s.activo = TRUE
              AND {_SQL_NORMALIZAR_NOMBRE_SITIO} = :nombre_ascii
            ORDER BY s.id_sitio ASC
            LIMIT 1
            """
        ),
        {"nombre_ascii": nombre_ascii},
    ).mappings().first()
    if not fila:
        return None

    return EntidadAsociadaHistorial(
        tipo="sitio",
        id=int(fila["id_sitio"]),
        nombre=str(fila["nombre"]),
    )


def _normalizar_tipo_filtro(
    tipo: str | None,
) -> Literal["general", "detalle", "todos"] | None:
    if tipo is None:
        return None
    valor = str(tipo).strip().lower()
    if valor in ("general", "detalle", "todos"):
        return valor  # type: ignore[return-value]
    if valor in ("sitio", "sitios"):
        return "detalle"
    return valor  # type: ignore[return-value]


def _resolver_ultimo_mensaje(
    db: Session, id_conversacion: int
) -> tuple[str | None, str | None, datetime | None]:
    consulta = text(
        """
        SELECT contenido, rol, creado_en
        FROM (
            SELECT contenido, rol, creado_en
            FROM conversacion.mensaje_explorador
            WHERE id_conversacion = :id_conversacion
            UNION ALL
            SELECT contenido, rol, creado_en
            FROM conversacion.mensaje_detalle
            WHERE id_conversacion = :id_conversacion
        ) AS union_mensajes
        ORDER BY creado_en DESC
        LIMIT 1
        """
    )
    fila = db.execute(
        consulta, {"id_conversacion": id_conversacion}
    ).mappings().first()
    if not fila:
        return None, None, None
    return fila["contenido"], fila["rol"], fila["creado_en"]


def _contar_por_tipo(
    db: Session, id_conversacion: int
) -> tuple[int, int, int]:
    consulta = text(
        """
        SELECT
            (SELECT COUNT(*) FROM conversacion.mensaje_explorador
             WHERE id_conversacion = :id_conversacion) AS total_explorador,
            (SELECT COUNT(*) FROM conversacion.mensaje_detalle
             WHERE id_conversacion = :id_conversacion) AS total_detalle
        """
    )
    fila = db.execute(
        consulta, {"id_conversacion": id_conversacion}
    ).mappings().first()
    total_explorador = int(fila["total_explorador"] or 0) if fila else 0
    total_detalle = int(fila["total_detalle"] or 0) if fila else 0
    return total_explorador + total_detalle, total_explorador, total_detalle


def _resolver_tipo_y_entidad(
    db: Session, id_conversacion: int
) -> tuple[TipoConversacion, EntidadAsociadaHistorial | None]:
    _, total_explorador, total_detalle = _contar_por_tipo(
        db, id_conversacion
    )
    if total_explorador > 0 and total_detalle == 0:
        tipo: TipoConversacion = "general"
    elif total_detalle > 0 and total_explorador == 0:
        tipo = "detalle"
    elif total_explorador > 0 and total_detalle > 0:
        tipo = "mixto"
    else:
        tipo = "general"

    entidad_asociada: EntidadAsociadaHistorial | None = None
    if total_detalle > 0:
        consulta = text(
            """
            SELECT entidad_asociada
            FROM conversacion.mensaje_detalle
            WHERE id_conversacion = :id_conversacion
              AND entidad_asociada IS NOT NULL
              AND entidad_asociada <> ''
            ORDER BY creado_en DESC
            LIMIT 1
            """
        )
        fila = db.execute(
            consulta, {"id_conversacion": id_conversacion}
        ).mappings().first()
        if fila:
            entidad_asociada = _resolver_entidad_sitio(
                db, fila["entidad_asociada"]
            )

    return tipo, entidad_asociada


def _verificar_propiedad(
    db: Session, id_usuario: int, id_conversacion: int
) -> bool:
    consulta = text(
        """
        SELECT 1
        FROM conversacion.conversacion
        WHERE id_conversacion = :id_conversacion
          AND id_usuario = :id_usuario
        LIMIT 1
        """
    )
    fila = db.execute(
        consulta,
        {"id_conversacion": id_conversacion, "id_usuario": id_usuario},
    ).mappings().first()
    return fila is not None


def listar_conversaciones(
    db: Session,
    id_usuario: int,
    tipo: TipoFiltroLista,
    limit: int,
    offset: int,
) -> dict:
    tipo_norm = _normalizar_tipo_filtro(tipo) or "todos"

    where_extra = ""
    params_base: dict = {"id_usuario": id_usuario}

    if tipo_norm == "general":
        where_extra = (
            " AND EXISTS (SELECT 1 FROM conversacion.mensaje_explorador ex "
            "             WHERE ex.id_conversacion = c.id_conversacion)"
        )
    elif tipo_norm == "detalle":
        where_extra = (
            " AND EXISTS (SELECT 1 FROM conversacion.mensaje_detalle pd "
            "             WHERE pd.id_conversacion = c.id_conversacion)"
        )

    consulta_total = text(
        f"""
        SELECT COUNT(*) AS total
        FROM conversacion.conversacion c
        WHERE c.id_usuario = :id_usuario{where_extra}
        """
    )
    total = int(
        db.execute(consulta_total, params_base).mappings().one()["total"]
    )

    consulta = text(
        f"""
        SELECT
            c.id_conversacion,
            c.sesion_id,
            c.titulo,
            (
                SELECT MAX(creado_en) FROM (
                    SELECT creado_en FROM conversacion.mensaje_explorador
                    WHERE id_conversacion = c.id_conversacion
                    UNION ALL
                    SELECT creado_en FROM conversacion.mensaje_detalle
                    WHERE id_conversacion = c.id_conversacion
                ) AS u
            ) AS ultimo_mensaje_en,
            (
                SELECT MIN(creado_en) FROM (
                    SELECT creado_en FROM conversacion.mensaje_explorador
                    WHERE id_conversacion = c.id_conversacion
                    UNION ALL
                    SELECT creado_en FROM conversacion.mensaje_detalle
                    WHERE id_conversacion = c.id_conversacion
                ) AS u
            ) AS creado_en
        FROM conversacion.conversacion c
        WHERE c.id_usuario = :id_usuario{where_extra}
        ORDER BY ultimo_mensaje_en DESC NULLS LAST, c.id_conversacion DESC
        LIMIT :limite OFFSET :desplazamiento
        """
    )
    params: dict = dict(params_base)
    params["limite"] = limit
    params["desplazamiento"] = offset
    filas = db.execute(consulta, params).mappings().all()

    items: list[dict] = []
    for fila in filas:
        id_conv = int(fila["id_conversacion"])
        ultimo_mensaje, ultimo_rol, ultimo_en = _resolver_ultimo_mensaje(
            db, id_conv
        )
        total_msj, _, _ = _contar_por_tipo(db, id_conv)
        tipo_conv, entidad = _resolver_tipo_y_entidad(db, id_conv)

        item: dict = {
            "id_conversacion": id_conv,
            "session_id": fila["sesion_id"],
            "titulo": entidad.nombre if entidad is not None else fila["titulo"],
            "tipo": tipo_conv,
            "ultimo_mensaje": ultimo_mensaje,
            "ultimo_rol": ultimo_rol,
            "ultimo_mensaje_en": ultimo_en,
            "creado_en": fila["creado_en"],
            "total_mensajes": total_msj,
        }
        if entidad is not None:
            item["entidad_asociada"] = entidad
        items.append(item)

    return {"items": items, "total": total}


def _obtener_mensajes_explorador(
    db: Session, id_conversacion: int, limit: int, offset: int
) -> list[dict]:
    consulta = text(
        """
        SELECT id_mensaje_ex AS id_mensaje,
               client_mensaje_id,
               rol,
               contenido,
               categoria,
               subcategoria,
               creado_en
        FROM conversacion.mensaje_explorador
        WHERE id_conversacion = :id_conversacion
        ORDER BY creado_en ASC, id_mensaje_ex ASC
        LIMIT :limite OFFSET :desplazamiento
        """
    )
    filas = db.execute(
        consulta,
        {
            "id_conversacion": id_conversacion,
            "limite": limit,
            "desplazamiento": offset,
        },
    ).mappings().all()
    return [
        {
            "id_mensaje": int(f["id_mensaje"]),
            "client_mensaje_id": f["client_mensaje_id"],
            "rol": f["rol"],
            "contenido": f["contenido"],
            "creado_en": f["creado_en"],
            "categoria": list(f["categoria"]) if f["categoria"] else None,
            "subcategoria": list(f["subcategoria"]) if f["subcategoria"] else None,
        }
        for f in filas
    ]


def _obtener_mensajes_detalle(
    db: Session, id_conversacion: int, limit: int, offset: int
) -> list[dict]:
    consulta = text(
        """
        SELECT id_mensaje_pd AS id_mensaje,
               client_mensaje_id,
               rol,
               contenido,
               entidad_asociada,
               creado_en
        FROM conversacion.mensaje_detalle
        WHERE id_conversacion = :id_conversacion
        ORDER BY creado_en ASC, id_mensaje_pd ASC
        LIMIT :limite OFFSET :desplazamiento
        """
    )
    filas = db.execute(
        consulta,
        {
            "id_conversacion": id_conversacion,
            "limite": limit,
            "desplazamiento": offset,
        },
    ).mappings().all()
    mensajes: list[dict] = []
    for f in filas:
        entidad = _resolver_entidad_sitio(db, f["entidad_asociada"])
        mensajes.append(
            {
                "id_mensaje": int(f["id_mensaje"]),
                "client_mensaje_id": f["client_mensaje_id"],
                "rol": f["rol"],
                "contenido": f["contenido"],
                "creado_en": f["creado_en"],
                "entidad_asociada": entidad,
            }
        )
    return mensajes


def obtener_mensajes(
    db: Session,
    id_usuario: int,
    id_conversacion: int,
    tipo: Literal["general", "detalle", "sitio"] | None,
    limit: int,
    offset: int,
):
    if not _verificar_propiedad(db, id_usuario, id_conversacion):
        return None

    fila_conv = db.execute(
        text(
            """
            SELECT id_conversacion, sesion_id, titulo
            FROM conversacion.conversacion
            WHERE id_conversacion = :id_conversacion
              AND id_usuario = :id_usuario
            """
        ),
        {"id_conversacion": id_conversacion, "id_usuario": id_usuario},
    ).mappings().first()

    if not fila_conv:
        return None

    _, total_explorador, total_detalle = _contar_por_tipo(
        db, id_conversacion
    )

    tipo_norm = _normalizar_tipo_filtro(tipo)
    tipo_resuelto: Literal["general", "detalle"]
    if tipo_norm in ("general", "detalle"):
        tipo_resuelto = tipo_norm
    else:
        if total_explorador > 0 and total_detalle == 0:
            tipo_resuelto = "general"
        elif total_detalle > 0 and total_explorador == 0:
            tipo_resuelto = "detalle"
        elif total_detalle > 0 and total_explorador > 0:
            fila_reciente = db.execute(
                text(
                    """
                    SELECT tipo, creado_en FROM (
                        SELECT 'general'::text AS tipo, creado_en
                        FROM conversacion.mensaje_explorador
                        WHERE id_conversacion = :id_conversacion
                        UNION ALL
                        SELECT 'detalle'::text AS tipo, creado_en
                        FROM conversacion.mensaje_detalle
                        WHERE id_conversacion = :id_conversacion
                    ) AS u
                    ORDER BY creado_en DESC
                    LIMIT 1
                    """
                ),
                {"id_conversacion": id_conversacion},
            ).mappings().first()
            tipo_resuelto = (
                fila_reciente["tipo"]
                if fila_reciente and fila_reciente["tipo"] in ("general", "detalle")
                else "general"
            )
        else:
            tipo_resuelto = "general"

    if tipo_resuelto == "general":
        mensajes = _obtener_mensajes_explorador(
            db, id_conversacion, limit, offset
        )
    else:
        mensajes = _obtener_mensajes_detalle(
            db, id_conversacion, limit, offset
        )

    _, entidad = _resolver_tipo_y_entidad(db, id_conversacion)

    respuesta: dict = {
        "id_conversacion": int(fila_conv["id_conversacion"]),
        "session_id": fila_conv["sesion_id"],
        "titulo": entidad.nombre if entidad is not None else fila_conv["titulo"],
        "tipo": tipo_resuelto,
        "creado_en": mensajes[0]["creado_en"] if mensajes else None,
        "mensajes": mensajes,
    }
    if entidad is not None:
        respuesta["entidad_asociada"] = entidad
    return respuesta