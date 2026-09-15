from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.autenticacion.actividad_sesion import (
    expirar_sesion_admin_por_inactividad,
    validar_sesion_admin,
)
from core.autenticacion.renovacion_tokens import obtener_sesion_activa
from core.infra.conexion import obtener_sesion
from core.autenticacion.permisos import (
    cargar_modulos_usuario,
    cargar_permisos_enriquecidos,
    cargar_sitios_asignados,
    sincronizar_permisos_sitio_dueno,
    tiene_permiso_modulo_accion,
)
from core.autenticacion.roles import ROLES_PANEL, rol_desde_cargo
from core.autenticacion.tokens import decodificar_token_tipo
from core.infra.trazabilidad import ActorTrazabilidad, obtener_ip_request


def _extraer_token_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
        )

    partes = authorization.split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
        )

    return partes[1]


def obtener_token_bearer(authorization: str | None = Header(default=None)) -> str:
    return _extraer_token_bearer(authorization)


def _enriquecer_usuario_panel(db: Session, usuario: dict) -> dict:
    resultado = dict(usuario)
    sincronizar_permisos_sitio_dueno(db, resultado)
    resultado["permisos"] = cargar_modulos_usuario(db, resultado)
    resultado["permisos_detalle"] = cargar_permisos_enriquecidos(db, resultado)
    resultado["sitios_asignados"] = cargar_sitios_asignados(db, int(resultado["id_usuario"]))
    return resultado


def requerir_usuario_autenticado(
    db: Session = Depends(obtener_sesion),
    token: str = Depends(obtener_token_bearer),
) -> dict:
    try:
        payload = decodificar_token_tipo(token, "access")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado",
        ) from exc

    id_usuario = payload.get("sub")
    if not id_usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
        )

    id_sesion = payload.get("sid")
    if not obtener_sesion_activa(db, id_sesion):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion revocada",
        )

    usuario = db.execute(
        text(
            """
            SELECT u.id_usuario, u.id_cargo, u.nombre_completo,
                   u.username, u.email, u.activo, u.foto_url,
                   u.autentificacion_doble, u.actualizado_en, u.ultimo_acceso_en,
                   c.nombre AS cargo_nombre
            FROM conversacion.usuario u
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE u.id_usuario = :id_usuario
            """
        ),
        {"id_usuario": int(id_usuario)},
    ).mappings().first()

    if not usuario or not usuario["activo"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autorizado",
        )

    resultado = dict(usuario)
    resultado["rol"] = rol_desde_cargo(resultado.get("cargo_nombre"))
    resultado["id_rol"] = resultado.get("id_cargo")
    resultado["id_sesion"] = str(id_sesion)

    return resultado


def requerir_usuario_panel(
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
    x_admin_session_id: str | None = Header(default=None, alias="X-Admin-Session-Id"),
) -> dict:
    if usuario["rol"] not in ROLES_PANEL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )
    if not x_admin_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion administrativa requerida",
        )
    if not validar_sesion_admin(
        x_admin_session_id,
        int(usuario["id_usuario"]),
        str(usuario["id_sesion"]),
    ):
        expirar_sesion_admin_por_inactividad(
            db,
            int(usuario["id_usuario"]),
            str(usuario["id_sesion"]),
            x_admin_session_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion expirada por inactividad",
        )
    return _enriquecer_usuario_panel(db, usuario)


def requerir_super_admin(
    usuario: dict = Depends(requerir_usuario_panel),
) -> dict:
    if usuario["rol"] != "super-admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )
    return usuario


def requerir_permiso(codigo: str, accion: str = "ver") -> Callable:
    def _dependencia(
        db: Session = Depends(obtener_sesion),
        usuario: dict = Depends(requerir_usuario_panel),
    ) -> dict:
        if usuario["rol"] == "super-admin":
            return usuario
        if codigo not in usuario.get("permisos", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado",
            )
        if not tiene_permiso_modulo_accion(db, usuario, codigo, accion):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado",
            )
        return usuario

    return _dependencia


def requerir_permiso_cualquiera(*permisos: tuple[str, str]) -> Callable:
    def _dependencia(
        db: Session = Depends(obtener_sesion),
        usuario: dict = Depends(requerir_usuario_panel),
    ) -> dict:
        if usuario["rol"] == "super-admin":
            return usuario
        for codigo, accion in permisos:
            if codigo not in usuario.get("permisos", []):
                continue
            if tiene_permiso_modulo_accion(db, usuario, codigo, accion):
                return usuario
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    return _dependencia


def obtener_actor(
    request: Request,
    usuario: dict = Depends(requerir_usuario_panel),
) -> ActorTrazabilidad:
    return ActorTrazabilidad(
        id_usuario=int(usuario["id_usuario"]),
        username=usuario["username"],
        ip=obtener_ip_request(request),
    )


def obtener_usuario_me(
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
) -> dict:
    if usuario["rol"] in ROLES_PANEL:
        return _enriquecer_usuario_panel(db, usuario)
    return usuario
