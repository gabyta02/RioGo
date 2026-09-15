import os
import shutil
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response, UploadFile, status
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.autenticacion.roles import es_rol_panel
from core.autenticacion.actividad_sesion import (
    crear_sesion_admin,
    expirar_sesion_admin_por_inactividad,
    limpiar_sesion_admin,
    limpiar_sesiones_admin_usuario,
    renovar_sesion_admin,
    segundos_inactividad_admin,
)
from core.autenticacion.encriptacion import encriptar_texto, verificar_texto
from core.autenticacion.renovacion_tokens import (
    crear_sesion_refresh,
    revocar_sesion_refresh,
    revocar_sesiones_usuario,
    rotar_refresh_token,
    validar_refresh_token,
)
from core.autenticacion.roles import rol_desde_cargo
from core.autenticacion.tokens import (
    crear_access_token,
    decodificar_token_tipo,
    segundos_access_token,
    segundos_token_refresh,
)
from core.infra.trazabilidad import (
    obtener_ip_request,
    obtener_user_agent_request,
    registrar_evento,
    registrar_inicio_sesion,
)
from core.reglas_seguridad import validar_correos_distintos_por_ip
from core.autenticacion.verificar_correo import (
    ErrorVerificacionCorreo,
    CODIGO_EXPIRA_MINUTOS,
    crear_token_verificacion_ficticio,
    enviar_codigo_verificacion,
    verificar_codigo_correo,
)
from core.correo import EnviarCorreoError, enviar_correo
from esquemas.autenticacion.autentificar import (
    FotoPerfilResponse,
    LoginRespuesta,
    SolicitudVerificacionCorreo,
    RecuperacionPasswordConfirmar,
    RecuperacionPasswordSolicitar,
    RecuperacionUsuarioSolicitar,
    UsuarioActualizar,
    UsuarioActualizar2FA,
    UsuarioEliminar,
    UsuarioLogin,
    UsuarioRegistroAdmin,
    UsuarioRegistroUsuario,
    UsuarioRespuesta,
    VerificacionCorreoRespuesta,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
REFRESH_COOKIE_PATH = os.getenv("REFRESH_COOKIE_PATH", "/api/v1/auth")
REFRESH_COOKIE_SECURE = os.getenv("REFRESH_COOKIE_SECURE", "true").lower() == "true"
REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", "lax")
REFRESH_COOKIE_MAX_AGE = int(os.getenv("REFRESH_COOKIE_MAX_AGE_SECONDS", str(365 * 24 * 60 * 60)))

PROFILE_IMAGES_DIR = Path("fuente_datos/imagenes/perfiles")
PROFILE_IMAGE_URL_PREFIX = "/api/v1/imagenes/perfiles"
MAX_PROFILE_PHOTO_BYTES = 2 * 1024 * 1024

_CAMPOS_USUARIO_PUBLICO = (
    "id_usuario",
    "id_rol",
    "id_cargo",
    "nombre_completo",
    "cargo_nombre",
    "username",
    "email",
    "rol",
    "activo",
    "autentificacion_doble",
    "actualizado_en",
    "ultimo_acceso_en",
)


def _cargo_desde_rol(rol: str) -> str:
    return "Super administrador" if rol == "super-admin" else "Usuario"


def _normalizar_usuario(usuario: dict) -> dict:
    resultado = dict(usuario)
    resultado["rol"] = rol_desde_cargo(resultado.get("cargo_nombre"))
    resultado["id_rol"] = resultado.get("id_cargo")
    return resultado


def _usuario_respuesta(usuario: dict) -> UsuarioRespuesta:
    return UsuarioRespuesta(**usuario)


def _usuario_publico(usuario: dict) -> dict:
    return {key: usuario[key] for key in _CAMPOS_USUARIO_PUBLICO if key in usuario}


def _buscar_usuario_por_username(db: Session, username: str) -> dict | None:
    fila = db.execute(
        text(
            """
            SELECT u.id_usuario, u.id_cargo, u.nombre_completo,
                   u.username, u.password, u.email, u.token, u.activo,
                   u.autentificacion_doble, u.actualizado_en, u.ultimo_acceso_en,
                   c.nombre AS cargo_nombre
            FROM conversacion.usuario u
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE u.username = :username
            """
        ),
        {"username": username},
    ).mappings().first()
    return _normalizar_usuario(dict(fila)) if fila else None


def _buscar_usuario_activo_por_username(db: Session, username: str) -> dict | None:
    usuario = _buscar_usuario_por_username(db, username)
    if not usuario or not usuario["activo"]:
        return None
    return usuario


def _buscar_usuario_activo_por_email(db: Session, email: str) -> dict | None:
    fila = db.execute(
        text(
            """
            SELECT u.id_usuario, u.id_cargo, u.nombre_completo,
                   u.username, u.password, u.email, u.token, u.activo,
                   u.autentificacion_doble, u.actualizado_en, u.ultimo_acceso_en,
                   c.nombre AS cargo_nombre
            FROM conversacion.usuario u
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE u.email = :email
              AND u.activo = TRUE
            """
        ),
        {"email": email},
    ).mappings().first()
    return _normalizar_usuario(dict(fila)) if fila else None


def _buscar_usuario_por_id(db: Session, id_usuario: int) -> dict | None:
    fila = db.execute(
        text(
            """
            SELECT u.id_usuario, u.id_cargo, u.nombre_completo,
                   u.username, u.password, u.email, u.token, u.activo,
                   u.autentificacion_doble, u.actualizado_en, u.ultimo_acceso_en,
                   c.nombre AS cargo_nombre
            FROM conversacion.usuario u
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE u.id_usuario = :id_usuario
            """
        ),
        {"id_usuario": id_usuario},
    ).mappings().first()
    return _normalizar_usuario(dict(fila)) if fila else None


def _cargar_todos_los_permisos(db: Session) -> list[str]:
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


def _cargar_permisos_panel(db: Session, usuario: dict) -> list[str]:
    if usuario["rol"] == "super-admin":
        return _cargar_todos_los_permisos(db)

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
            {"id_usuario": usuario["id_usuario"]},
        ).scalars().all()
    )


