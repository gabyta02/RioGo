# Documentación de APIs — RiobambaGo

Índice de la documentación del contenedor `apis/`. La fuente de verdad de contratos HTTP
es el código (`rutas/`, `esquemas/`) y la documentación interactiva en `/docs` (OpenAPI).

## Documentos principales

| Documento | Contenido |
|-----------|-----------|
| [`contratos_apis.md`](contratos_apis.md) | Contratos HTTP por módulo: panel admin, app móvil, favoritos, noticias |
| [`autentificacion.md`](autentificacion.md) | JWT, refresh, 2FA, recuperación de cuenta, permisos, inactividad admin |
| [`arquitectura.md`](arquitectura.md) | Stack, carpetas por dominio, autorización, trazabilidad |
| [`dominios/README.md`](dominios/README.md) | Mapa de dominios (`core/`, `rutas/`, `servicios/`, `esquemas/`) |
| [`chatboot_arquitectura_api.md`](chatboot_arquitectura_api.md) | Herramientas H1–H12, pregunta directa, historial |
| [`chatboot_apis.md`](chatboot_apis.md) | Referencia legacy del monolito `/chatboot/*` (histórico) |
| [`correo.md`](correo.md) | Plantillas SMTP y propósitos de verificación |

## Mapa rápido de rutas (`/api/v1`)

Las rutas protegidas exigen `Authorization: Bearer`.

| Dominio | Prefijo | Documentación |
|---------|---------|---------------|
| Autenticación | `/auth` | `autentificacion.md` |
| Recuperación de cuenta | `/auth/recuperacion/*` | `autentificacion.md`, `contratos_apis.md` |
| Panel — dashboard | `/admin/dashboard` | `contratos_apis.md` |
| Panel — atractivos | `/admin/atractivos` | `contratos_apis.md` |
| Panel — rutas turísticas | `/admin/rutas-turisticas` | `contratos_apis.md` |
| Panel — noticias | `/admin/noticias` | `contratos_apis.md` |
| Panel — contenido chatbots | `/admin/contenido-chatbots` | `contratos_apis.md` |
| Panel — registro acciones | `/admin/registro-acciones` | `contratos_apis.md` |
| Panel — cuentas / cargos | `/admin/cuentas`, `/admin/cargos`, `/admin/permisos` | `contratos_apis.md` |
| App móvil — sitios | `/sitios` | `contratos_apis.md` |
| App móvil — ficha | `/ficha_sitio` | `contratos_apis.md` |
| App móvil — favoritos | `/favoritos` | `contratos_apis.md` |
| App móvil — noticias | `/noticias` | `contratos_apis.md` |
| App móvil — rutas turismo | `/rutas-movil-turismo` | `contratos_apis.md` |
| App móvil — buses | `/rutas-buses` | `contratos_apis.md` |
| App móvil — historial | `/historial` | `contratos_apis.md` |
| Chatboot exploración + historial PD | `/chatboot/herramientas` | `chatboot_arquitectura_api.md` |
| Chatboot pregunta directa | `/chatboot/pregunta-directa` | `chatboot_arquitectura_api.md` |
| Compartido | `/comprobar_archivos` | `contratos_apis.md` |
| Imágenes estáticas | `/imagenes` | `contratos_apis.md`, `arquitectura.md` |

## Esquemas de base de datos (referencia)

| Esquema | Uso principal |
|---------|---------------|
| `conversacion` | Usuarios, permisos, mensajes chatbot, conversaciones |
| `turismo` | Sitios, categorías, noticias, chunks, multimedia |
| `gis` | Rutas turísticas, geometría, buses |
| `trazabilidad` | Registro de acciones e inicios de sesión |

## Mantenimiento

Al cambiar un endpoint o regla de seguridad, actualizar:

1. El módulo correspondiente en `contratos_apis.md` o `chatboot_arquitectura_api.md`
2. `autentificacion.md` si afecta tokens, roles o permisos
3. `arquitectura.md` si cambia estructura de carpetas o dependencias `core/`

La vista pública de recuperación se sirve desde el panel en `/account/`; la app
móvil debe abrir esa URL en navegador/webview para cambiar contraseña o consultar
usuario. Su contrato backend está en `/auth/recuperacion/*`.

Probador chatboot: `tests/probar_apis_chatboot.py`  
Tests automatizados: `pytest tests/ -q --ignore=tests/probar_apis_chatboot.py`
