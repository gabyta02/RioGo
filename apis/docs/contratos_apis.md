# Contratos de APIs

## Base URL

```txt
/api/v1
```

Todas las respuestas son JSON.

## Autenticacion

### Solicitar codigo de correo

```http
POST /api/v1/auth/correo/verificacion
```

Body:

```json
{
  "proposito": "login_2fa",
  "username": "admin"
}
```

Para registro de usuario:

```json
{
  "proposito": "registro_usuario",
  "email": "usuario@example.com"
}
```

Respuesta:

```json
{
  "mensaje": "Codigo de verificacion enviado",
  "token_verificacion": "jwt-temporal",
  "expira_en_minutos": 10
}
```

### Reenviar codigo

```http
POST /api/v1/auth/correo/reenviar
```

Usa el mismo body de solicitud de codigo. El codigo anterior queda invalidado.

### Login

```http
POST /api/v1/auth/login
```

Usuario normal:

```json
{
  "username": "usuario1",
  "password": "Password123"
}
```

Administrador:

```json
{
  "username": "admin",
  "password": "Password123",
  "codigo_verificacion": "123456",
  "token_verificacion": "jwt-temporal"
}
```

Respuesta:

```json
{
  "rol": "super-admin",
  "token": "jwt-sesion",
  "usuario": {
    "id_usuario": 1,
    "id_rol": 2,
    "username": "admin",
    "email": "admin@example.com",
    "rol": "super-admin",
    "activo": true,
    "autentificacion_doble": true,
    "actualizado_en": "2026-06-13T00:00:00Z"
  }
}
```

### Registro usuario

```http
POST /api/v1/auth/registro/usuario
```

Requiere verificacion de correo.

```json
{
  "username": "usuario1",
  "email": "usuario@example.com",
  "password": "Password123",
  "rol": "usuario",
  "codigo_verificacion": "123456",
  "token_verificacion": "jwt-temporal"
}
```

### Registro admin

```http
POST /api/v1/auth/registro/admin
```

No requiere codigo de correo.

```json
{
  "username": "admin",
  "email": "admin@example.com",
  "password": "Password123",
  "rol": "super-admin"
}
```

### Cerrar sesion

```http
POST /api/v1/auth/logout
Authorization: Bearer jwt-sesion
```

### Renovar sesion (refresh)

```http
POST /api/v1/auth/refresh
Cookie: refresh_token=<token-persistente>
```

Devuelve la misma estructura que login (`access_token`, `permisos`, `usuario`, etc.).
El token persistente no se usa para consultar APIs; se guarda hasheado en
`conversacion.sesion_usuario`, rota en cada refresh y queda vigente hasta logout,
revocacion o cambio sensible de credenciales. La vida de la cookie se controla con
`REFRESH_COOKIE_MAX_AGE_SECONDS`. Ver detalle en [`autentificacion.md`](autentificacion.md).

Para sesiones del panel administrativo, la respuesta de login incluye
`admin_sesion_id`. Las rutas `/api/v1/admin/*` requieren además:

```http
X-Admin-Session-Id: <admin_sesion_id>
```

El panel renueva esa ventana de inactividad con:

```http
POST /api/v1/auth/admin-session/refresh
Authorization: Bearer jwt-sesion
X-Admin-Session-Id: <admin_sesion_id>
```

### Perfil del usuario autenticado

```http
GET /api/v1/auth/me
Authorization: Bearer jwt-sesion
```

Respuesta: datos del usuario, rol, permisos enriquecidos y sitios asignados si aplica.
Incluye `foto_url` y `autentificacion_doble`.

Respuesta logout:

```json
{
  "mensaje": "Sesion cerrada correctamente"
}
```

Los endpoints protegidos validan el JWT de acceso y que su `sid` pertenezca a
una sesion activa en `conversacion.sesion_usuario`. Los endpoints bajo
`/api/v1/admin/*` tambien validan la sesion administrativa de Redis.

Contrato completo de autenticación: [`autentificacion.md`](autentificacion.md).

### Actualizar cuenta

```http
PATCH /api/v1/auth/cuenta
```

Cambiar solo username:

```json
{
  "username": "usuario1",
  "password": "Password123",
  "nuevo_username": "usuario2"
}
```

Cambiar email o password requiere codigo:

```json
{
  "username": "usuario1",
  "password": "Password123",
  "nuevo_email": "nuevo@example.com",
  "nuevo_password": "Password456",
  "codigo_verificacion": "123456",
  "token_verificacion": "jwt-temporal"
}
```

### Recuperar contraseña sin sesion

Vista pública recomendada para navegador: `/account/`. Esta vista también sirve
para usuarios móviles que abren el recurso fuera de la app.

Solicitar codigo:

```http
POST /api/v1/auth/recuperacion/password/solicitar
```

```json
{
  "email": "usuario@example.com"
}
```

Respuesta siempre generica:

```json
{
  "mensaje": "Si el correo corresponde a una cuenta activa, enviaremos un codigo para continuar.",
  "token_verificacion": "jwt-temporal",
  "expira_en_minutos": 10
}
```

Códigos esperados: `200`, `422`, `429` si aplica rate limit de correo.

En la vista `/account/`, el usuario ingresa primero correo, nueva contraseña y
confirmación. Después se solicita el código y se muestra una pantalla de
verificación similar al login con 2FA.

Confirmar cambio:

```http
POST /api/v1/auth/recuperacion/password/confirmar
```

```json
{
  "email": "usuario@example.com",
  "nuevo_password": "Password456",
  "codigo_verificacion": "123456",
  "token_verificacion": "jwt-temporal"
}
```

Respuesta:

```json
{
  "mensaje": "Contrasena actualizada correctamente"
}
```

No requiere sesion ni password actual. Al cambiar la contrasena se revocan tokens
activos y actividad administrativa si aplica.

Códigos esperados: `200`, `400`, `422`.

### Consultar nombre de usuario por correo

```http
POST /api/v1/auth/recuperacion/usuario/solicitar
```

```json
{
  "email": "usuario@example.com"
}
```

Respuesta siempre generica:

```json
{
  "mensaje": "Si el correo corresponde a una cuenta activa, enviaremos el nombre de usuario asociado."
}
```

El nombre de usuario no se devuelve por API; se envia solo por correo. Además,
el backend aplica una regla central de seguridad: si una misma IP consulta
demasiados correos distintos dentro de una ventana corta, la IP queda bloqueada
temporalmente para esta operación y se responde `429`.

Códigos esperados: `200`, `422`, `429` por exceso de correos distintos desde la
misma IP.

### Subir foto de perfil

```http
POST /api/v1/auth/cuenta/foto
Authorization: Bearer jwt-sesion
Content-Type: multipart/form-data
```

