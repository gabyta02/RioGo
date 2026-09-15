# Autenticación y autorización

Las APIs no usan token de aplicación. La autenticación de usuarios se realiza
mediante JWT enviado en el encabezado `Authorization`.

```http
Authorization: Bearer <access_token>
```

## Sesiones

- `POST /api/v1/auth/login` crea una sesión y devuelve los tokens de acceso y
  actualización.
- `POST /api/v1/auth/refresh` renueva el token de acceso.
- `POST /api/v1/auth/logout` invalida la sesión autenticada.
- `GET /api/v1/auth/me` devuelve el perfil de la sesión actual.

El access token es un JWT de vida corta y viaja en `Authorization`. La sesion
persistente se guarda en `conversacion.sesion_usuario` como hash del refresh
token y permite renovar access tokens sin pisar otros dispositivos. El refresh
persistente no autoriza consultas directas a APIs y se revoca en logout, cambio
de contrasena, eliminacion o desactivacion de cuenta.

Los endpoints públicos, como inicio de sesión, registro y consulta de sitios,
no requieren encabezado de autorización. Los endpoints protegidos declaran sus
dependencias de JWT y permisos en sus rutas.

## Panel administrativo

El panel requiere una sesión JWT con rol `admin` o `super-admin`. Los permisos
por módulo y acción se validan en el backend. La actividad de administradores
se controla en Redis mediante `X-Admin-Session-Id` y expira tras el periodo de
inactividad configurado.

## Verificación por correo

Los flujos de verificación de correo emiten códigos temporales y tokens de
verificación. No sustituyen al JWT de una sesión autenticada.

Propósitos actuales:

| Propósito | Uso |
|-----------|-----|
| `registro_usuario` | Confirmar registro de cuenta móvil/web |
| `login_2fa` | Completar login de cuentas con autenticación doble |
| `actualizar_credenciales` | Confirmar cambios de email, contraseña o 2FA desde una sesión conocida |
| `eliminar_cuenta` | Confirmar eliminación de cuenta |
| `recuperar_password` | Cambiar contraseña cuando el usuario olvidó sus credenciales |

Los códigos tienen TTL configurable con `CODIGO_CORREO_EXPIRA_MINUTOS` (10 minutos
por defecto). La verificación se apoya en Redis y usa memoria local como fallback
para entornos sin Redis.

## Recuperación de cuenta sin sesión

El flujo público de recuperación se usa cuando el usuario no puede iniciar sesión.
No requiere JWT ni contraseña actual.

Endpoints:

| Endpoint | Uso |
|----------|-----|
| `POST /api/v1/auth/recuperacion/password/solicitar` | Solicita código por email para cambiar contraseña |
| `POST /api/v1/auth/recuperacion/password/confirmar` | Cambia contraseña con email, código y token de verificación |
| `POST /api/v1/auth/recuperacion/usuario/solicitar` | Envía por correo el nombre de usuario asociado |

Reglas de seguridad:

- Las respuestas de solicitud son genéricas y no revelan si el correo existe.
- El nombre de usuario nunca se devuelve por API; solo se envía por correo.
- La consulta de usuario aplica una regla central en `core/reglas_seguridad.py`:
  demasiados correos distintos desde la misma IP bloquean temporalmente esa IP
  para reducir barridos de cuentas.
- Al confirmar cambio de contraseña se revoca el refresh token almacenado y se
  limpia la actividad administrativa si la cuenta pertenece al panel.
- La vista pública del panel vive en `/account/` y sirve tanto a administradores
  como a usuarios móviles. No redirige automáticamente a `/admin/`.
- La app móvil debe enviar al usuario a `https://<dominio-publico>/account/`
  para cambiar contraseña o consultar su nombre de usuario; no necesita construir
  una pantalla nativa para este flujo.
- En `/account/`, el cambio de contraseña captura primero correo, nueva
  contraseña y confirmación; luego solicita el código y lo valida en una pantalla
  separada al completar 6 dígitos.

Contrato detallado: [`contratos_apis.md`](contratos_apis.md#recuperar-contraseña-sin-sesion).