def _obtener_id_cargo(db: Session, nombre_cargo: str) -> int:
    fila = db.execute(
        text(
            """
            SELECT id_cargo
            FROM conversacion.cargo
            WHERE nombre = :nombre AND activo = TRUE
            """
        ),
        {"nombre": nombre_cargo},
    ).mappings().first()

    if not fila:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cargo '{nombre_cargo}' no configurado",
        )

    return int(fila["id_cargo"])


def _existe_username(db: Session, username: str, excluir_id: int | None = None) -> bool:
    consulta = """
        SELECT 1
        FROM conversacion.usuario
        WHERE username = :username
    """
    parametros = {"username": username}

    if excluir_id is not None:
        consulta += " AND id_usuario <> :excluir_id"
        parametros["excluir_id"] = excluir_id

    return db.execute(text(consulta), parametros).first() is not None


def _existe_email(db: Session, email: str, excluir_id: int | None = None) -> bool:
    consulta = """
        SELECT 1
        FROM conversacion.usuario
        WHERE email = :email
    """
    parametros = {"email": email}

    if excluir_id is not None:
        consulta += " AND id_usuario <> :excluir_id"
        parametros["excluir_id"] = excluir_id

    return db.execute(text(consulta), parametros).first() is not None


def _registrar_login(
    db: Session,
    *,
    usuario: dict | None,
    username: str,
    request: Request | None,
    resultado: str,
    detalle: str | None = None,
) -> None:
    registrar_inicio_sesion(
        db,
        id_usuario=usuario["id_usuario"] if usuario else None,
        username=usuario["username"] if usuario else username,
        ip=obtener_ip_request(request),
        user_agent=obtener_user_agent_request(request),
        resultado=resultado,
        detalle=detalle,
    )


def _validar_credenciales(
    db: Session,
    username: str,
    password: str,
    *,
    request: Request | None = None,
    auditar_login: bool = False,
) -> dict:
    usuario = _buscar_usuario_activo_por_username(db, username)

    if not usuario:
        if auditar_login:
            _registrar_login(
                db,
                usuario=None,
                username=username,
                request=request,
                resultado="fallido",
                detalle="Usuario inexistente o inactivo",
            )
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o password incorrectos",
        )

    if not verificar_texto(password, usuario["password"]):
        if auditar_login:
            _registrar_login(
                db,
                usuario=usuario,
                username=username,
                request=request,
                resultado="fallido",
                detalle="Password incorrecto",
            )
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o password incorrectos",
        )

    return usuario