Campo `archivo`: imagen JPG o PNG, máximo 2 MB.

Respuesta:

```json
{
  "foto_url": "/api/v1/imagenes/perfiles/1/a1b2c3.jpg",
  "mensaje": "Foto de perfil actualizada"
}
```

### Activar o desactivar autenticacion en dos pasos

```http
PATCH /api/v1/auth/cuenta/2fa
```

```json
{
  "username": "usuario1",
  "password": "Password123",
  "autentificacion_doble": true,
  "codigo_verificacion": "123456",
  "token_verificacion": "jwt-temporal"
}
```

Requiere verificacion por correo (`proposito: actualizar_credenciales`) al activar o desactivar.

### Eliminar cuenta

```http
DELETE /api/v1/auth/cuenta
```

```json
{
  "username": "usuario1",
  "password": "Password123",
  "codigo_verificacion": "123456",
  "token_verificacion": "jwt-temporal"
}
```

## Dashboard Admin

Base:

```txt
/api/v1/admin/dashboard
```

### Resumen

```http
GET /api/v1/admin/dashboard/resumen
```

Query params:

```txt
periodo=all|today|week|month|year|custom
fecha_inicio=YYYY-MM-DD
fecha_fin=YYYY-MM-DD
```

Respuesta:

```json
{
  "usuarios_registrados": { "valor": 1, "variacion": 100.0 },
  "atractivos_activos": { "valor": 0, "variacion": 0.0 },
  "preguntas_chatbots": { "valor": 0, "variacion": 0.0 },
  "favoritos_guardados": { "valor": 0, "variacion": 0.0 },
  "noticias_activas": { "valor": 0, "variacion": 0.0 },
  "rutas_activas": { "valor": 0, "variacion": 0.0 }
}
```

Fuentes principales:

```txt
usuarios   -> conversacion.usuario
atractivos -> turismo.sitio
preguntas  -> conversacion.mensaje_explorador + conversacion.mensaje_detalle
favoritos  -> conversacion.favorito
noticias   -> turismo.noticia
rutas      -> gis.rutas_turistica
```

**Alcance por sitios:** cuentas `admin` con permisos restringidos a sitios concretos
(`usuario_permiso.id_sitio`) solo ven métricas, consultas y semántica de esos sitios.
`super-admin` ve el universo completo.

### Metrica individual

```http
GET /api/v1/admin/dashboard/metricas
```

Query params:

```txt
metric=usuarios|atractivos|preguntas|favoritos|noticias|rutas
periodo=all|today|week|month|year|custom
estado=activo|inactivo|publicado|borrador|all
tipo_chatbot=general|sitio|all
categoria=Naturaleza
subcategoria=Volcanes
id_sitio=1
```

Respuesta:

```json
{
  "metric": "rutas",
  "periodo": "all",
  "valor": 11
}
```

Para `metric=rutas`, el conteo usa:

```sql
SELECT COUNT(*) FROM gis.rutas_turistica
```

## Atractivos Turisticos Admin

Base:

```txt
/api/v1/admin/atractivos
```

### Listar atractivos

```http
GET /api/v1/admin/atractivos
```

Query params:

```txt
q=chimborazo
id_categoria=1
id_subcategoria=2
estado=activo|inactivo|all
servicio=wifi|parqueadero|mascotas|accesibilidad|all
precio=gratis|pagado|all
page=1
page_size=10
```

Respuesta:

```json
{
  "page": 1,
  "page_size": 10,
  "total": 1,
  "items": [
    {
      "id_sitio": 1,
      "nombre": "Volcan Chimborazo",
      "descripcion_corta": "El punto mas alto del Ecuador.",
      "id_categoria": 1,
      "categoria": "Naturaleza",
      "id_subcategoria": 2,
      "subcategoria": "Reservas naturales",
      "activo": true,
      "imagen_url": "https://example.com/chimborazo.jpg"
    }
  ]
}
```

### Crear atractivo

```http
POST /api/v1/admin/atractivos
```

Body minimo:

```json
{
  "id_parroquia": 1,
  "id_plataforma": 1,
  "id_categoria": 1,
  "id_subcategoria": 2,
  "tipo": "atractivo_turistico",
  "nombre": "Volcan Chimborazo",
  "descripcion_corta": "El punto mas alto del Ecuador.",
  "latitud": -1.4691,
  "longitud": -78.8175,
  "direccion_texto": "Reserva de Produccion de Fauna Chimborazo",
  "referencia_adicional": "Ingreso principal por la via Guaranda",
  "horario": {
    "abierto_24h": false,
    "dias_semana": [1, 2, 3, 4, 5, 6, 7],
    "hora_inicio": "07:00",
    "hora_fin": "17:00",
    "comentario": "Solo con reservacion previa"
  },
  "contactos": [
    { "tipo": "telefono", "contenido": "(03) 296-0300" }
  ],
  "multimedia": [
    {
      "url": "/api/v1/imagenes/volcan-chimborazo/imagen.jpg",
      "es_principal": true
    }
  ],
  "precio": {
    "es_gratuito": true,
    "precio_min": null,
    "precio_max": null,
    "etiqueta_precio": "desconocido",
    "tarifa_acceso": null,
    "condicion_tarifa": null
  },
  "tiene_wifi": true,
  "parqueadero": true,
  "permite_mascotas": false,
  "accesibilidad": true,
  "activo": true
}
```

Body completo:

```json
{
  "id_parroquia": 1,
  "id_plataforma": 1,
  "id_categoria": 1,
  "id_subcategoria": 2,
  "tipo": "atractivo_turistico",
  "nombre": "Volcan Chimborazo",
  "descripcion_corta": "El punto mas alto del Ecuador y el mas cercano al sol.",
  "latitud": -1.4691,
  "longitud": -78.8175,
  "es_gratuito": true,
  "permite_mascotas": false,
  "parqueadero": true,
  "tiene_wifi": false,
  "accesibilidad": true,
  "activo": true,
  "direccion_texto": "Reserva de Produccion de Fauna Chimborazo",
  "referencia_adicional": "Ingreso principal por la via Guaranda",
  "horario": {
    "abierto_24h": false,
    "dias_semana": [1, 2, 3, 4, 5, 6, 7],
    "hora_inicio": "07:00",
    "hora_fin": "17:00",
    "comentario": "Solo con reservacion previa"
  },
  "contactos": [
    { "tipo": "telefono", "contenido": "(03) 296-0300" },
    { "tipo": "whatsapp", "contenido": "0999999999" },
    { "tipo": "email", "contenido": "info@chimborazo.gob.ec" },
    { "tipo": "web", "contenido": "https://www.turismo.gob.ec" },
    { "tipo": "facebook", "contenido": "https://facebook.com/chimborazo" },
    { "tipo": "instagram", "contenido": "https://instagram.com/chimborazo" },
    { "tipo": "tiktok", "contenido": "https://tiktok.com/@chimborazo" },
    { "tipo": "otro", "contenido": "Centro de informacion turistico" }
  ],
  "multimedia": [
    {
      "url": "/api/v1/imagenes/volcan-chimborazo/chimborazo.jpg",
      "es_principal": true
    }
  ],
  "precio": {
    "es_gratuito": false,
    "precio_min": 2.5,
    "precio_max": 10,
    "etiqueta_precio": "economico",
    "tarifa_acceso": 5,
    "condicion_tarifa": "Adultos"
  }
}
```

