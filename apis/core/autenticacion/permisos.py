from collections import defaultdict
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

PERMISOS_SITIO_DUENO: dict[str, tuple[str, ...]] = {
    "attractions": ("ver", "actualizar"),
    "chatbot_content": ("ver", "crear", "actualizar", "eliminar", "exportar"),
    "analytics": ("ver",),
}

ACCIONES_VALIDAS = frozenset({"ver", "crear", "actualizar", "eliminar", "exportar"})

MAPEO_ACCION: dict[str, str] = {
    "activar": "actualizar",
    "desactivar": "actualizar",
    "aprobar": "actualizar",
    "generar_chunks": "exportar",
    "generar_secciones": "actualizar",
}


def normalizar_accion(accion: str) -> str:
    accion_lower = (accion or "").strip().lower()
    return MAPEO_ACCION.get(accion_lower, accion_lower)


def _es_super_admin(usuario: dict) -> bool:
    return usuario.get("rol") == "super-admin"


def _id_usuario(usuario: dict) -> int:
    return int(usuario["id_usuario"])


def _normalizar_nombre(value: str | None) -> str:
    texto = unicodedata.normalize("NFD", value or "")
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")
    return texto.strip().lower()


def _es_dueno(usuario: dict) -> bool:
    return _normalizar_nombre(usuario.get("cargo_nombre")) == "dueno"


def cargar_modulos_usuario(db: Session, usuario: dict) -> list[str]:
    if _es_super_admin(usuario):
        return list(
            db.execute(
                text(
                    """
                    SELECT codigo
                    FROM conversacion.modulo
                    WHERE activo = TRUE
                    ORDER BY codigo
                    """
                )
            ).scalars().all()
        )

    return list(
        db.execute(
            text(
                """
                SELECT DISTINCT m.codigo
                FROM conversacion.usuario_permiso up
                JOIN conversacion.modulo m ON m.id_modulo = up.id_modulo
                WHERE up.id_usuario = :id_usuario
                  AND m.activo = TRUE
                ORDER BY m.codigo
                """
            ),
            {"id_usuario": _id_usuario(usuario)},
        ).scalars().all()
    )


def tiene_permiso_modulo_accion(
    db: Session,
    usuario: dict,
    codigo_modulo: str,
    accion: str,
) -> bool:
    if _es_super_admin(usuario):
        return True

    accion_norm = normalizar_accion(accion)
    if accion_norm not in ACCIONES_VALIDAS:
        return False

    return (
        db.execute(
            text(
                """
                SELECT 1
                FROM conversacion.usuario_permiso up
                JOIN conversacion.modulo m ON m.id_modulo = up.id_modulo
                WHERE up.id_usuario = :id_usuario
                  AND m.codigo = :codigo_modulo
                  AND up.accion = CAST(:accion AS conversacion.accion_t)
                  AND m.activo = TRUE
                """
            ),
            {
                "id_usuario": _id_usuario(usuario),
                "codigo_modulo": codigo_modulo,
                "accion": accion_norm,
            },
        ).first()
        is not None
    )


def obtener_sitios_permitidos(
    db: Session,
    usuario: dict,
    codigo_modulo: str,
    accion: str,
) -> list[int] | None:
    if _es_super_admin(usuario):
        return None

    accion_norm = normalizar_accion(accion)
    if accion_norm not in ACCIONES_VALIDAS:
        return []

    if _es_dueno(usuario):
        return cargar_sitios_asignados(db, _id_usuario(usuario))

    params = {
        "id_usuario": _id_usuario(usuario),
        "codigo_modulo": codigo_modulo,
        "accion": accion_norm,
    }

    acceso_global = db.execute(
        text(
            """
            SELECT 1
            FROM conversacion.usuario_permiso up
            JOIN conversacion.modulo m ON m.id_modulo = up.id_modulo
            WHERE up.id_usuario = :id_usuario
              AND m.codigo = :codigo_modulo
              AND up.accion = CAST(:accion AS conversacion.accion_t)
              AND up.id_sitio IS NULL
              AND m.activo = TRUE
            """
        ),
        params,
    ).first()

    if acceso_global:
        return None

    sitios = db.execute(
        text(
            """
            SELECT DISTINCT up.id_sitio
            FROM conversacion.usuario_permiso up
            JOIN conversacion.modulo m ON m.id_modulo = up.id_modulo
            WHERE up.id_usuario = :id_usuario
              AND m.codigo = :codigo_modulo
              AND up.accion = CAST(:accion AS conversacion.accion_t)
              AND up.id_sitio IS NOT NULL
              AND m.activo = TRUE
            ORDER BY up.id_sitio
            """
        ),
        params,
    ).scalars().all()

    return [int(sitio) for sitio in sitios]


def validar_acceso_sitio(
    db: Session,
    usuario: dict,
    id_sitio: int,
    codigo_modulo: str,
    accion: str,
) -> None:
    sitios = obtener_sitios_permitidos(db, usuario, codigo_modulo, accion)
    if sitios is None:
        return
    if int(id_sitio) not in sitios:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )


def validar_acceso_vinculo(
    db: Session,
    usuario: dict,
    origen: str,
    id_vinculo: int,
    codigo_modulo: str,
    accion: str,
) -> None:
    if origen == "sitio":
        validar_acceso_sitio(db, usuario, id_vinculo, codigo_modulo, accion)
        return

    sitios = obtener_sitios_permitidos(db, usuario, codigo_modulo, accion)
    if sitios is None:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acceso denegado",
    )