def _error_verificacion(exc: ErrorVerificacionCorreo) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


def _verificar_correo(
    *,
    email: str,
    proposito: str,
    codigo: str | None,
    token: str | None,
) -> None:
    if not codigo or not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe enviar codigo_verificacion y token_verificacion",
        )

    try:
        verificar_codigo_correo(
            email=email,
            proposito=proposito,
            codigo=codigo,
            token_verificacion=token,
        )
    except ErrorVerificacionCorreo as exc:
        raise _error_verificacion(exc) from exc


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,
    )


def _limpiar_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
    )


def _login_respuesta(
    db: Session,
    usuario: dict,
    response: Response,
    *,
    request: Request | None = None,
    id_sesion: str | None = None,
    refresh_token: str | None = None,
    crear_admin_sesion: bool = True,
) -> LoginRespuesta:
    permisos = _cargar_permisos_panel(db, usuario)
    if not id_sesion or not refresh_token:
        id_sesion, refresh_token = crear_sesion_refresh(
            db,
            int(usuario["id_usuario"]),
            request,
        )
    access_token = crear_access_token(usuario, permisos, id_sesion)
    _set_refresh_cookie(response, refresh_token)
    usuario["ultimo_acceso_en"] = db.execute(text("SELECT NOW()")).scalar()

    admin_sesion_id = (
        crear_sesion_admin(int(usuario["id_usuario"]), id_sesion)
        if crear_admin_sesion and es_rol_panel(usuario["rol"])
        else None
    )

    return LoginRespuesta(
        rol=usuario["rol"],
        token=access_token,
        access_token=access_token,
        token_type="Bearer",
        expires_in=segundos_access_token(),
        token_refresh_in=segundos_token_refresh(),
        inactividad_max_segundos=segundos_inactividad_admin()
        if es_rol_panel(usuario["rol"])
        else None,
        id_sesion=id_sesion,
        admin_sesion_id=admin_sesion_id,
        permisos=permisos,
        usuario=_usuario_respuesta(_usuario_publico(usuario)),
    )


def solicitar_verificacion_correo(
    db: Session,
    datos: SolicitudVerificacionCorreo,
) -> VerificacionCorreoRespuesta:
    if datos.proposito == "registro_usuario":
        if not datos.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe enviar email para verificar un registro",
            )
        email_destino = str(datos.email)
    else:
        if not datos.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe enviar username para verificar esta operacion",
            )
        usuario = _buscar_usuario_activo_por_username(db, datos.username)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        if datos.proposito == "login_2fa" and not usuario["autentificacion_doble"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La verificacion por correo solo aplica a cuentas con autenticacion doble",
            )
        email_destino = usuario["email"]

    try:
        verificacion = enviar_codigo_verificacion(email_destino, datos.proposito)
    except ErrorVerificacionCorreo as exc:
        raise _error_verificacion(exc) from exc

    return VerificacionCorreoRespuesta(
        mensaje="Codigo de verificacion enviado",
        **verificacion,
    )


def solicitar_recuperacion_password(
    db: Session,
    datos: RecuperacionPasswordSolicitar,
) -> VerificacionCorreoRespuesta:
    email = str(datos.email)
    usuario = _buscar_usuario_activo_por_email(db, email)
    if usuario:
        try:
            verificacion = enviar_codigo_verificacion(email, "recuperar_password")
        except ErrorVerificacionCorreo:
            verificacion = {
                "token_verificacion": crear_token_verificacion_ficticio(
                    email,
                    "recuperar_password",
                ),
                "expira_en_minutos": CODIGO_EXPIRA_MINUTOS,
            }
    else:
        verificacion = {
            "token_verificacion": crear_token_verificacion_ficticio(
                email,
                "recuperar_password",
            ),
            "expira_en_minutos": CODIGO_EXPIRA_MINUTOS,
        }

    return VerificacionCorreoRespuesta(
        mensaje=(
            "Si el correo corresponde a una cuenta activa, enviaremos un codigo "
            "para continuar."
        ),
        **verificacion,
    )