Respuesta: `201 Created` con el mismo formato de un item de listado.

Notas:

- `id_categoria`, `tipo` y `nombre` son obligatorios porque asi esta definido el esquema SQL.
- `id_parroquia` e `id_plataforma` pueden enviarse como `null`; si se envia `id_plataforma`, tambien debe enviarse `id_parroquia`.
- Los tipos validos de sitio salen del enum `turismo.tipo_sitio_t`: `servicio_turistico`, `atractivo_turistico`, `operadora_turistica`, `desconocido`.
- `id_subcategoria`, `descripcion_corta`, `latitud`, `longitud`, `direccion_texto`, `referencia_adicional`, `horario`, `contactos`, `multimedia` y `precio` tambien son obligatorios para el formulario administrativo actual.
- `id_subcategoria` debe pertenecer a `id_categoria`.
- `contactos` requiere al menos un item; no es necesario enviar todos los tipos de contacto.
- `multimedia` crea registros en `turismo.multimedia`; si ninguna imagen llega marcada como principal, la primera sera principal.
- `direccion_texto` crea el registro asociado en `turismo.direccion`.
- Si `horario.abierto_24h=true`, la API guarda los dias seleccionados con rango interno `00:00` a `23:59`. En este caso `horario.detalles` se ignora.
- `horario.detalles` es opcional y permite definir uno o mas horarios por dia (1-7).
  Cada item es `{ "dia_semana": 1..7, "cerrado": false, "hora_inicio": "HH:MM", "hora_fin": "HH:MM" }`.
  Si `cerrado=true`, no se persisten horas para ese dia. `dias_semana` sigue
  siendo la fuente de verdad de "que dias abre"; los dias listados que no
  tengan detalle se interpretan como cerrados.
  - Si `detalles` esta presente y `abierto_24h=false`, se usa el detalle por
    dia. `hora_inicio`/`hora_fin` globales pueden omitirse.
  - Si `detalles` esta vacio, se replica `hora_inicio`/`hora_fin` globales
    en cada dia de `dias_semana`.
- `horario.comentario` es opcional, maximo 200 caracteres. Se guarda en `turismo.horario.comentario`.
- Los tipos validos de contacto salen del enum `turismo.tipo_contacto_t`: `telefono`, `whatsapp`, `email`, `web`, `facebook`, `instagram`, `tiktok`, `otro`.
- Las etiquetas validas de precio salen del enum `turismo.etiqueta_precio_t`: `economico`, `medio`, `alto`, `desconocido`.
- `precio.es_gratuito=true` indica sitio gratuito. En este caso no se
  aceptan `precio_min`, `precio_max`, `tarifa_acceso` ni `condicion_tarifa`.
- `precio.tarifa_acceso` y `precio.precio_min`+`precio_max` son **excluyentes**:
  envie uno u otro, no ambos. Si llegan ambos, la API responde 400.
- La API guarda `descripcion_corta` como dato descriptivo; los embeddings para chatbot se generan desde secciones de documentos Markdown.

### Detalle de atractivo

```http
GET /api/v1/admin/atractivos/{id_sitio}
```

Devuelve la informacion completa usada por el formulario de edicion:
datos generales, clasificacion, direccion, coordenadas, horario, contactos,
multimedia, servicios y precios.

`horario` incluye un array `detalles` con la lista persistida de
`horario_detalle` (un item por dia con horario activo). Los dias
listados en `dias_semana` que no aparecen en `detalles` se interpretan
como cerrados.

### Actualizar atractivo

```http
PUT /api/v1/admin/atractivos/{id_sitio}
```

Usa el mismo body de creacion. La API actualiza el sitio y reemplaza las
relaciones editables del formulario: direccion, multimedia, contactos, horario,
rango de precio y tarifa de acceso.

Si una imagen local registrada en `turismo.multimedia` deja de estar asociada
al atractivo despues de editar, el archivo se elimina desde
`fuente_datos/imagenes`.

### Eliminar atractivo

```http
DELETE /api/v1/admin/atractivos/{id_sitio}
```

Elimina fisicamente el registro de `turismo.sitio`. Las tablas dependientes
con `ON DELETE CASCADE` se eliminan por la base de datos. Antes de eliminar el
sitio, la API limpia referencias en `gis.ruta_puntos` para evitar conflictos
con el `CHECK` de esa tabla. Tambien borra los archivos locales registrados en
`turismo.multimedia` cuando pertenecen a `/api/v1/imagenes/...`. Las URLs
externas no se eliminan del filesystem.

### Cambiar estado de atractivo

```http
PATCH /api/v1/admin/atractivos/{id_sitio}/estado
```

Body:

```json
{
  "activo": false
}
```

Actualiza solo `turismo.sitio.activo`. Este endpoint se usa desde el badge
`Activo/Inactivo` del panel y no elimina archivos ni relaciones.

### Subir imagenes

```http
POST /api/v1/admin/atractivos/imagenes
Content-Type: multipart/form-data
```

Campos:

```txt
nombre_sitio=Volcan Chimborazo
archivos=<uno o varios archivos image/*>
```

La API guarda los archivos en:

```txt
fuente_datos/imagenes/{nombre-del-sitio}/
```

Respuesta:

```json
[
  {
    "nombre_archivo": "archivo.jpg",
    "url": "/api/v1/imagenes/volcan-chimborazo/archivo.jpg"
  }
]
```

### Categorias

```http
GET /api/v1/admin/atractivos/categorias
GET /api/v1/admin/atractivos/categorias/detalle
POST /api/v1/admin/atractivos/categorias
PATCH /api/v1/admin/atractivos/categorias/{id_categoria}
PATCH /api/v1/admin/atractivos/categorias/{id_categoria}/estado
DELETE /api/v1/admin/atractivos/categorias/{id_categoria}
```

Body POST:

```json
{
  "nombre": "Naturaleza",
  "activo": true
}
```

Respuesta:

```json
{
  "id_categoria": 1,
  "nombre": "Naturaleza",
  "activo": true
}
```

