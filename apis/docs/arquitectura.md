# Arquitectura de APIs

## Stack

- FastAPI para rutas HTTP.
- SQLAlchemy con sesiones desde un pool de conexiones.
- PostgreSQL/PostGIS con `pgvector`.
- Pydantic para contratos de entrada y salida.
- `python-dotenv` para configuracion por `.env`.
- Redis para tokens de verificacion de correo.
- Voyage `voyage-4-lite` para embeddings.
- SMTP (Gmail) para correos transaccionales.

## Estructura

```txt
apis/
  main.py
  app/
    registro_routers.py    # include_router por dominio

  core/
    infra/                 # conexion, redis, trazabilidad, filtros
    autenticacion/         # tokens, permisos y roles
    correo/                # plantillas y SMTP transaccional
    embeddings/
    chatboot_evaluacion/   # horario, GIS, chunks, precios
    *.py                   # shims de compatibilidad (rutas legacy)

  esquemas/
    autenticacion/
    panel_administrativo/
    app_movil/
    chatboot_exploracion/
    chatboot_especifico/
    compartido/
    *.py                   # shims

  rutas/
    (mismos dominios que esquemas)
    *.py                   # shims

  servicios/
    (mismos dominios que esquemas)
    *.py                   # shims

  docs/
    README.md              # indice de documentacion
    dominios/README.md     # mapa de dominios
    contratos_apis.md      # contratos HTTP panel + app movil
    chatboot_arquitectura_api.md
    arquitectura.md
    autentificacion.md
    correo.md

  tests/
```

Detalle del mapa de dominios: `docs/dominios/README.md`.

## Responsabilidades

`main.py` crea la aplicacion FastAPI, monta archivos estaticos de imagenes en
`/api/v1/imagenes` y delega el registro
de routers a `app/registro_routers.py`.

`core/infra/conexion.py` configura `DATABASE_URL`, el engine de SQLAlchemy y el pool
de conexiones. Cada request obtiene una sesion con `obtener_sesion`.

`core/autenticacion/dependencias.py` centraliza la autorizacion del panel:

| Dependencia | Uso |
|-------------|-----|
| `requerir_usuario_autenticado` | JWT valido, usuario activo y actividad admin en Redis |
| `requerir_usuario_panel` | Rol `super-admin` o `admin` |
| `requerir_super_admin` | Solo super-admin |
| `requerir_permiso(codigo)` | Permiso de modulo por usuario |
| `obtener_actor` | Username del usuario del panel para trazabilidad |

`core/embeddings/embeddings.py` abstrae la generacion de vectores con Voyage.

`core/autenticacion/encriptacion.py` centraliza bcrypt y JWT.

`core/correo/` centraliza plantillas HTML, enrutamiento por accion y envio SMTP
multipart. Ver `docs/correo.md`.

`core/autenticacion/enviar_correo.py` es fachada de compatibilidad sobre `core/correo`.

`core/autenticacion/verificar_correo.py` gestiona codigos de verificacion con Redis o memoria
local y delega el envio al enrutador de correo. También genera tokens ficticios
para respuestas genéricas de recuperación, evitando revelar si un correo existe.

`core/infra/redis_cliente.py` centraliza la conexion Redis compartida por actividad
admin y verificacion de correo.

`core/autenticacion/roles.py` centraliza roles de panel y mapeo cargo → rol.

`core/autenticacion/renovacion_tokens.py` gestiona sesiones persistentes en
`conversacion.sesion_usuario`. El access JWT dura poco y contiene `sid`; las
rutas protegidas verifican que ese `sid` siga activo antes de aceptar la peticion.

`core/autenticacion/actividad_sesion.py` controla la inactividad de administradores
en Redis (default 30 min) con fallback en memoria local. La actividad del panel se
renueva explicitamente con `POST /auth/admin-session/refresh` y
`X-Admin-Session-Id`; el refresh del access token no mantiene viva la inactividad.

`core/infra/trazabilidad.py` registra eventos semanticos en `trazabilidad.accion` e
`trazabilidad.inicio_sesion`.

`esquemas/` define los modelos Pydantic, literales permitidos por enums SQL y
respuestas de API.

`rutas/` contiene solo endpoints, dependencias de sesion y mapeo HTTP.

`servicios/` contiene la logica de negocio y consultas SQL.

## Modelo de autorizacion del panel

Roles derivados del cargo en `conversacion.cargo`:

- `usuario`: app movil/web de turistas.
- `admin`: personal del panel con permisos por modulo y accion.
- `super-admin`: acceso total y gestion de cuentas/cargos.