def confirmar_recuperacion_password(
    db: Session,
    datos: RecuperacionPasswordConfirmar,
    request: Request | None = None,
) -> dict[str, str]:
    email = str(datos.email)
    usuario = _buscar_usuario_activo_por_email(db, email)
    if not usuario:
        _verificar_correo(
            email=email,
            proposito="recuperar_password",
            codigo=datos.codigo_verificacion,
            token=datos.token_verificacion,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo de verificacion invalido o expirado",
        )

    _verificar_correo(
        email=email,
        proposito="recuperar_password",
        codigo=datos.codigo_verificacion,
        token=datos.token_verificacion,
    )

    db.execute(
        text(
            """
            UPDATE conversacion.usuario
            SET password = :nuevo_password
            WHERE id_usuario = :id_usuario
            """
        ),
        {
            "nuevo_password": encriptar_texto(datos.nuevo_password),
            "id_usuario": usuario["id_usuario"],
        },
    )
    revocar_sesiones_usuario(db, int(usuario["id_usuario"]))
    if es_rol_panel(usuario["rol"]):
        limpiar_sesiones_admin_usuario(int(usuario["id_usuario"]))

    registrar_evento(
        db,
        username=usuario["username"],
        id_usuario=usuario["id_usuario"],
        ip=obtener_ip_request(request),
        accion="cambio_password",
        esquema_modificado="conversacion",
        tabla_modificada="usuario",
        entidad_modificada=usuario["id_usuario"],
        datos_anteriores={"password": "*****"},
        datos_nuevos={"password": "*****"},
    )

    db.commit()
    return {"mensaje": "Contrasena actualizada correctamente"}


def solicitar_recordatorio_usuario(
    db: Session,
    datos: RecuperacionUsuarioSolicitar,
    request: Request | None = None,
) -> dict[str, str]:
    email = str(datos.email)
    validar_correos_distintos_por_ip(
        regla="recordatorio_username",
        ip=obtener_ip_request(request),
        email=email,
    )

    usuario = _buscar_usuario_activo_por_email(db, email)
    if usuario:
        try:
            enviar_correo(
                "recordatorio_username",
                usuario["email"],
                {
                    "nombre_completo": usuario.get("nombre_completo"),
                    "username": usuario["username"],
                },
            )
        except EnviarCorreoError:
            pass

    return {
        "mensaje": (
            "Si el correo corresponde a una cuenta activa, enviaremos el nombre "
            "de usuario asociado."
        )
    }


