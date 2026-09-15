from fastapi import APIRouter, Cookie, Depends, File, Header, Request, Response, UploadFile
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import (
    obtener_token_bearer,
    obtener_usuario_me,
    requerir_usuario_autenticado,
)
from esquemas.autenticacion.autentificar import (
    FotoPerfilResponse,
    LoginRespuesta,
    MensajeRespuesta,
    PermisoModuloResponse,
    RecuperacionPasswordConfirmar,
    RecuperacionPasswordSolicitar,
    RecuperacionUsuarioSolicitar,
    SolicitudVerificacionCorreo,
    UsuarioActualizar,
    UsuarioActualizar2FA,
    UsuarioEliminar,
    UsuarioLogin,
    UsuarioMeResponse,
    UsuarioRegistroAdmin,
    UsuarioRegistroUsuario,
    UsuarioRespuesta,
    VerificacionCorreoRespuesta,
)
from servicios.autenticacion.autentificar import (
    actualizar_autentificacion_doble,
    actualizar_cuenta,
    cerrar_sesion,
    confirmar_recuperacion_password,
    eliminar_cuenta,
    guardar_foto_perfil,
    loguear_usuario,
    renovar_sesion_admin_panel,
    renovar_sesion,
    registrar_usuario,
    solicitar_recuperacion_password,
    solicitar_recordatorio_usuario,
    solicitar_verificacion_correo,
    REFRESH_COOKIE_NAME,
)

router = APIRouter(prefix="/auth", tags=["Autenticacion"])


@router.post("/correo/verificacion", response_model=VerificacionCorreoRespuesta)
def solicitar_codigo_correo(
    datos: SolicitudVerificacionCorreo,
    db: Session = Depends(obtener_sesion),
):
    return solicitar_verificacion_correo(db, datos)


@router.post("/correo/reenviar", response_model=VerificacionCorreoRespuesta)
def reenviar_codigo_correo(
    datos: SolicitudVerificacionCorreo,
    db: Session = Depends(obtener_sesion),
):
    return solicitar_verificacion_correo(db, datos)


@router.post(
    "/recuperacion/password/solicitar",
    response_model=VerificacionCorreoRespuesta,
)
def solicitar_codigo_recuperacion_password(
    datos: RecuperacionPasswordSolicitar,
    db: Session = Depends(obtener_sesion),
):
    return solicitar_recuperacion_password(db, datos)


@router.post("/recuperacion/password/confirmar", response_model=MensajeRespuesta)
def confirmar_password_recuperacion(
    datos: RecuperacionPasswordConfirmar,
    request: Request,
    db: Session = Depends(obtener_sesion),
):
    return confirmar_recuperacion_password(db, datos, request)


@router.post("/recuperacion/usuario/solicitar", response_model=MensajeRespuesta)
def solicitar_usuario_por_correo(
    datos: RecuperacionUsuarioSolicitar,
    request: Request,
    db: Session = Depends(obtener_sesion),
):
    return solicitar_recordatorio_usuario(db, datos, request)


@router.post(
    "/registro/usuario",
    response_model=UsuarioRespuesta,
    status_code=201,
)
def registrar_usuario_regular(
    datos: UsuarioRegistroUsuario,
    request: Request,
    db: Session = Depends(obtener_sesion),
):
    return registrar_usuario(db, datos, request)


@router.post(
    "/registro/admin",
    response_model=UsuarioRespuesta,
    status_code=201,
)
def registrar_usuario_admin(
    datos: UsuarioRegistroAdmin,
    request: Request,
    db: Session = Depends(obtener_sesion),
):
    return registrar_usuario(db, datos, request)


@router.post("/login", response_model=LoginRespuesta)
def login(
    datos: UsuarioLogin,
    request: Request,
    response: Response,
    db: Session = Depends(obtener_sesion),
):
    return loguear_usuario(db, datos, response, request)


@router.post("/refresh", response_model=LoginRespuesta)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(obtener_sesion),
):
    return renovar_sesion(db, refresh_token, response)


@router.post("/admin-session/refresh", response_model=MensajeRespuesta)
def refresh_admin_session(
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
    x_admin_session_id: str | None = Header(default=None, alias="X-Admin-Session-Id"),
):
    return renovar_sesion_admin_panel(db, usuario, x_admin_session_id)


@router.post("/logout", response_model=MensajeRespuesta)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(obtener_sesion),
    token: str = Depends(obtener_token_bearer),
    x_admin_session_id: str | None = Header(default=None, alias="X-Admin-Session-Id"),
):
    return cerrar_sesion(db, token, response, request, x_admin_session_id)


@router.delete("/cuenta", response_model=MensajeRespuesta)
def borrar_cuenta(
    datos: UsuarioEliminar,
    request: Request,
    db: Session = Depends(obtener_sesion),
):
    return eliminar_cuenta(db, datos, request)


@router.patch("/cuenta", response_model=UsuarioRespuesta)
def actualizar_usuario(
    datos: UsuarioActualizar,
    request: Request,
    db: Session = Depends(obtener_sesion),
):
    return actualizar_cuenta(db, datos, request)


@router.patch("/cuenta/2fa", response_model=UsuarioRespuesta)
def actualizar_2fa_usuario(
    datos: UsuarioActualizar2FA,
    request: Request,
    db: Session = Depends(obtener_sesion),
):
    return actualizar_autentificacion_doble(db, datos, request)


@router.post("/cuenta/foto", response_model=FotoPerfilResponse)
def subir_foto_perfil(
    request: Request,
    archivo: UploadFile = File(...),
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
):
    return guardar_foto_perfil(db, int(usuario["id_usuario"]), archivo, request)


@router.get("/me", response_model=UsuarioMeResponse)
def me(usuario_actual: dict = Depends(obtener_usuario_me)):
    permisos = usuario_actual.get("permisos_detalle") or []
    return UsuarioMeResponse(
        id_usuario=int(usuario_actual["id_usuario"]),
        username=usuario_actual["username"],
        email=usuario_actual["email"],
        nombre_completo=usuario_actual.get("nombre_completo"),
        rol=usuario_actual["rol"],
        cargo_nombre=usuario_actual.get("cargo_nombre"),
        activo=bool(usuario_actual["activo"]),
        autentificacion_doble=bool(usuario_actual.get("autentificacion_doble")),
        foto_url=usuario_actual.get("foto_url"),
        permisos=[PermisoModuloResponse(**permiso) for permiso in permisos],
        sitios_asignados=usuario_actual.get("sitios_asignados") or [],
    )