def aplicar_filtro_sitios_sql(
    sitios_permitidos: list[int] | None,
    alias: str = "s",
) -> tuple[str, dict]:
    if sitios_permitidos is None:
        return "", {}
    if not sitios_permitidos:
        return " AND 1=0", {}
    return (
        f" AND {alias}.id_sitio = ANY(:sitios_permitidos)",
        {"sitios_permitidos": sitios_permitidos},
    )


def cargar_sitios_asignados(db: Session, id_usuario: int) -> list[int]:
    return [
        int(sitio)
        for sitio in db.execute(
            text(
                """
                SELECT DISTINCT id_sitio
                FROM conversacion.usuario_permiso
                WHERE id_usuario = :id_usuario
                  AND id_sitio IS NOT NULL
                ORDER BY id_sitio
                """
            ),
            {"id_usuario": id_usuario},
        ).scalars().all()
    ]


def cargar_permisos_enriquecidos(db: Session, usuario: dict) -> list[dict]:
    if _es_super_admin(usuario):
        modulos = db.execute(
            text(
                """
                SELECT codigo
                FROM conversacion.modulo
                WHERE activo = TRUE
                ORDER BY codigo
                """
            )
        ).scalars().all()
        return [
            {
                "modulo": codigo,
                "acciones": sorted(ACCIONES_VALIDAS),
                "alcance": "global",
            }
            for codigo in modulos
        ]

    filas = db.execute(
        text(
            """
            SELECT m.codigo AS modulo,
                   up.accion::TEXT AS accion,
                   up.id_sitio
            FROM conversacion.usuario_permiso up
            JOIN conversacion.modulo m ON m.id_modulo = up.id_modulo
            WHERE up.id_usuario = :id_usuario
              AND m.activo = TRUE
            ORDER BY m.codigo, up.accion, up.id_sitio NULLS FIRST
            """
        ),
        {"id_usuario": _id_usuario(usuario)},
    ).mappings().all()

    por_modulo: dict[str, dict] = {}
    for fila in filas:
        modulo = fila["modulo"]
        accion = fila["accion"]
        id_sitio = fila["id_sitio"]

        if modulo not in por_modulo:
            por_modulo[modulo] = {
                "acciones_globales": set(),
                "acciones_sitio": defaultdict(set),
                "sitios": set(),
            }

        entrada = por_modulo[modulo]
        if id_sitio is None:
            entrada["acciones_globales"].add(accion)
        else:
            sitio_id = int(id_sitio)
            entrada["sitios"].add(sitio_id)
            entrada["acciones_sitio"][sitio_id].add(accion)

    resultado: list[dict] = []
    for modulo in sorted(por_modulo):
        entrada = por_modulo[modulo]
        sitios = sorted(entrada["sitios"])
        acciones_globales = entrada["acciones_globales"]
        acciones_sitio = entrada["acciones_sitio"]

        if acciones_globales:
            resultado.append(
                {
                    "modulo": modulo,
                    "acciones": sorted(acciones_globales),
                    "alcance": "global",
                }
            )
            continue

        if not sitios:
            continue

        acciones_union: set[str] = set()
        for sitio_id in sitios:
            acciones_union.update(acciones_sitio.get(sitio_id, set()))

        resultado.append(
            {
                "modulo": modulo,
                "acciones": sorted(acciones_union),
                "alcance": "sitio",
                "sitios": sitios,
            }
        )

    return resultado


def _obtener_id_modulo(db: Session, codigo: str) -> int | None:
    fila = db.execute(
        text(
            """
            SELECT id_modulo
            FROM conversacion.modulo
            WHERE codigo = :codigo AND activo = TRUE
            """
        ),
        {"codigo": codigo},
    ).scalar()
    return int(fila) if fila is not None else None


def insertar_permisos_sitio_dueno(
    db: Session,
    id_usuario: int,
    id_sitio: int,
) -> None:
    for codigo_modulo, acciones in PERMISOS_SITIO_DUENO.items():
        id_modulo = _obtener_id_modulo(db, codigo_modulo)
        if id_modulo is None:
            continue
        for accion in acciones:
            db.execute(
                text(
                    """
                    INSERT INTO conversacion.usuario_permiso
                        (id_usuario, id_modulo, accion, id_sitio)
                    VALUES (
                        :id_usuario,
                        :id_modulo,
                        CAST(:accion AS conversacion.accion_t),
                        :id_sitio
                    )
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "id_usuario": id_usuario,
                    "id_modulo": id_modulo,
                    "accion": accion,
                    "id_sitio": id_sitio,
                },
            )


def reemplazar_sitios_usuario(
    db: Session,
    id_usuario: int,
    sitios: list[int],
) -> None:
    db.execute(
        text(
            """
            DELETE FROM conversacion.usuario_permiso
            WHERE id_usuario = :id_usuario
              AND id_sitio IS NOT NULL
            """
        ),
        {"id_usuario": id_usuario},
    )

    for id_sitio in sitios:
        insertar_permisos_sitio_dueno(db, id_usuario, int(id_sitio))


def sincronizar_permisos_sitio_dueno(db: Session, usuario: dict) -> None:
    if _es_super_admin(usuario) or not _es_dueno(usuario):
        return
    sitios = cargar_sitios_asignados(db, _id_usuario(usuario))
    if not sitios:
        return
    for id_sitio in sitios:
        insertar_permisos_sitio_dueno(db, _id_usuario(usuario), int(id_sitio))
    db.commit()