def registrar_usuario(
    db: Session,
    datos: UsuarioRegistroUsuario | UsuarioRegistroAdmin,
    request: Request | None = None,
) -> UsuarioRespuesta:
    if datos.rol == "usuario":
        _verificar_correo(
            email=str(datos.email),
            proposito="registro_usuario",
            codigo=datos.codigo_verificacion,
            token=datos.token_verificacion,
        )

    if _existe_username(db, datos.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El username ya esta registrado",
        )

    if _existe_email(db, str(datos.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya esta registrado",
        )

    id_cargo = _obtener_id_cargo(db, _cargo_desde_rol(datos.rol))
    autentificacion_doble = datos.rol == "super-admin"

    fila = db.execute(
        text(
            """
            INSERT INTO conversacion.usuario (
                id_cargo, username, password, email, autentificacion_doble
            )
            VALUES (:id_cargo, :username, :password, :email, :autentificacion_doble)
            RETURNING id_usuario, id_cargo, username, email, activo,
                      autentificacion_doble, actualizado_en, ultimo_acceso_en
            """
        ),
        {
            "id_cargo": id_cargo,
            "username": datos.username,
            "password": encriptar_texto(datos.password),
            "email": str(datos.email),
            "autentificacion_doble": autentificacion_doble,
        },
    ).mappings().one()

    usuario = _normalizar_usuario({**dict(fila), "cargo_nombre": _cargo_desde_rol(datos.rol)})

    registrar_evento(
        db,
        username=datos.username,
        id_usuario=usuario["id_usuario"],
        ip=obtener_ip_request(request),
        accion="creacion_cuenta",
        esquema_modificado="conversacion",
        tabla_modificada="usuario",
        entidad_modificada=usuario["id_usuario"],
        datos_nuevos=_usuario_publico(usuario),
    )

    db.commit()
    return _usuario_respuesta(usuario)


def loguear_usuario(
    db: Session,
    datos: UsuarioLogin,
    response: Response,
    request: Request | None = None,
) -> LoginRespuesta:
    usuario = _validar_credenciales(
        db,
        datos.username,
        datos.password,
        request=request,
        auditar_login=True,
    )

    if usuario["autentificacion_doble"]:
        _verificar_correo(
            email=usuario["email"],
            proposito="login_2fa",
            codigo=datos.codigo_verificacion,
            token=datos.token_verificacion,
        )

    db.execute(
        text(
            """
            UPDATE conversacion.usuario
            SET ultimo_acceso_en = NOW()
            WHERE id_usuario = :id_usuario
            """
        ),
        {"id_usuario": usuario["id_usuario"]},
    )

    _registrar_login(
        db,
        usuario=usuario,
        username=usuario["username"],
        request=request,
        resultado="exitoso",
        detalle="Inicio de sesion exitoso",
    )

    respuesta = _login_respuesta(db, usuario, response, request=request)
    db.commit()
    return respuesta


def renovar_sesion(
    db: Session,
    refresh_token: str | None,
    response: Response,
) -> LoginRespuesta:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token requerido",
        )

    usuario_refresh = validar_refresh_token(db, refresh_token)
    usuario = _buscar_usuario_por_id(db, int(usuario_refresh["id_usuario"]))
    if not usuario or not usuario["activo"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autorizado",
        )

    refresh_nuevo = rotar_refresh_token(db, usuario_refresh["id_sesion"])
    respuesta = _login_respuesta(
        db,
        usuario,
        response,
        id_sesion=str(usuario_refresh["id_sesion"]),
        refresh_token=refresh_nuevo,
        crear_admin_sesion=False,
    )
    db.commit()
    return respuesta


def renovar_sesion_admin_panel(
    db: Session,
    usuario: dict,
    admin_sesion_id: str | None,
) -> dict[str, str | int]:
    if not es_rol_panel(usuario["rol"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )

    renovada = renovar_sesion_admin(
        admin_sesion_id,
        int(usuario["id_usuario"]),
        str(usuario["id_sesion"]),
    )
    if not renovada:
        expirar_sesion_admin_por_inactividad(
            db,
            int(usuario["id_usuario"]),
            str(usuario["id_sesion"]),
            admin_sesion_id,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion expirada por inactividad",
        )

    return {
        "mensaje": "Sesion administrativa renovada",
        "inactividad_max_segundos": segundos_inactividad_admin(),
    }


def cerrar_sesion(
    db: Session,
    token: str,
    response: Response,
    request: Request | None = None,
    admin_sesion_id: str | None = None,
) -> dict[str, str]:
    try:
        payload = decodificar_token_tipo(token, "access")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado",
        ) from exc

    id_usuario = int(payload["sub"])
    id_sesion = payload.get("sid")
    usuario = _buscar_usuario_por_id(db, id_usuario)
    revocar_sesion_refresh(db, id_sesion)
    limpiar_sesion_admin(admin_sesion_id)
    _limpiar_refresh_cookie(response)

    if usuario:
        registrar_evento(
            db,
            username=usuario["username"],
            id_usuario=usuario["id_usuario"],
            ip=obtener_ip_request(request),
            accion="logout",
            esquema_modificado="conversacion",
            tabla_modificada="usuario",
            entidad_modificada=usuario["id_usuario"],
            datos_nuevos={"username": usuario["username"]},
        )

    db.commit()
    return {"mensaje": "Sesion cerrada correctamente"}