`DELETE` elimina fisicamente la categoria, sus subcategorias y los atractivos
asociados. Tambien limpia imagenes locales asociadas a esos atractivos.

`PATCH /estado` cambia solamente `turismo.categoria.activo`.

### Subcategorias

```http
GET /api/v1/admin/atractivos/subcategorias?id_categoria=1
POST /api/v1/admin/atractivos/subcategorias
PATCH /api/v1/admin/atractivos/subcategorias/{id_subcategoria}
PATCH /api/v1/admin/atractivos/subcategorias/{id_subcategoria}/estado
DELETE /api/v1/admin/atractivos/subcategorias/{id_subcategoria}
```

Body POST:

```json
{
  "id_categoria": 1,
  "nombre": "Reservas naturales",
  "activo": true
}
```

`DELETE` elimina fisicamente la subcategoria y los atractivos asociados.
Tambien limpia imagenes locales asociadas a esos atractivos.

`PATCH /estado` cambia solamente `turismo.subcategoria.activo`.

Respuesta:

```json
{
  "id_subcategoria": 2,
  "id_categoria": 1,
  "nombre": "Reservas naturales",
  "activo": true
}
```

### Catalogos auxiliares para formularios

```http
GET /api/v1/admin/atractivos/parroquias
GET /api/v1/admin/atractivos/plataformas?id_parroquia=1
```

Respuesta:

```json
[
  {
    "id": 1,
    "nombre": "Riobamba",
    "activo": true
  }
]
```

## Rutas Turisticas Admin

Base:

```txt
/api/v1/admin/rutas-turisticas
```

### Listar rutas

```http
GET /api/v1/admin/rutas-turisticas
```

Query params:

```txt
q=hielo
tipo_ruta=Senderismo|Ciclismo|Caminata Urbana|Montañismo|Otras
estado=activo|inactivo|all
page=1
page_size=10
```

Respuesta:

```json
{
  "page": 1,
  "page_size": 10,
  "total": 1,
  "items": [
    {
      "id_ruta": 1,
      "tipo_ruta": "Senderismo",
      "titulo": "Ruta del Hielo",
      "url_imagen": "/api/v1/imagenes/rutas/ruta-del-hielo/imagen.jpg",
      "descripcion": "Ruta interpretativa de alta montana.",
      "activo": true,
      "total_puntos": 0,
      "tiene_linea": false
    }
  ]
}
```

### Crear ruta

```http
POST /api/v1/admin/rutas-turisticas
```

Body actual del panel:

```json
{
  "tipo_ruta": "Senderismo",
  "titulo": "Ruta del Hielo",
  "url_imagen": "/api/v1/imagenes/rutas/ruta-del-hielo/imagen.jpg",
  "descripcion": "Ruta interpretativa de alta montana.",
  "activo": true
}
```

Notas:

- `tipo_ruta`, `titulo`, `url_imagen`, `descripcion` y `activo` son los campos usados por el formulario administrativo actual.
- Los tipos validos de ruta salen del enum `gis.tipo_ruta_t`: `Senderismo`, `Ciclismo`, `Caminata Urbana`, `Montañismo`, `Otras`.
- La geometria `geom_linea` y los puntos de `gis.ruta_puntos` se administran
  desde los endpoints de geometria; no son obligatorios para crear la ruta base.
- La API guarda `descripcion` como dato descriptivo; los embeddings para chatbot se generan desde secciones de documentos Markdown.

### Buscar sitios para geometria

```http
GET /api/v1/admin/rutas-turisticas/sitios
```

Query params:

```txt
q=chimborazo
limit=20
```

Respuesta:

```json
[
  {
    "id_sitio": 1,
    "nombre": "Volcan Chimborazo",
    "categoria": "Naturaleza",
    "subcategoria": "Volcanes",
    "latitud": -1.4692,
    "longitud": -78.8175
  }
]
```

Solo devuelve sitios activos con `turismo.sitio.ubicacion` registrada.

### Obtener geometria de ruta

```http
GET /api/v1/admin/rutas-turisticas/{id_ruta}/geometria
```

Respuesta:

```json
{
  "id_ruta": 1,
  "titulo": "Ruta de las Iglesias",
  "linea": [
    { "latitud": -1.673, "longitud": -78.648 },
    { "latitud": -1.675, "longitud": -78.651 }
  ],
  "puntos": [
    {
      "orden": 1,
      "tipo": "inicio",
      "id_sitio": null,
      "nombre_sitio": null,
      "latitud": -1.673,
      "longitud": -78.648
    },
    {
      "orden": 2,
      "tipo": "sitio",
      "id_sitio": 10,
      "nombre_sitio": "Catedral de Riobamba",
      "latitud": -1.674,
      "longitud": -78.65
    }
  ]
}
```

Tipos de punto usados por el panel:

```txt
inicio|fin|libre|sitio
```

En la interfaz, los puntos se crean primero como puntos normales. Luego el
usuario puede marcar cualquier punto como origen o final. Si el punto proviene
de un sitio, conserva `id_sitio`; si ademas se marca como origen o final, la API
guarda tambien `punto_inicio` o `punto_fin`.

El panel modela la edicion como un grafo local: puntos con identificador
interno, lineas independientes y vertices libres o enlazados a puntos. Al
guardar, ese grafo se aplana a un unico arreglo `linea` porque la base de datos
guarda la forma final en `gis.rutas_turistica.geom_linea`.

### Guardar geometria de ruta

```http
PUT /api/v1/admin/rutas-turisticas/{id_ruta}/geometria
```

Body:

```json
{
  "linea": [
    { "latitud": -1.673, "longitud": -78.648 },
    { "latitud": -1.675, "longitud": -78.651 }
  ],
  "puntos": [
    {
      "orden": 1,
      "tipo": "inicio",
      "latitud": -1.673,
      "longitud": -78.648
    },
    {
      "orden": 2,
      "tipo": "sitio",
      "id_sitio": 10
    },
    {
      "orden": 3,
      "tipo": "fin",
      "latitud": -1.675,
      "longitud": -78.651
    }
  ]
}
```

La API reemplaza la geometria previa:

- `gis.rutas_turistica.geom_linea` se actualiza con la linea enviada o queda
  `NULL` si no hay linea.
- `gis.ruta_puntos` se reemplaza completo para esa ruta.
- Los puntos `sitio` guardan `id_sitio`.
- Los puntos `inicio` y `libre` guardan `punto_inicio` cuando no son solo una
  referencia a sitio.
- Los puntos `fin` guardan `punto_fin`.

### Subir imagen de ruta

```http
POST /api/v1/admin/rutas-turisticas/imagen
Content-Type: multipart/form-data
```

Campos:

```txt
titulo_ruta=Ruta del Hielo
archivo=<un archivo image/*>
```

