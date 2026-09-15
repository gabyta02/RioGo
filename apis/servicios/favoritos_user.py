from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.imagenes import normalizar_url_imagen


def _obtener_sitio(db: Session, id_sitio: int) -> Optional[dict]:
    consulta = text(
        """
        SELECT s.id_sitio, s.nombre, s.descripcion_corta, s.ubicacion,
               c.nombre AS categoria,
               sc.nombre AS subcategoria
        FROM turismo.sitio s
        LEFT JOIN turismo.categoria c ON c.id_categoria = s.id_categoria
        LEFT JOIN turismo.subcategoria sc ON sc.id_subcategoria = s.id_subcategoria
        WHERE s.id_sitio = :id_sitio AND s.activo = TRUE
        """
    )
    return db.execute(consulta, {"id_sitio": id_sitio}).mappings().first()


def _obtener_imagen_principal(db: Session, id_sitio: int) -> Optional[str]:
    consulta = text(
        """
        SELECT url
        FROM turismo.multimedia
        WHERE id_sitio = :id_sitio AND activo = TRUE
        ORDER BY es_principal DESC NULLS LAST, id_multimedia ASC
        LIMIT 1
        """
    )
    fila = db.execute(consulta, {"id_sitio": id_sitio}).mappings().first()
    return normalizar_url_imagen(fila["url"] if fila else None)


def verificar_sitio_existe(db: Session, id_sitio: int) -> bool:
    sitio = _obtener_sitio(db, id_sitio)
    return sitio is not None


def verificar_estado_favorito(db: Session, id_usuario: int, id_sitio: int) -> bool:
    consulta = text(
        """
        SELECT 1
        FROM conversacion.favorito
        WHERE id_usuario = :id_usuario AND id_sitio = :id_sitio
        """
    )
    fila = db.execute(consulta, {"id_usuario": id_usuario, "id_sitio": id_sitio}).mappings().first()
    return fila is not None


def agregar_favorito(db: Session, id_usuario: int, id_sitio: int) -> dict:
    sitio = _obtener_sitio(db, id_sitio)
    if not sitio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sitio no encontrado",
        )

    existente = verificar_estado_favorito(db, id_usuario, id_sitio)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El sitio ya esta en favoritos",
        )

    db.execute(
        text(
            """
            INSERT INTO conversacion.favorito (id_usuario, id_sitio)
            VALUES (:id_usuario, :id_sitio)
            RETURNING id_favorito
            """
        ),
        {"id_usuario": id_usuario, "id_sitio": id_sitio},
    )
    db.commit()

    return {
        "message": "Sitio agregado a favoritos correctamente",
        "id_sitio": id_sitio,
        "es_favorito": True,
    }


def _extraer_coordenadas(db: Session, id_sitio: int) -> Optional[dict]:
    consulta = text(
        """
        SELECT ST_AsText(ubicacion) AS coords
        FROM turismo.sitio
        WHERE id_sitio = :id_sitio AND ubicacion IS NOT NULL
        """
    )
    fila = db.execute(consulta, {"id_sitio": id_sitio}).mappings().first()
    if not fila or not fila["coords"]:
        return None

    coords = fila["coords"]
    if coords.startswith("POINT(") and coords.endswith(")"):
        partes = coords[6:-1].split()
        if len(partes) == 2:
            try:
                return {
                    "longitud": float(partes[0]),
                    "latitud": float(partes[1]),
                }
            except (ValueError, IndexError):
                pass
    return None


def listar_favoritos(db: Session, id_usuario: int) -> dict:
    consulta = text(
        """
        SELECT f.id_favorito, f.id_sitio, f.creado_en,
               s.nombre, s.descripcion_corta,
               c.nombre AS categoria,
               sc.nombre AS subcategoria
        FROM conversacion.favorito f
        JOIN turismo.sitio s ON s.id_sitio = f.id_sitio
        LEFT JOIN turismo.categoria c ON c.id_categoria = s.id_categoria
        LEFT JOIN turismo.subcategoria sc ON sc.id_subcategoria = s.id_subcategoria
        WHERE f.id_usuario = :id_usuario AND s.activo = TRUE
        ORDER BY f.creado_en DESC
        """
    )
    filas = db.execute(consulta, {"id_usuario": id_usuario}).mappings().all()

    favoritos = []
    for fila in filas:
        imagen = _obtener_imagen_principal(db, fila["id_sitio"])
        ubicacion = _extraer_coordenadas(db, fila["id_sitio"])

        favoritos.append({
            "id_favorito": fila["id_favorito"],
            "id_sitio": fila["id_sitio"],
            "nombre": fila["nombre"],
            "categoria": fila["categoria"] or "Sin categoría",
            "subcategoria": fila["subcategoria"] or "Sin subcategoría",
            "descripcion_corta": fila["descripcion_corta"],
            "imagen_principal": imagen,
            "ubicacion": ubicacion,
            "fecha_agregado": fila["creado_en"],
        })

    return {
        "total": len(favoritos),
        "favoritos": favoritos,
    }


def eliminar_favorito(db: Session, id_usuario: int, id_sitio: int) -> dict:
    consulta = text(
        """
        DELETE FROM conversacion.favorito
        WHERE id_usuario = :id_usuario AND id_sitio = :id_sitio
        RETURNING id_favorito
        """
    )
    resultado = db.execute(consulta, {"id_usuario": id_usuario, "id_sitio": id_sitio})
    fila = resultado.mappings().first()

    if not fila:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorito no encontrado",
        )

    db.commit()

    return {
        "message": "Sitio eliminado de favoritos correctamente",
        "id_sitio": id_sitio,
        "es_favorito": False,
    }