def eliminar_cuenta(
    db: Session,
    datos: UsuarioEliminar,
    request: Request | None = None,
) -> dict[str, str]:
    usuario = _validar_credenciales(db, datos.username, datos.password)
    _verificar_correo(
        email=usuario["email"],
        proposito="eliminar_cuenta",
        codigo=datos.codigo_verificacion,
        token=datos.token_verificacion,
    )

    db.execute(
        text(
            """
            UPDATE conversacion.usuario
            SET activo = FALSE
            WHERE id_usuario = :id_usuario
            """
        ),
        {"id_usuario": usuario["id_usuario"]},
    )
    revocar_sesiones_usuario(db, int(usuario["id_usuario"]))
    limpiar_sesiones_admin_usuario(int(usuario["id_usuario"]))

    registrar_evento(
        db,
        username=usuario["username"],
        id_usuario=usuario["id_usuario"],
        ip=obtener_ip_request(request),
        accion="eliminacion_cuenta",
        esquema_modificado="conversacion",
        tabla_modificada="usuario",
        entidad_modificada=usuario["id_usuario"],
        datos_anteriores=_usuario_publico(usuario),
        datos_nuevos={"activo": False},
    )

    db.commit()
    return {"mensaje": "Cuenta eliminada correctamente"}


def actualizar_cuenta(
    db: Session,
    datos: UsuarioActualizar,
    request: Request | None = None,
) -> UsuarioRespuesta:
    usuario = _validar_credenciales(db, datos.username, datos.password)

    if not any([datos.nuevo_username, datos.nuevo_email, datos.nuevo_password]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe enviar al menos un campo para actualizar",
        )

    if datos.nuevo_email or datos.nuevo_password:
        _verificar_correo(
            email=usuario["email"],
            proposito="actualizar_credenciales",
            codigo=datos.codigo_verificacion,
            token=datos.token_verificacion,
        )

    if datos.nuevo_username and _existe_username(
        db,
        datos.nuevo_username,
        excluir_id=usuario["id_usuario"],
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nuevo username ya esta registrado",
        )

    if datos.nuevo_email and _existe_email(
        db,
        str(datos.nuevo_email),
        excluir_id=usuario["id_usuario"],
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nuevo email ya esta registrado",
        )

    usuario_actualizado = db.execute(
        text(
            """
            UPDATE conversacion.usuario
            SET username = COALESCE(:nuevo_username, username),
                email = COALESCE(:nuevo_email, email),
                password = COALESCE(:nuevo_password, password)
            WHERE id_usuario = :id_usuario
            RETURNING id_usuario, id_cargo, username, email, activo,
                      autentificacion_doble, actualizado_en, ultimo_acceso_en
            """
        ),
        {
            "nuevo_username": datos.nuevo_username,
            "nuevo_email": str(datos.nuevo_email) if datos.nuevo_email else None,
            "nuevo_password": encriptar_texto(datos.nuevo_password)
            if datos.nuevo_password
            else None,
            "id_usuario": usuario["id_usuario"],
        },
    ).mappings().one()

    usuario_nuevo = _normalizar_usuario(
        {
            **dict(usuario_actualizado),
            "cargo_nombre": usuario.get("cargo_nombre"),
            "nombre_completo": usuario.get("nombre_completo"),
        }
    )
    if datos.nuevo_password:
        revocar_sesiones_usuario(db, int(usuario["id_usuario"]))
        if es_rol_panel(usuario_nuevo["rol"]):
            limpiar_sesiones_admin_usuario(int(usuario["id_usuario"]))
    ip = obtener_ip_request(request)

    if datos.nuevo_username:
        registrar_evento(
            db,
            username=usuario["username"],
            id_usuario=usuario["id_usuario"],
            ip=ip,
            accion="cambio_username",
            esquema_modificado="conversacion",
            tabla_modificada="usuario",
            entidad_modificada=usuario["id_usuario"],
            datos_anteriores={"username": usuario["username"]},
            datos_nuevos={"username": usuario_nuevo["username"]},
        )

    if datos.nuevo_email:
        registrar_evento(
            db,
            username=usuario_nuevo["username"],
            id_usuario=usuario["id_usuario"],
            ip=ip,
            accion="cambio_email",
            esquema_modificado="conversacion",
            tabla_modificada="usuario",
            entidad_modificada=usuario["id_usuario"],
            datos_anteriores={"email": usuario["email"]},
            datos_nuevos={"email": usuario_nuevo["email"]},
        )

    if datos.nuevo_password:
        registrar_evento(
            db,
            username=usuario_nuevo["username"],
            id_usuario=usuario["id_usuario"],
            ip=ip,
            accion="cambio_password",
            esquema_modificado="conversacion",
            tabla_modificada="usuario",
            entidad_modificada=usuario["id_usuario"],
            datos_anteriores={"password": "*****"},
            datos_nuevos={"password": "*****"},
        )

    db.commit()
    return _usuario_respuesta(usuario_nuevo)


