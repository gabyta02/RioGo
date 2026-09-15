# Mapa de dominios (`apis/`)

La API se organiza por **dominio de negocio** dentro de cada capa técnica
(`core`, `rutas`, `servicios`, `esquemas`). Las rutas HTTP no cambian; los
archivos en la raíz de cada capa son **shims** que redirigen al módulo real vía
`sys.modules`.

## Dominios de capa HTTP

| Dominio | Carpeta | Descripción |
|---------|---------|-------------|
| `autenticacion` | `*/autenticacion/` | Login, refresh, `/auth/me` |
| `panel_administrativo` | `*/panel_administrativo/` | Dashboard, atractivos, cuentas, noticias, chunks |
| `app_movil` | `*/app_movil/` | Sitios, favoritos, historial, rutas buses |
| `chatboot_exploracion` | `*/chatboot_exploracion/` | Herramientas de exploración (horario, GIS, semántica, etc.) |
| `chatboot_especifico` | `*/chatboot_especifico/` | Pregunta directa, ficha compacta, historial PD |
| `compartido` | `*/compartido/` | Utilidades transversales (`comprobar_archivos`) |

## Subpaquetes de `core/`

| Subpaquete | Contenido |
|------------|-----------|
| `core/infra/` | Conexión DB, Redis, trazabilidad, filtros, búsqueda texto |
| `core/autenticacion/` | JWT, permisos, roles y verificación correo |
| `core/correo/` | Plantillas, SMTP, enrutador transaccional |
| `core/embeddings/` | Voyage, evaluación semántica |
| `core/chatboot_evaluacion/` | Lógica compartida de herramientas chatboot |

## Registro de routers

`app/registro_routers.py` centraliza `include_router` importando desde las
nuevas rutas por dominio. `main.py` solo crea la app y llama a
`registrar_routers(app)`.

## Compatibilidad

Imports legacy (`from core.tokens`, `from servicios.horario_consulta`) siguen
funcionando: cada shim en la raíz de la capa reemplaza su entrada en
`sys.modules` por el módulo canónico del subdominio.

Para código nuevo, preferir rutas explícitas:

```python
from core.autenticacion.tokens import crear_access_token
from servicios.chatboot_exploracion.horario_consulta import consultar_sitios_por_horario
```

## Documentación relacionada

| Archivo | Descripción |
|---------|-------------|
| [`../README.md`](../README.md) | Índice general de docs de APIs |
| [`../contratos_apis.md`](../contratos_apis.md) | Contratos HTTP del panel y app móvil |
| [`../chatboot_arquitectura_api.md`](../chatboot_arquitectura_api.md) | Herramientas chatboot H1–H12 |
| [`../autentificacion.md`](../autentificacion.md) | Tokens, permisos y roles |