La API guarda el archivo en:

```txt
fuente_datos/imagenes/rutas/{titulo-de-la-ruta}/
```

Respuesta:

```json
{
  "nombre_archivo": "archivo.jpg",
  "url": "/api/v1/imagenes/rutas/ruta-del-hielo/archivo.jpg"
}
```

### Actualizar ruta

```http
PATCH /api/v1/admin/rutas-turisticas/{id_ruta}
```

Body parcial:

```json
{
  "titulo": "Ruta del Hielo actualizada",
  "url_imagen": "/api/v1/imagenes/rutas/ruta-del-hielo/nueva.jpg",
  "activo": false
}
```

Si `url_imagen` cambia y la URL anterior apuntaba a un archivo local bajo
`/api/v1/imagenes/rutas/...`, la API elimina el archivo anterior del
filesystem. Si la URL anterior era externa, no se elimina ningun archivo.

### Cambiar estado de ruta

```http
PATCH /api/v1/admin/rutas-turisticas/{id_ruta}/estado
```

Body:

```json
{
  "activo": false
}
```

Actualiza solo `gis.rutas_turistica.activo`. Este endpoint se usa desde el
badge `Activo/Inactivo` del panel.

### Eliminar ruta

```http
DELETE /api/v1/admin/rutas-turisticas/{id_ruta}
```

Elimina fisicamente el registro en `gis.rutas_turistica`. Las tablas
dependientes como `gis.documento_ruta` y `gis.ruta_puntos` se eliminan por
`ON DELETE CASCADE`. Tambien elimina del filesystem la imagen local asociada a
`url_imagen` cuando pertenece a `/api/v1/imagenes/rutas/...`. Las URLs externas
no se eliminan.

## Noticias Turisticas Admin

Base:

```txt
/api/v1/admin/noticias
```

### Listar noticias

```http
GET /api/v1/admin/noticias
```

Query params:

```txt
q=festival
estado=activo|inactivo|publicada|vencida|all
page=1
page_size=12
```

Respuesta:

```json
{
  "page": 1,
  "page_size": 12,
  "total": 1,
  "items": [
    {
      "id_noticia": 1,
      "titulo": "Festival de las Frutas y las Flores 2026",
      "imagen_url": "/api/v1/imagenes/noticias/festival/imagen.jpg",
      "fecha_inicio": "2026-06-01",
      "fecha_fin": "2026-06-30",
      "activa": true,
      "estado_visual": "publicada"
    }
  ]
}
```

`estado_visual` se calcula en la API:

```txt
publicada -> activa=true y sin fecha_fin vencida
vencida     -> fecha_fin < hoy
inactiva    -> activa=false
```

### Crear noticia

```http
POST /api/v1/admin/noticias
```

Body:

```json
{
  "titulo": "Festival de las Frutas y las Flores 2026",
  "imagen_url": "/api/v1/imagenes/noticias/festival/imagen.jpg",
  "fecha_inicio": "2026-06-01",
  "fecha_fin": "2026-06-30",
  "activa": true
}
```

Respuesta: `201 Created` con el mismo formato de un item de listado.

### Detalle de noticia

```http
GET /api/v1/admin/noticias/{id_noticia}
```

### Actualizar noticia

```http
PATCH /api/v1/admin/noticias/{id_noticia}
```

Body parcial:

```json
{
  "titulo": "Festival actualizado",
  "fecha_fin": "2026-07-15",
  "activa": true
}
```

Si `imagen_url` cambia y la URL anterior apuntaba a un archivo local bajo
`/api/v1/imagenes/noticias/...`, la API elimina el archivo anterior del
filesystem.

### Cambiar estado de noticia

```http
PATCH /api/v1/admin/noticias/{id_noticia}/estado
```

Body:

```json
{
  "activa": false
}
```

Actualiza solo `turismo.noticia.activa`. Este endpoint se usa desde el badge
del panel.

### Eliminar noticia

```http
DELETE /api/v1/admin/noticias/{id_noticia}
```

Elimina fisicamente el registro en `turismo.noticia`. Tambien elimina del
filesystem la imagen local asociada a `imagen_url` cuando pertenece a
`/api/v1/imagenes/noticias/...`.

### Subir imagen de noticia

```http
POST /api/v1/admin/noticias/imagen
Content-Type: multipart/form-data
```

Campos:

```txt
titulo_noticia=Festival de las Frutas
archivo=<un archivo image/*>
```

La API guarda el archivo en:

```txt
fuente_datos/imagenes/noticias/{titulo-de-la-noticia}/
```

Respuesta:

```json
{
  "nombre_archivo": "archivo.jpg",
  "url": "/api/v1/imagenes/noticias/festival-de-las-frutas/archivo.jpg"
}
```

## Noticias Usuario (App movil)

Base:

```txt
/api/v1/noticias
```

### Listar noticias vigentes

```http
GET /api/v1/noticias/usuario
```

No requiere autenticacion. Devuelve solo noticias que cumplan:

```txt
activa = true
fecha_inicio <= hoy
fecha_fin es null o fecha_fin >= hoy
```

Respuesta:

```json
{
  "total": 2,
  "noticias": [
    {
      "id_noticia": 1,
      "titulo": "Festival de las Frutas y las Flores 2026",
      "imagen_url": "/api/v1/imagenes/noticias/festival/imagen.jpg",
      "fecha_inicio": "2026-06-01",
      "fecha_fin": "2026-06-30"
    }
  ]
}
```

Las URLs de imagen relativas (`/api/v1/imagenes/...`) deben resolverse contra el
dominio base del backend en la app movil.

## Contenido Chatbots Admin

Base:

```txt
/api/v1/admin/contenido-chatbots
```

Repositorios Markdown por sitio o ruta turística. Los archivos viven en
`fuente_datos/mardowks/{sitios|rutas}/{slug}/`. Los embeddings para RAG se generan
al guardar secciones del documento.

### Permisos por acción

| Acción BD | Endpoints típicos |
|-----------|-------------------|
| `ver` | Listar entidades, repositorios, leer contenido |
| `crear` | Crear repositorio para admins globales; crear documento |
| `actualizar` | Renombrar repositorio para admins globales; metadatos de documento; editar contenido Markdown |
| `eliminar` | Eliminar repositorio para admins globales; eliminar documento |
| `exportar` | Regenerar chunk de descripción |

Admins con permisos por sitio, incluido el cargo Dueño, reciben repositorios
automáticos para sus sitios asignados. Pueden crear, editar y eliminar documentos,
pero no crear, renombrar ni eliminar el repositorio/contenedor del sitio.

### Buscar entidades

```http
GET /api/v1/admin/contenido-chatbots/entidades?q=chimborazo&tipo=sitio|all&limit=20
```