def _eliminar_foto_perfil_anterior(foto_url: str | None) -> None:
    if not foto_url or not foto_url.startswith(f"{PROFILE_IMAGE_URL_PREFIX}/"):
        return
    relative = foto_url.removeprefix(f"{PROFILE_IMAGE_URL_PREFIX}/").lstrip("/")
    path = (PROFILE_IMAGES_DIR / relative).resolve()
    base = PROFILE_IMAGES_DIR.resolve()
    if path.is_file() and str(path).startswith(str(base)):
        path.unlink()


def guardar_foto_perfil(
    db: Session,
    id_usuario: int,
    archivo: UploadFile,
    request: Request | None = None,
) -> FotoPerfilResponse:
    content_type = archivo.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos de imagen",
        )

    extension = Path(archivo.filename or "").suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png"}:
        extension = ".jpg"

    contenido = archivo.file.read()
    if len(contenido) > MAX_PROFILE_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen no puede superar 2 MB",
        )

    usuario = _buscar_usuario_por_id(db, id_usuario)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    _eliminar_foto_perfil_anterior(usuario.get("foto_url"))

    user_dir = PROFILE_IMAGES_DIR / str(id_usuario)
    user_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    destination = user_dir / filename
    with destination.open("wb") as buffer:
        buffer.write(contenido)

    foto_url = f"{PROFILE_IMAGE_URL_PREFIX}/{id_usuario}/{filename}"
    db.execute(
        text(
            """
            UPDATE conversacion.usuario
            SET foto_url = :foto_url
            WHERE id_usuario = :id_usuario
            """
        ),
        {"foto_url": foto_url, "id_usuario": id_usuario},
    )

    registrar_evento(
        db,
        username=usuario["username"],
        id_usuario=id_usuario,
        ip=obtener_ip_request(request),
        accion="cambio_foto_perfil",
        esquema_modificado="conversacion",
        tabla_modificada="usuario",
        entidad_modificada=id_usuario,
        datos_anteriores={"foto_url": usuario.get("foto_url")},
        datos_nuevos={"foto_url": foto_url},
    )
    db.commit()
    return FotoPerfilResponse(foto_url=foto_url)


def actualizar_autentificacion_doble(
    db: Session,
    datos: UsuarioActualizar2FA,
    request: Request | None = None,
) -> UsuarioRespuesta:
    usuario = _validar_credenciales(db, datos.username, datos.password)
    _verificar_correo(
        email=usuario["email"],
        proposito="actualizar_credenciales",
        codigo=datos.codigo_verificacion,
        token=datos.token_verificacion,
    )

    if bool(usuario["autentificacion_doble"]) == datos.autentificacion_doble:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La autenticacion en dos pasos ya tiene ese estado",
        )

    usuario_actualizado = db.execute(
        text(
            """
            UPDATE conversacion.usuario
            SET autentificacion_doble = :autentificacion_doble
            WHERE id_usuario = :id_usuario
            RETURNING id_usuario, id_cargo, username, email, activo,
                      autentificacion_doble, actualizado_en, ultimo_acceso_en
            """
        ),
        {
            "autentificacion_doble": datos.autentificacion_doble,
            "id_usuario": usuario["id_usuario"],
        },
    ).mappings().one()

    usuario_nuevo = _normalizar_usuario(
        {
            **dict(usuario_actualizado),
            "cargo_nombre": usuario.get("cargo_nombre"),
            "nombre_completo": usuario.get("nombre_completo"),
        }
    )

    registrar_evento(
        db,
        username=usuario_nuevo["username"],
        id_usuario=usuario["id_usuario"],
        ip=obtener_ip_request(request),
        accion="cambio_2fa",
        esquema_modificado="conversacion",
        tabla_modificada="usuario",
        entidad_modificada=usuario["id_usuario"],
        datos_anteriores={"autentificacion_doble": bool(usuario["autentificacion_doble"])},
        datos_nuevos={"autentificacion_doble": datos.autentificacion_doble},
    )
    db.commit()
    return _usuario_respuesta(usuario_nuevo)
