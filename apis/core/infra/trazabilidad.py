import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import Request
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.autenticacion.tokens import decodificar_token_tipo

_CAMPOS_SENSIBLES = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "codigo_hash",
        "codigo_verificacion",
        "token_verificacion",
        "email",
        "email_nuevo",
    }
)

_ACCIONES_COMPATIBLES = {
    "registro_usuario": "creacion_cuenta",
    "creacion_cuenta_admin": "creacion_cuenta",
    "actualizacion_cuenta_admin": "actualizacion_cuenta",
    "actualizacion_sitios_cuenta_admin": "actualizacion_cuenta",
    "inactivacion_cuenta_admin": "inactivacion_cuenta",
    "eliminacion_cuenta_admin": "eliminacion_cuenta",
    "eliminacion_cuenta": "eliminacion_cuenta",
}


@dataclass(frozen=True, slots=True)
class ActorTrazabilidad:
    username: str
    id_usuario: int | None = None
    ip: str = "0.0.0.0"


ACTOR_SISTEMA = ActorTrazabilidad(username="sistema")


def obtener_ip_request(request: Request | None) -> str:
    if request is None:
        return "0.0.0.0"

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "0.0.0.0"

    return request.client.host if request.client else "0.0.0.0"


def obtener_user_agent_request(request: Request | None) -> str | None:
    if request is None:
        return None
    return request.headers.get("user-agent")


def _sanitizar_datos(datos: Any) -> Any:
    if datos is None:
        return None

    if isinstance(datos, dict):
        resultado: dict[str, Any] = {}
        for clave, valor in datos.items():
            if clave in _CAMPOS_SENSIBLES:
                resultado[clave] = "*****"
            else:
                resultado[clave] = _sanitizar_datos(valor)
        return resultado

    if isinstance(datos, list):
        return [_sanitizar_datos(item) for item in datos]

    if isinstance(datos, tuple):
        return [_sanitizar_datos(item) for item in datos]

    if isinstance(datos, (datetime, date, time)):
        return datos.isoformat()

    if isinstance(datos, Decimal):
        return float(datos)

    if isinstance(datos, UUID):
        return str(datos)

    return datos


def _jsonb(datos: dict[str, Any] | None) -> str | None:
    if datos is None:
        return None
    return json.dumps(_sanitizar_datos(datos), ensure_ascii=False)


def _normalizar_para_comparar(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {clave: _normalizar_para_comparar(valor[clave]) for clave in sorted(valor)}
    if isinstance(valor, list):
        return [_normalizar_para_comparar(item) for item in valor]
    if isinstance(valor, tuple):
        return [_normalizar_para_comparar(item) for item in valor]
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, UUID):
        return str(valor)
    return valor


def _solo_campos_modificados(
    datos_anteriores: dict[str, Any] | None,
    datos_nuevos: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not datos_anteriores or not datos_nuevos:
        return datos_anteriores, datos_nuevos

    anteriores: dict[str, Any] = {}
    nuevos: dict[str, Any] = {}
    claves = set(datos_anteriores) | set(datos_nuevos)
    for clave in claves:
        anterior = datos_anteriores.get(clave)
        nuevo = datos_nuevos.get(clave)
        if _normalizar_para_comparar(anterior) != _normalizar_para_comparar(nuevo):
            if clave in datos_anteriores:
                anteriores[clave] = anterior
            if clave in datos_nuevos:
                nuevos[clave] = nuevo

    return anteriores or None, nuevos or None


def preparar_datos_auditoria(
    accion: str,
    datos_anteriores: dict[str, Any] | None,
    datos_nuevos: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if accion in {"INSERT", "creacion_cuenta", "registro_usuario"}:
        return None, datos_nuevos
    if accion in {"DELETE", "eliminacion_cuenta"}:
        return datos_anteriores, None
    return _solo_campos_modificados(datos_anteriores, datos_nuevos)


def obtener_username_desde_authorization(authorization: str | None) -> str | None:
    if not authorization:
        return None

    partes = authorization.split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        return None

    try:
        payload = decodificar_token_tipo(partes[1], "access")
    except JWTError:
        return None

    username = payload.get("username")
    return str(username) if username else None


def registrar_inicio_sesion(
    db: Session,
    *,
    id_usuario: int | None,
    username: str,
    ip: str,
    user_agent: str | None,
    resultado: str,
    detalle: str | None = None,
) -> None:
    db.execute(
        text(
            """
            SELECT trazabilidad.fn_registrar_inicio_sesion(
                :id_usuario,
                :username,
                CAST(:ip AS INET),
                :user_agent,
                CAST(:resultado AS trazabilidad.resultado_t),
                :detalle
            )
            """
        ),
        {
            "id_usuario": id_usuario,
            "username": username,
            "ip": ip,
            "user_agent": user_agent,
            "resultado": resultado,
            "detalle": detalle,
        },
    )


def registrar_evento(
    db: Session,
    *,
    username: str,
    accion: str,
    esquema_modificado: str,
    tabla_modificada: str,
    entidad_modificada: str | int | None = None,
    datos_anteriores: dict[str, Any] | None = None,
    datos_nuevos: dict[str, Any] | None = None,
    referencia: str | None = None,
    id_usuario: int | None = None,
    ip: str = "0.0.0.0",
) -> None:
    accion_final = _ACCIONES_COMPATIBLES.get(accion, accion)
    datos_anteriores, datos_nuevos = preparar_datos_auditoria(
        accion_final,
        datos_anteriores,
        datos_nuevos,
    )

    db.execute(
        text(
            """
            SELECT trazabilidad.fn_registrar_accion(
                :id_usuario,
                :username,
                CAST(:ip AS INET),
                CAST(:accion AS trazabilidad.accion_t),
                :esquema_modificado,
                :tabla_modificada,
                :id_registro,
                :referencia,
                CAST(:datos_anteriores AS JSONB),
                CAST(:datos_nuevos AS JSONB)
            )
            """
        ),
        {
            "id_usuario": id_usuario,
            "username": username,
            "ip": ip,
            "accion": accion_final,
            "esquema_modificado": esquema_modificado,
            "tabla_modificada": tabla_modificada,
            "id_registro": str(entidad_modificada) if entidad_modificada is not None else None,
            "referencia": referencia,
            "datos_anteriores": _jsonb(datos_anteriores),
            "datos_nuevos": _jsonb(datos_nuevos),
        },
    )


def registrar_evento_actor(
    db: Session,
    actor: ActorTrazabilidad,
    *,
    accion: str,
    esquema_modificado: str,
    tabla_modificada: str,
    entidad_modificada: str | int | None = None,
    datos_anteriores: dict[str, Any] | None = None,
    datos_nuevos: dict[str, Any] | None = None,
    referencia: str | None = None,
) -> None:
    registrar_evento(
        db,
        username=actor.username,
        id_usuario=actor.id_usuario,
        ip=actor.ip,
        accion=accion,
        esquema_modificado=esquema_modificado,
        tabla_modificada=tabla_modificada,
        entidad_modificada=entidad_modificada,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        referencia=referencia,
    )