### Repositorios

```http
GET    /api/v1/admin/contenido-chatbots/repositorios
POST   /api/v1/admin/contenido-chatbots/repositorios
PATCH  /api/v1/admin/contenido-chatbots/repositorios/{slug}
DELETE /api/v1/admin/contenido-chatbots/repositorios/{slug}
```

Body POST (crear repositorio):

```json
{
  "origen": "sitio",
  "id_vinculo": 1
}
```

La limpieza de documentos huérfanos en disco se ejecuta como máximo una vez cada
5 minutos al listar repositorios (no en cada GET).

### Documentos

```http
POST   /api/v1/admin/contenido-chatbots/repositorios/{slug}/documentos
PATCH  /api/v1/admin/contenido-chatbots/documentos/{id_documento}
GET    /api/v1/admin/contenido-chatbots/documentos/{id_documento}/contenido
PUT    /api/v1/admin/contenido-chatbots/documentos/{id_documento}/contenido
DELETE /api/v1/admin/contenido-chatbots/documentos/{id_documento}
```

Permisos:

- Crear documento: `chatbot_content.crear`.
- Editar metadatos o contenido Markdown: `chatbot_content.actualizar`.
- Ver contenido: `chatbot_content.ver`.
- Eliminar documento: `chatbot_content.eliminar`.

### Regenerar chunk de descripción

```http
POST /api/v1/admin/contenido-chatbots/chunks/descripcion
```

```json
{
  "origen": "sitio",
  "id_vinculo": 1
}
```

Regenera el chunk RAG a partir de `descripcion_corta` (sitio) o `descripcion` (ruta).
Valida acceso al vínculo según permisos del usuario.

## Registro de acciones Admin

Base:

```txt
/api/v1/admin/registro-acciones
```

### Listar acciones

```http
GET /api/v1/admin/registro-acciones
```

Query params:

```txt
q=chimborazo
usuario=admin
modulo=attractions|categories|routes|noticias|chatbot_content|admin_accounts|sistema|all
accion=creacion|edicion|actualizacion|desactivacion|eliminacion|sesion|all
fecha_inicio=YYYY-MM-DD
fecha_fin=YYYY-MM-DD
page=1
page_size=10
```

Respuesta:

```json
{
  "page": 1,
  "page_size": 10,
  "total": 1,
  "items": [
    {
      "id_evento": 103,
      "administrador": "Maria Yanez",
      "username": "admin",
      "iniciales": "MY",
      "accion": "INSERT",
      "accion_label": "Creacion",
      "accion_tipo": "creacion",
      "modulo": "noticias",
      "modulo_label": "Noticias",
      "direccion": "192.168.1.24",
      "fecha_modificacion": "2026-06-17T10:33:25-05:00"
    }
  ]
}
```

Fuente: `trazabilidad.accion`.

Cada item expone `direccion` con la IP del administrador al momento de la
accion (`host(t.ip)`). Si no hay IP registrada, el valor es `"—"`.

La paginación aplica el filtro `accion` (tipo visual) directamente en SQL, sin cargar
todo el historial en memoria.

### Catalogos para filtros

```http
GET /api/v1/admin/registro-acciones/catalogos
```

### Detalle de accion

```http
GET /api/v1/admin/registro-acciones/{id_evento}
```

Incluye `direccion`, `datos_anteriores` y `datos_nuevos` sanitizados.
El panel muestra la comparacion en dos columnas con resaltado tipo diff
(rojo para eliminado, verde para agregado).

## Politica de imagenes locales

La API solo elimina archivos del filesystem cuando la URL pertenece al prefijo
estatico administrado por el proyecto:

```txt
/api/v1/imagenes/...
```

Para atractivos, los archivos se guardan bajo:

```txt
fuente_datos/imagenes/{nombre-del-sitio}/
```

Para rutas, los archivos se guardan bajo:

```txt
fuente_datos/imagenes/rutas/{titulo-de-la-ruta}/
```

Para noticias, los archivos se guardan bajo:

```txt
fuente_datos/imagenes/noticias/{titulo-de-la-noticia}/
```

Las URLs externas se conservan intactas porque la API no controla esos
recursos. Si una carpeta local queda vacia despues de eliminar archivos, la API
intenta remover tambien la carpeta.

### Series temporales

```http
GET /api/v1/admin/dashboard/series
```

Query params:

```txt
metric=preguntas
periodo=week
agrupar_por=hour|day|week|month|year
comparar_por=none|tipo_chatbot|categoria|subcategoria|estado
```

Respuesta:

```json
{
  "metric": "preguntas",
  "periodo": "week",
  "agrupar_por": "day",
  "comparar_por": "tipo_chatbot",
  "series": []
}
```

### Distribucion

```http
GET /api/v1/admin/dashboard/distribucion
```

Query params:

```txt
metric=preguntas|favoritos|atractivos|noticias|rutas
dimension=tipo_chatbot|categoria|subcategoria|estado|sitio
periodo=month
limit=10
```

Respuesta:

```json
{
  "metric": "preguntas",
  "dimension": "tipo_chatbot",
  "periodo": "month",
  "items": [
    { "label": "general", "key": "general", "valor": 10 }
  ]
}
```

### Ranking

```http
GET /api/v1/admin/dashboard/ranking
```

Query params:

```txt
tipo=sitios_consultados|sitios_favoritos|categorias_buscadas|subcategorias_buscadas|rutas_consultadas
periodo=month
limit=5
categoria=Naturaleza
subcategoria=Volcanes
tipo_chatbot=general|sitio|all
```

Respuesta:

```json
{
  "tipo": "sitios_favoritos",
  "periodo": "month",
  "limit": 5,
  "items": [
    {
      "posicion": 1,
      "id": 1,
      "nombre": "Volcan Chimborazo",
      "valor": 12
    }
  ]
}
```

Nota: `rutas_consultadas` lista rutas activas desde `gis.rutas_turistica`.
Cuando exista una tabla de eventos de consulta de rutas, el valor debe pasar a
representar consultas reales.

### Consultas

```http
GET /api/v1/admin/dashboard/consultas
```

Query params:

```txt
periodo=month
tipo_chatbot=general|sitio|all
categoria=Naturaleza
subcategoria=Volcanes
id_sitio=1
q=wifi
page=1
page_size=20
orden=fecha_desc|fecha_asc
```

Respuesta:

```json
{
  "page": 1,
  "page_size": 20,
  "total": 0,
  "items": []
}
```

### Análisis semántico

```http
GET /api/v1/admin/dashboard/semantica
```

Permiso: `analytics`.

Query params:

