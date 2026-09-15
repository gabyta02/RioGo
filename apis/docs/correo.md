# Correo transaccional

Modulo unificado para envio de correos con plantillas HTML reutilizables.

## Estructura

```txt
core/correo/
  configuracion.py   # SMTP, remitente, marca, URL panel
  transporte.py      # envio multipart (texto + HTML)
  renderizado.py     # Jinja2
  enrutador.py       # unico punto de enrutamiento por accion
  tipos.py           # acciones y contexto por plantilla
  plantillas/
    base.html
    codigo_verificacion.html / .txt
    cuenta_admin_creada.html / .txt
    recordatorio_username.html / .txt
```

## Uso

```python
from core.correo import enviar_correo

enviar_correo(
    "codigo_verificacion",
    "usuario@example.com",
    {
        "codigo": "123456",
        "proposito": "login_2fa",
        "expira_minutos": 10,
    },
)
```

Acciones soportadas:

| Accion | Descripcion |
|--------|-------------|
| `codigo_verificacion` | Codigos de verificacion por email (auth) |
| `recordatorio_username` | Recordatorio de nombre de usuario para recuperacion de cuenta |
| `cuenta_admin_creada` | Credenciales temporales de cuenta admin |

Propósitos de `codigo_verificacion`:

| Propósito | Descripción |
|-----------|-------------|
| `registro_usuario` | Confirmar registro de una cuenta regular |
| `login_2fa` | Segundo factor de acceso al panel |
| `actualizar_credenciales` | Confirmar cambios desde una sesión conocida |
| `eliminar_cuenta` | Confirmar eliminación permanente |
| `recuperar_password` | Cambiar contraseña desde `/account/` sin sesión |

La acción `recordatorio_username` se usa cuando un usuario solicita consultar su
nombre de usuario por correo. El username no debe exponerse en respuestas HTTP.

## Variables de entorno

```env
GMAIL_USUARIO=
GMAIL_CLAVE_APLICATION=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

CORREO_FROM_EMAIL=noreply@tudominio.com
CORREO_FROM_NOMBRE=RiobambaTour
CORREO_REPLY_TO=soporte@tudominio.com
CORREO_URL_PANEL=https://www.riobambatour.org/admin/
CORREO_MARCA_COLOR_PRIMARIO=#0D5A38
CORREO_MARCA_COLOR_ACENTO=#FF7A00
```

## Entregabilidad (anti-spam)

El codigo envia correos `multipart/alternative` (texto + HTML), con
`From`, `Reply-To`, `Message-ID` y `Date`.

Para reducir spam en produccion configure tambien en DNS:

- **SPF** autorizando su servidor SMTP.
- **DKIM** con el proveedor de correo o dominio propio.
- **DMARC** con politica alineada al dominio del remitente.

Un dominio propio (`CORREO_FROM_EMAIL`) mejora la reputacion frente a
`@gmail.com` generico.

## Compatibilidad

`core/enviar_correo.py` se mantiene como fachada de compatibilidad y delega
en `core/correo/transporte.py`.

`core/verificar_correo.py` conserva la logica JWT + Redis y delega el envio
al enrutador de correo.
