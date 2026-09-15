from typing import Any, Literal

AccionCorreo = Literal[
    "codigo_verificacion",
    "cuenta_admin_creada",
    "recordatorio_username",
]
PropositoVerificacion = Literal[
    "registro_usuario",
    "eliminar_cuenta",
    "actualizar_credenciales",
    "login_2fa",
    "recuperar_password",
]

METADATA_CODIGO_VERIFICACION: dict[str, dict[str, str]] = {
    "registro_usuario": {
        "asunto": "Confirma tu registro en RiobambaTour",
        "titulo": "Confirma tu registro",
        "mensaje": (
            "Usa este codigo para completar el registro de tu cuenta en RiobambaTour."
        ),
    },
    "login_2fa": {
        "asunto": "Codigo de acceso al panel RiobambaTour",
        "titulo": "Verificacion de acceso",
        "mensaje": (
            "Usa este codigo para completar el inicio de sesion en el panel administrativo."
        ),
    },
    "actualizar_credenciales": {
        "asunto": "Confirma cambios en tu cuenta RiobambaTour",
        "titulo": "Confirma tus cambios",
        "mensaje": (
            "Usa este codigo para confirmar la actualizacion de tus credenciales."
        ),
    },
    "eliminar_cuenta": {
        "asunto": "Confirma eliminacion de cuenta RiobambaTour",
        "titulo": "Confirmar eliminacion",
        "mensaje": (
            "Usa este codigo para confirmar la eliminacion permanente de tu cuenta."
        ),
    },
    "recuperar_password": {
        "asunto": "Recupera tu contrasena RiobambaTour",
        "titulo": "Recupera tu contrasena",
        "mensaje": (
            "Usa este codigo para cambiar la contrasena de tu cuenta RiobambaTour."
        ),
    },
}


def contexto_codigo_verificacion(
    *,
    codigo: str,
    proposito: str,
    expira_minutos: int,
) -> dict[str, Any]:
    meta = METADATA_CODIGO_VERIFICACION.get(
        proposito,
        {
            "asunto": "Codigo de verificacion RiobambaTour",
            "titulo": "Codigo de verificacion",
            "mensaje": "Usa este codigo para continuar con tu solicitud.",
        },
    )
    return {
        "codigo": codigo,
        "proposito": proposito,
        "expira_minutos": expira_minutos,
        "titulo": meta["titulo"],
        "mensaje": meta["mensaje"],
        "asunto": meta["asunto"],
    }


def contexto_cuenta_admin_creada(
    *,
    nombre_completo: str,
    username: str,
    password_temporal: str,
    url_panel: str,
) -> dict[str, Any]:
    return {
        "nombre_completo": nombre_completo,
        "username": username,
        "password_temporal": password_temporal,
        "url_panel": url_panel,
        "asunto": "Tu cuenta administrativa en RiobambaTour",
    }


def contexto_recordatorio_username(
    *,
    nombre_completo: str | None,
    username: str,
) -> dict[str, Any]:
    return {
        "nombre_completo": nombre_completo or "Usuario",
        "username": username,
        "asunto": "Tu nombre de usuario RiobambaTour",
    }