```txt
periodo=month
fecha_inicio=YYYY-MM-DD
fecha_fin=YYYY-MM-DD
categoria=Naturaleza
subcategoria=Volcanes
canal=exploracion|pregunta_directa|all
limit=30
umbral=0.82
max_consultas_analisis=10000
min_total_consultas=20
```

Agrupa preguntas de usuario (`rol='usuario'`) por similitud coseno de embeddings
(Voyage). `limit` controla cuantos grupos se devuelven; `max_consultas_analisis`
controla cuantas preguntas elegibles se analizan antes de agrupar.
`min_total_consultas` filtra los grupos ya agrupados para mostrar solo patrones
con volumen suficiente; por defecto el panel usa grupos de 20 o mas consultas.
En el panel administrativo esta consulta no se ejecuta al abrir la pantalla de
Analisis de consultas: primero se muestra el selector de periodo y solo se llama
al endpoint cuando el usuario presiona `Aplicar filtros`.
Fuentes:

- `conversacion.mensaje_explorador` (`canal=exploracion`, `tipo_chatbot=general`)
- `conversacion.mensaje_detalle` (`canal=pregunta_directa`, `tipo_chatbot=sitio`)

La respuesta se cachea en Redis por un TTL corto usando claves
`dashboard:semantica:v1:{hash_filtros}`. Este prefijo es exclusivo del dashboard
administrativo y no comparte espacio con codigos de correo, actividad de sesion ni
cache de embeddings.

Respuesta:

```json
{
  "periodo": "month",
  "total_grupos": 2,
  "total_consultas_agrupadas": 42,
  "resumen": {
    "consultas_totales": 42,
    "total_preguntas_usuario": 8058,
    "total_mensajes_historial": 16116,
    "preguntas_con_embedding": 8058,
    "preguntas_sin_embedding": 0,
    "preguntas_analizadas": 8058,
    "categoria_mas_frecuente": { "label": "Manifestaciones Culturales", "valor": 42 },
    "entidad_mas_relacionada": { "label": null, "valor": 0 }
  },
  "grupos": [
    {
      "id_grupo": 1,
      "consulta_representativa": "museos cerca",
      "total_consultas": 42,
      "tipo_chatbot": "general",
      "canal": "exploracion",
      "similitud_promedio": 0.94,
      "ultima_fecha": "2026-07-01T12:00:00Z",
      "preguntas_relacionadas": [
        {
          "pregunta": "museos cerca",
          "total_consultas": 24,
          "categoria": "Manifestaciones Culturales",
          "subcategoria": "Museos",
          "entidad": null,
          "tipo_chatbot": "general",
          "canal": "exploracion",
          "ultima_fecha": "2026-07-01T12:00:00Z"
        },
        {
          "pregunta": "quiero visitar museos",
          "total_consultas": 18,
          "categoria": "Manifestaciones Culturales",
          "subcategoria": "Museos",
          "entidad": null,
          "tipo_chatbot": "general",
          "canal": "exploracion",
          "ultima_fecha": "2026-06-28T09:30:00Z"
        }
      ],
      "consultas": []
    }
  ]
}
```

Admins con alcance por sitio solo reciben mensajes del chatbot de sitio vinculados a
sus `id_sitio` permitidos.

## Favoritos Usuario

Base:

```txt
/api/v1/favoritos
```

Requiere `Authorization: Bearer jwt-sesion` de un usuario autenticado (`rol=usuario`).

### Listar favoritos

```http
GET /api/v1/favoritos
```

No requiere body. El `id_usuario` se toma del JWT.

Respuesta:

```json
{
  "total": 1,
  "favoritos": [
    {
      "id_favorito": 1,
      "id_sitio": 41,
      "nombre": "Volcan Chimborazo",
      "categoria": "Naturaleza",
      "subcategoria": "Volcanes",
      "descripcion_corta": "El punto mas alto del Ecuador.",
      "imagen_principal": "/api/v1/imagenes/volcan-chimborazo/imagen.jpg",
      "ubicacion": { "latitud": -1.4691, "longitud": -78.8175 },
      "fecha_agregado": "2026-06-17T10:00:00Z"
    }
  ]
}
```

### Agregar favorito

```http
POST /api/v1/favoritos/{id_sitio}
```

No requiere body. Solo el `id_sitio` en la ruta y el JWT del usuario.

Respuesta:

```json
{
  "message": "Sitio agregado a favoritos correctamente",
  "id_sitio": 41,
  "es_favorito": true
}
```

Errores comunes:

```json
{ "detail": "Sitio no encontrado" }
```

```json
{ "detail": "El sitio ya esta en favoritos" }
```

### Eliminar favorito

```http
DELETE /api/v1/favoritos/{id_sitio}
```

### Verificar estado

```http
GET /api/v1/favoritos/{id_sitio}/estado
```

Respuesta:

```json
{
  "id_sitio": 41,
  "es_favorito": true
}
```

## App móvil — Sitios

Base: `/api/v1/sitios`. No requiere autenticación.

```http
GET  /api/v1/sitios/categorias
GET  /api/v1/sitios/subcategorias?id_categoria=1
GET  /api/v1/sitios/?id_categoria=1&id_subcategoria=2&nombre=chimborazo
POST /api/v1/sitios/cache/cargar
PUT  /api/v1/sitios/cache/{id_sitio}
DELETE /api/v1/sitios/cache/{id_sitio}
```

El cache en memoria acelera listados; los endpoints `cache/*` son de mantenimiento
interno o sincronización tras cambios en el panel.

## App móvil — Ficha de sitio

```http
GET /api/v1/ficha_sitio/{id_sitio}
```

Detalle completo para la pantalla de ficha: horario, contactos, multimedia, precios,
atributos booleanos.

## App móvil — Rutas turísticas

Base: `/api/v1/rutas-movil-turismo`

```http
GET /api/v1/rutas-movil-turismo
GET /api/v1/rutas-movil-turismo/{id_ruta}
```

Solo rutas activas con geometría para mapa móvil.

## App móvil — Rutas de buses

Base: `/api/v1/rutas-buses`

```http
GET /api/v1/rutas-buses/
GET /api/v1/rutas-buses/leyenda
GET /api/v1/rutas-buses/{id_ruta}
```

## App móvil — Historial de conversaciones

Base: `/api/v1/historial`. Requiere JWT de usuario (`rol=usuario`).

```http
GET /api/v1/historial/conversaciones?tipo=general|sitio|detalle|todos&limit=50&offset=0
GET /api/v1/historial/conversaciones/{id_conversacion}/mensajes?tipo=general|detalle|sitio
```

**Nota:** cuando la conversación pertenece a un sitio turístico, `entidad_asociada` se resuelve como `{ tipo: "sitio", id, nombre }` y el `titulo` del resumen prioriza el nombre del sitio. En mensajes de tipo detalle/sitio, cada item puede llevar `entidad_asociada` con el sitio resuelto.