Catalogo de modulos en `conversacion.modulo`:

`dashboard`, `analytics`, `attractions`, `categories`, `routes`,
`chatbot_content`, `noticias`, `admin_accounts`, `action_log`.

Acciones en `conversacion.accion_t`: `ver`, `crear`, `actualizar`, `eliminar`, `exportar`.

Los permisos efectivos de cada cuenta `admin` viven en `conversacion.usuario_permiso`
(alcance global con `id_sitio IS NULL` o restringido por sitio).
Los cargos en `conversacion.cargo` y plantillas en `conversacion.cargo_permiso` sirven
como referencia al crear cuentas.

Admins con sitios asignados ven en dashboard, analisis de consultas y contenido
chatbot solo datos de esos sitios. Ver `core/autenticacion/permisos.py`
(`obtener_sitios_permitidos`).

## Modulos actuales

### Autenticacion (`/api/v1/auth`)

Registro, login, logout, verificacion por correo, reenvio de codigo,
actualizacion de cuenta, eliminacion de cuenta y recuperacion publica de cuenta.

El login del panel devuelve `permisos[]`, `inactividad_max_segundos` y actualiza
`ultimo_acceso_en`. Ver contrato completo en `docs/autentificacion.md`.

La recuperación pública (`/auth/recuperacion/*`) cubre usuarios que olvidaron
contraseña o nombre de usuario. Es intencionalmente neutral: no exige sesión,
no requiere contraseña actual, no revela existencia de emails y envía datos
sensibles solo por correo. Al cambiar contraseña revoca refresh token y actividad
admin. La experiencia pública se centraliza en `/account/`, servida por el panel,
para que administradores y app móvil usen la misma vista web.

### Dashboard (`/api/v1/admin/dashboard`)

Resumen, metricas, series, distribuciones, rankings, listado de consultas y analisis
semantico agrupado por embeddings.

Endpoints de resumen/metricas exigen permiso `dashboard` (accion `ver`).
Consultas y semantica exigen permiso `analytics` (accion `ver`).
Metricas de admins con sitios asignados se filtran por `id_sitio` permitido.
En el panel, `Analisis de consultas` no dispara el analisis semantico al abrir:
primero muestra filtros de periodo y consulta `/admin/dashboard/semantica` solo
cuando el usuario aplica filtros.

### Atractivos (`/api/v1/admin/atractivos`)

Listado, detalle, creacion, edicion, eliminacion, subida de imagenes,
catalogos de categorias/subcategorias, cambios de estado y catalogos auxiliares.

Los endpoints de sitios exigen permiso `attractions` con la accion correspondiente
(`ver`, `crear`, `actualizar`, `eliminar`).
Los endpoints de categorias/subcategorias exigen permiso `categories` por accion.
Listados de sitios aplican filtro SQL cuando el admin tiene alcance por sitio.

`turismo.horario` guarda `abierto_24h`, `activo` y `comentario` opcional
(maximo 200 caracteres) para notas como "Solo con reservacion previa".

### Rutas turisticas (`/api/v1/admin/rutas-turisticas`)

Listado, creacion, edicion, eliminacion fisica, cambio de estado, subida de
imagen de referencia y administracion de geometria/puntos.

Exige permiso `routes`.

### Contenido chatbots (`/api/v1/admin/contenido-chatbots`)

Repositorios y documentos Markdown con secciones embebibles para chatbots.
Permisos por accion (`ver`, `crear`, `actualizar`, `eliminar`, `exportar`).
Listado de repositorios con throttle de limpieza de huerfanos (5 min).
Regeneracion de chunk de descripcion valida ACL del vinculo sitio/ruta.

Exige permiso `chatbot_content`.

### Cuentas administrativas (`/api/v1/admin/cuentas`)

CRUD de cuentas `admin`, cambio de estado, asignacion de sitios y eliminacion fisica.

Solo `super-admin`. `PUT /sitios` valida que los IDs existan en `turismo.sitio`.

Al crear una cuenta:

1. Se genera una contrasena temporal aleatoria.
2. Se guarda hasheada en `conversacion.usuario`.
3. Se envia por correo al email de la cuenta.
4. Si el correo falla, se hace rollback de la transaccion.

Los usuarios que olviden la contraseña o el nombre de usuario deben usar la vista
publica `/account/`, compartida con cuentas móviles y administradores.

### Cargos y permisos (`/api/v1/admin/cargos`, `/api/v1/admin/permisos`)

CRUD de cargos con plantillas de modulos y catalogo de permisos del panel.

Solo `super-admin`.

