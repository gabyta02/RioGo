import secrets
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.autenticacion.encriptacion import hash_token_almacenado
from core.infra.trazabilidad import obtener_ip_request, obtener_user_agent_request


def _generar_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _cliente_desde_request(request: Request | None) -> str:
    if request is None:
        return "unknown"
    origen = (request.headers.get("x-client-type") or "").strip().lower()
    if origen in {"panel", "mobile", "web"}:
        return origen
    user_agent = (request.headers.get("user-agent") or "").lower()
    if "mozilla" in user_agent:
        return "web"
    return "unknown"


def crear_sesion_refresh(
    db: Session,
    id_usuario: int,
    request: Request | None = None,
) -> tuple[str, str]:
    refresh_token = _generar_refresh_token()
    fila = db.execute(
        text(
            """
            INSERT INTO conversacion.sesion_usuario (
                id_usuario, refresh_token_hash, cliente, ip, user_agent, ultimo_uso_en
            )
            VALUES (
                :id_usuario,
                :refresh_token_hash,
                :cliente,
                CAST(:ip AS INET),
                :user_agent,
                NOW()
            )
            RETURNING id_sesion
            """
        ),
        {
            "id_usuario": id_usuario,
            "refresh_token_hash": hash_token_almacenado(refresh_token),
            "cliente": _cliente_desde_request(request),
            "ip": obtener_ip_request(request),
            "user_agent": obtener_user_agent_request(request),
        },
    ).mappings().one()
    return str(fila["id_sesion"]), refresh_token


def emitir_y_guardar_refresh_token(
    db: Session,
    id_usuario: int,
    request: Request | None = None,
) -> str:
    _id_sesion, refresh_token = crear_sesion_refresh(db, id_usuario, request)
    return refresh_token


def obtener_sesion_activa(db: Session, id_sesion: str | UUID | None) -> dict | None:
    if not id_sesion:
        return None
    fila = db.execute(
        text(
            """
            SELECT su.id_sesion, su.id_usuario, su.activo, su.caducado,
                   su.revocado_en, u.username, u.email, u.activo AS usuario_activo,
                   c.nombre AS cargo_nombre
            FROM conversacion.sesion_usuario su
            JOIN conversacion.usuario u ON u.id_usuario = su.id_usuario
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE su.id_sesion = CAST(:id_sesion AS UUID)
            LIMIT 1
            """
        ),
        {"id_sesion": str(id_sesion)},
    ).mappings().first()
    if not fila:
        return None
    sesion = dict(fila)
    if (
        not sesion["activo"]
        or sesion["caducado"]
        or sesion["revocado_en"] is not None
        or not sesion["usuario_activo"]
    ):
        return None
    return sesion


def validar_refresh_token(db: Session, refresh_token: str) -> dict:
    token_hash = hash_token_almacenado(refresh_token)
    fila = db.execute(
        text(
            """
            SELECT su.id_sesion, su.id_usuario, su.activo, su.caducado,
                   su.revocado_en, u.username, u.email, u.activo AS usuario_activo,
                   c.nombre AS cargo_nombre
            FROM conversacion.sesion_usuario su
            JOIN conversacion.usuario u ON u.id_usuario = su.id_usuario
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE su.refresh_token_hash = :token_hash
            LIMIT 1
            """
        ),
        {"token_hash": token_hash},
    ).mappings().first()

    if not fila:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revocado",
        )

    sesion = dict(fila)
    if not sesion["usuario_activo"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autorizado",
        )
    if not sesion["activo"] or sesion["caducado"] or sesion["revocado_en"] is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revocado",
        )

    return sesion


def rotar_refresh_token(db: Session, id_sesion: str | UUID) -> str:
    refresh_token = _generar_refresh_token()
    db.execute(
        text(
            """
            UPDATE conversacion.sesion_usuario
            SET refresh_token_hash = :refresh_token_hash,
                ultimo_uso_en = NOW()
            WHERE id_sesion = CAST(:id_sesion AS UUID)
              AND activo = TRUE
              AND caducado = FALSE
              AND revocado_en IS NULL
            """
        ),
        {
            "id_sesion": str(id_sesion),
            "refresh_token_hash": hash_token_almacenado(refresh_token),
        },
    )
    return refresh_token


def revocar_sesion_refresh(db: Session, id_sesion: str | UUID | None) -> None:
    if not id_sesion:
        return
    db.execute(
        text(
            """
            UPDATE conversacion.sesion_usuario
            SET activo = FALSE,
                revocado_en = COALESCE(revocado_en, NOW())
            WHERE id_sesion = CAST(:id_sesion AS UUID)
            """
        ),
        {"id_sesion": str(id_sesion)},
    )


def revocar_refresh_token(db: Session, id_usuario: int) -> None:
    revocar_sesiones_usuario(db, id_usuario)


def revocar_sesiones_usuario(db: Session, id_usuario: int) -> None:
    db.execute(
        text(
            """
            UPDATE conversacion.sesion_usuario
            SET activo = FALSE,
                revocado_en = COALESCE(revocado_en, NOW())
            WHERE id_usuario = :id_usuario
              AND activo = TRUE
            """
        ),
        {"id_usuario": id_usuario},
    )