## Compartido — Comprobar archivos

```http
GET /api/v1/comprobar_archivos/{id_sitio}
```

Verifica existencia de archivos multimedia locales registrados para un sitio.

## Chatboot

> **Documentación vigente:** [`chatboot_arquitectura_api.md`](chatboot_arquitectura_api.md)

Las herramientas del planificador viven bajo `/api/v1/chatboot/herramientas/*`.
La pregunta directa (chatbot de sitio) bajo `/api/v1/chatboot/pregunta-directa/*`.

No requieren JWT. Deben exponerse en red interna.

| Área | Base |
|------|------|
| Exploración H1–H10 + historial | `/api/v1/chatboot/herramientas` |
| Pregunta directa (ficha, chunks, multimedia) | `/api/v1/chatboot/pregunta-directa` |
| Resolver sitio por nombre | `POST .../herramientas/pregunta-directa` |

El monolito legacy `POST /api/v1/chatboot/*` está documentado en
[`chatboot_apis.md`](chatboot_apis.md) solo como referencia histórica.

## Errores comunes

Periodo custom sin fechas:

```json
{
  "detail": "fecha_inicio y fecha_fin son obligatorias para periodo=custom"
}
```

Parametro fuera del catalogo:

```json
{
  "detail": [
    {
      "type": "literal_error",
      "loc": ["query", "metric"],
      "msg": "Input should be ..."
    }
  ]
}
```

## Autorizacion del panel administrativo

Roles de panel:

| Rol | Acceso |
|-----|--------|
| `super-admin` | Todos los modulos, todos los sitios, gestion de cuentas/cargos |
| `admin` | Modulos y acciones en `conversacion.usuario_permiso`; alcance global o por sitio |

### Acciones por modulo

Cada permiso en BD usa el enum `conversacion.accion_t`: `ver`, `crear`, `actualizar`,
`eliminar`, `exportar`.

| Modulo panel | Codigo | Acciones tipicas por endpoint |
|--------------|--------|-------------------------------|
| Dashboard | `dashboard` | `ver` — resumen, metricas, series, distribucion, ranking |
| Analisis | `analytics` | `ver` — `/consultas`, `/semantica` |
| Atractivos | `attractions` | `ver` listado/detalle; `crear` POST; `actualizar` PUT/PATCH estado; `eliminar` DELETE |
| Categorias | `categories` | `ver` GET; `crear` POST; `actualizar` PATCH; `eliminar` DELETE |
| Rutas | `routes` | Igual patron que noticias/atractivos |
| Noticias | `noticias` | Igual patron |
| Registro | `action_log` | `ver` |
| Contenido chatbots | `chatbot_content` | `ver`, `crear`, `actualizar` (incluye contenido Markdown), `eliminar`, `exportar` (regenerar chunks) |
| Cuentas admin | `admin_accounts` | Solo `super-admin` |

### Alcance por sitio

- Permiso con `id_sitio IS NULL` → alcance **global** para ese modulo/accion.
- Permiso con `id_sitio` concreto → solo ese sitio (listados, dashboard, contenido chatbot).
- Super-admin ignora restricciones de sitio.

Asignacion de sitios a una cuenta admin (solo super-admin):

```http
GET /api/v1/admin/cuentas/{id_usuario}/sitios
PUT /api/v1/admin/cuentas/{id_usuario}/sitios
```

```json
{ "sitios": [1, 5, 12] }
```

Los IDs deben existir en `turismo.sitio`. Al asignar sitios se insertan permisos
de dueno (`attractions`: ver/actualizar; `chatbot_content`:
ver/crear/actualizar/eliminar/exportar; `analytics`: ver) por cada sitio. También
se asegura automáticamente un repositorio de contenido para cada sitio asignado.

Matriz modulo / router (referencia rapida):

| Modulo panel | Codigo permiso | Router |
|--------------|----------------|--------|
| Dashboard | `dashboard` | `/admin/dashboard/*` excepto consultas y semantica |
| Analisis de consultas | `analytics` | `/admin/dashboard/consultas`, `/admin/dashboard/semantica` |
| Atractivos | `attractions` | `/admin/atractivos` (sitios, imagenes; no categorias) |
| Categorias | `categories` | `/admin/atractivos/categorias*`, `/subcategorias*` |
| Rutas | `routes` | `/admin/rutas-turisticas` |
| Noticias | `noticias` | `/admin/noticias` |
| Registro de acciones | `action_log` | `/admin/registro-acciones` |
| Contenido chatbots | `chatbot_content` | `/admin/contenido-chatbots` |
| Cuentas administrativas | `admin_accounts` | Solo super-admin via `/admin/cuentas` |

## Cuentas administrativas

Base path (solo `super-admin`):

```txt
/api/v1/admin/cuentas
```

### Listar cuentas

```http
GET /api/v1/admin/cuentas?q=maria&id_cargo=2&activo=true&page=1&page_size=10
```

Respuesta:

```json
{
  "items": [
    {
      "id_usuario": 3,
      "nombre_completo": "Andrea Pilco",
      "email": "andrea.pilco@riobambatour.gob.ec",
      "username": "andrea.pilco",
      "id_cargo": 3,
      "cargo_nombre": "Analista",
      "activo": true,
      "ultimo_acceso_en": "2026-06-15T09:00:00Z",
      "iniciales": "AP"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

### Crear cuenta

```http
POST /api/v1/admin/cuentas
```

```json
{
  "nombre_completo": "Andrea Pilco",
  "email": "andrea.pilco@riobambatour.gob.ec",
  "id_cargo": 3,
  "activo": true,
  "permisos": ["dashboard", "attractions", "categories", "routes", "chatbot_content"]
}
```

La contrasena inicial es generada automaticamente y se envia por correo
al email de la cuenta creada.

### Actualizar cuenta

```http
PATCH /api/v1/admin/cuentas/{id_usuario}
```

### Cambiar estado

```http
PATCH /api/v1/admin/cuentas/{id_usuario}/estado
```

```json
{
  "activo": false
}
```

### Eliminar cuenta

```http
DELETE /api/v1/admin/cuentas/{id_usuario}
```

## Cargos y permisos

```http
GET /api/v1/admin/cargos
GET /api/v1/admin/cargos/{id_cargo}
POST /api/v1/admin/cargos
PATCH /api/v1/admin/cargos/{id_cargo}
DELETE /api/v1/admin/cargos/{id_cargo}
GET /api/v1/admin/permisos
```

Ejemplo de cargo:

```json
{
  "nombre": "Analista",
  "activo": true,
  "permisos": ["dashboard", "analytics", "attractions"]
}
```