### Chatboot — herramientas del planificador (`/api/v1/chatboot/herramientas`)

Endpoints HTTP consumidos por el nodo de exploración del chatboot. No usan JWT del panel.

Documentación detallada: [`docs/chatboot_arquitectura_api.md`](chatboot_arquitectura_api.md).

| Herramienta | Ruta | Módulos clave |
|-------------|------|---------------|
| busqueda_referencia | `busqueda-referencia` | trigram + parroquia/plataforma |
| contacto_busqueda | `contacto-busqueda` | contacto por nombre |
| horario_consulta | `horario-consulta` | `core/chatboot_evaluacion/horario_evaluacion.py` |
| precio_consulta | `precio-consulta` | `core/chatboot_evaluacion/precio_evaluacion.py` |
| tarifa_acceso_consulta | `tarifa-acceso-consulta` | `core/chatboot_evaluacion/tarifa_evaluacion.py` |
| atributos_booleanos_consulta | `atributos-booleanos-consulta` | `core/chatboot_evaluacion/atributos_evaluacion.py` |
| gis_consulta | `gis-consulta` | `core/chatboot_evaluacion/gis_evaluacion.py` (sitio o ruta) |
| ruta_consulta | `ruta-consulta` | `core/chatboot_evaluacion/ruta_evaluacion.py` |
| busqueda_semantica_consulta | `busqueda-semantica-consulta` | `core/embeddings/semantica_evaluacion.py`, `core/embeddings/embeddings.py` |

Todas comparten `ids_consulta` para encadenar el pipeline (`esquemas/chatboot_comun.py`,
`core/infra/filtro_sitios.py`). La búsqueda semántica indexa sobre `turismo.chunk` +
`turismo.chunk_fuente` (solo `origen = sitio`).

Optimizaciones recientes:

- Caché de embeddings Voyage en Redis/memoria (`core/embeddings/cache_embedding.py`).
- `input_type` query/document en llamadas Voyage.
- Boosts de keywords y score trigram en memoria (`rapidfuzz`) sin round-trips extra a BD.
- `DISTINCT ON (id_sitio)` en consultas vectoriales para un candidato por sitio.
- Pregunta directa: embeddings en batch para multiples textos de chunk.

Probador: `tests/probar_apis_chatboot.py`.

## Imagenes

Las imagenes se guardan en:

```txt
fuente_datos/imagenes/
```

Se sirven desde:

```txt
/api/v1/imagenes
```

La API solo elimina archivos locales si la URL pertenece al prefijo
`/api/v1/imagenes/...`. Las URLs externas no se tocan.

## Trazabilidad

Los servicios administrativos registran eventos en `trazabilidad.accion` e
`trazabilidad.inicio_sesion` con acciones semanticas (`login`, `creacion_cuenta_admin`,
`INSERT`, `UPDATE`, etc.).

El listado de registro de acciones pagina en SQL incluso cuando se filtra por tipo
visual de accion (`creacion`, `edicion`, etc.).

### Campos persistidos

| Campo | Inicio de sesion | Acciones CRUD |
|-------|------------------|---------------|
| Usuario (`username`, `id_usuario`) | Si | Si |
| Accion / resultado | Si | Si |
| Modulo (via `tabla_modificada`) | — | Si (mapeo en `registro_acciones`) |
| Fecha (`creado_en`) | Si | Si |
| IP | Si (desde `Request`) | Si (`direccion` en panel) |
| Referencia legible | Resultado | Si (`referencia`) |
| Datos antes/despues | — | Si (solo campos modificados cuando hay comparacion) |

### Registro en panel

- `GET /admin/registro-acciones` usa `vista=acciones` por defecto y consulta
  `trazabilidad.accion`.
- `vista=inicios_sesion` consulta `trazabilidad.inicio_sesion` y permite filtrar
  por `resultado=all|exitoso|fallido`.
- El detalle de acciones muestra creacion, edicion y eliminacion con presentacion
  diferenciada; los inicios de sesion muestran resultado, IP, user agent y detalle.

## Convenciones

- Mantener los endpoints delgados en `rutas/`.
- Mantener validaciones de negocio y SQL en `servicios/`.
- Mantener contratos de entrada/salida en `esquemas/`.
- Usar literales Pydantic cuando el valor proviene de un enum SQL.
- No duplicar logica de embeddings, correo ni autorizacion fuera de `core/`.
- Actualizar `docs/contratos_apis.md`, `docs/chatboot_arquitectura_api.md` y
  `docs/autentificacion.md` cuando cambie un endpoint o regla de seguridad.
- Mantener `docs/README.md` como indice de la documentacion.
