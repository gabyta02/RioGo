from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

RolUsuario = Literal["super-admin", "admin", "usuario"]
PropositoVerificacion = Literal[
    "registro_usuario",
    "eliminar_cuenta",
    "actualizar_credenciales",
    "login_2fa",
    "recuperar_password",
]


class VerificacionCorreoMixin(BaseModel):
    codigo_verificacion: str = Field(min_length=6, max_length=6)
    token_verificacion: str = Field(min_length=1)


class UsuarioRegistroBase(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6)


class UsuarioRegistroUsuario(UsuarioRegistroBase, VerificacionCorreoMixin):
    rol: Literal["usuario"] = "usuario"


class UsuarioRegistroAdmin(UsuarioRegistroBase):
    rol: Literal["super-admin"] = "super-admin"


class UsuarioLogin(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1)
    codigo_verificacion: str | None = Field(default=None, min_length=6, max_length=6)
    token_verificacion: str | None = Field(default=None, min_length=1)


class UsuarioEliminar(VerificacionCorreoMixin):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1)


class UsuarioActualizar(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1)
    nuevo_username: str | None = Field(default=None, min_length=3, max_length=80)
    nuevo_email: EmailStr | None = None
    nuevo_password: str | None = Field(default=None, min_length=6)
    codigo_verificacion: str | None = Field(default=None, min_length=6, max_length=6)
    token_verificacion: str | None = Field(default=None, min_length=1)


class UsuarioActualizar2FA(VerificacionCorreoMixin):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1)
    autentificacion_doble: bool


class FotoPerfilResponse(BaseModel):
    foto_url: str
    mensaje: str = "Foto de perfil actualizada"


class SolicitudVerificacionCorreo(BaseModel):
    proposito: PropositoVerificacion
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=80)


class RecuperacionPasswordSolicitar(BaseModel):
    email: EmailStr


class RecuperacionPasswordConfirmar(VerificacionCorreoMixin):
    email: EmailStr
    nuevo_password: str = Field(min_length=6)


class RecuperacionUsuarioSolicitar(BaseModel):
    email: EmailStr


class UsuarioRespuesta(BaseModel):
    id_usuario: int
    id_rol: int | None = None
    id_cargo: int | None = None
    nombre_completo: str | None = None
    cargo_nombre: str | None = None
    username: str
    email: EmailStr
    rol: RolUsuario
    activo: bool
    autentificacion_doble: bool
    actualizado_en: datetime
    ultimo_acceso_en: datetime | None = None


class LoginRespuesta(BaseModel):
    rol: RolUsuario
    token: str
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    token_refresh_in: int
    inactividad_max_segundos: int | None = None
    id_sesion: str | None = None
    admin_sesion_id: str | None = None
    permisos: list[str] = Field(default_factory=list)
    usuario: UsuarioRespuesta


class MensajeRespuesta(BaseModel):
    mensaje: str


class VerificacionCorreoRespuesta(BaseModel):
    mensaje: str
    token_verificacion: str
    expira_en_minutos: int


class PermisoModuloResponse(BaseModel):
    modulo: str
    acciones: list[str] = Field(default_factory=list)
    alcance: Literal["global", "sitio"]
    sitios: list[int] | None = None


class UsuarioMeResponse(BaseModel):
    id_usuario: int
    username: str
    email: EmailStr
    nombre_completo: str | None = None
    rol: RolUsuario
    cargo_nombre: str | None = None
    activo: bool
    autentificacion_doble: bool = False
    foto_url: str | None = None
    permisos: list[PermisoModuloResponse] = Field(default_factory=list)
    sitios_asignados: list[int] = Field(default_factory=list)
