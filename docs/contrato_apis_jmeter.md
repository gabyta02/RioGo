# Contrato de APIs para pruebas de desempeño en Apache JMeter

Documento de referencia para configurar pruebas de carga contra el backend FastAPI de RiobambaGo. Cubre los endpoints HTTP relevantes para desempeño: health, autenticación, app móvil pública, favoritos, historial y herramientas chatboot.

**Alcance:** ~45 endpoints REST bajo `/api/v1` más `GET /`. No incluye panel admin (`/admin/*`), WebSockets ni operaciones de caché interna de sitios.

**Fuentes internas:** [`apis/docs/contratos_apis.md`](../apis/docs/contratos_apis.md), [`apis/docs/autentificacion.md`](../apis/docs/autentificacion.md), [`apis/docs/chatboot_arquitectura_api.md`](../apis/docs/chatboot_arquitectura_api.md), [`apis/tests/probar_apis_chatboot.py`](../apis/tests/probar_apis_chatboot.py).

---

## 1. URLs base

| Entorno | Base URL | Notas |
|---------|----------|-------|
| Producción (nginx) | `https://riobambatour.org` | Prefijo API: `/api/v1` |
| Local (docker) | `http://localhost` | Proxy nginx en puerto 80 |
| API directa (debug) | `http://localhost:8000` | Sin nginx; útil en desarrollo |

Todas las respuestas de la API son JSON salvo `GET /api/v1/imagenes/*` (binario).

---

## 2. Configuración JMeter

### 2.1 Variables globales recomendadas

| Variable | Ejemplo | Uso |
|----------|---------|-----|
| `BASE_URL` | `http://localhost` | Dominio del Test Plan |
| `API_PREFIX` | `/api/v1` | Prefijo común |
| `ACCESS_TOKEN` | (extraído de login) | JWT de acceso |
| `ID_SITIO` | `1` | ID de sitio activo en BD |
| `ID_RUTA` | `1` | ID de ruta turística activa |
| `ID_CONVERSACION` | `10` | ID de conversación del usuario |

### 2.2 Header Manager estándar

Aplicar en el Thread Group (los valores dinámicos se sobrescriben en el PreProcessor):

```http
Content-Type: application/json
Authorization: Bearer ${ACCESS_TOKEN}
```

`Authorization` solo en samplers que requieran Bearer. `Content-Type` no aplica en `GET` sin body.

### 2.3 Cookie Manager (refresh de sesión)

Para `POST /api/v1/auth/refresh`:

- Añadir **HTTP Cookie Manager** al Thread Group.
- Marcar **Clear cookies each iteration** solo si cada iteración hace login completo.
- La cookie `refresh_token` es `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/api/v1/auth`.
- Tras `POST /auth/login`, JMeter almacena la cookie automáticamente si el Cookie Manager está activo.

### 2.4 Extracción de token tras login

**JSON Extractor** en `POST /auth/login`:

| Campo | Valor |
|-------|-------|
| Names of created variables | `ACCESS_TOKEN` |
| JSON Path expressions | `$.access_token` |
| Match No. | `1` |

Usar `${ACCESS_TOKEN}` en el header `Authorization: Bearer ${ACCESS_TOKEN}`.

---

## 3. Matriz de autenticación

No existe rol JWT “invitado”. **Invitado** = petición publica sin `Authorization`.

| Nivel | Headers requeridos | Endpoints en este documento |
|-------|-------------------|----------------------------|
| **Público / invitado** | Ninguno | Sitios, ficha, rutas, buses, noticias, comprobar archivos, imágenes, chatboot, auth pre-login (login, refresh, verificación correo) |
| **Usuario autenticado** | `Authorization: Bearer <access_token>` | `/favoritos/*`, `/historial/*`, `/auth/me`, `/auth/logout` |
| **Panel admin** | Bearer + rol `admin`/`super-admin` + permisos módulo | **Fuera de alcance** |
| **Super-admin** | Bearer + rol `super-admin` | **Fuera de alcance** |

### Resumen por header

| Header | ¿Cuándo? |
|--------|----------|
| `Authorization: Bearer` | Favoritos, historial, `/auth/me`, `/auth/logout` |
| Cookie `refresh_token` | Solo `POST /auth/refresh` |

---

## 4. Catálogo de datos de prueba válidos

| Dato | Valor | Uso |
|------|-------|-----|
| Coordenadas Riobamba | `lat: -1.6736, lon: -78.6473` | GIS, búsqueda por cercanía |
| Referencia ubicación | `"mercado la condamine"` | `busqueda-ubicacion` |
| Referencia dirección | `"jose veloz y morona"` | `busqueda-referencia` |
| Texto semántico | `"museo con exposiciones de arte colonial"` | `busqueda-semantica-consulta` |
| Keywords semánticas | `["arte colonial", "colonial"]` | `busqueda-semantica-consulta` |
| Tipo ruta | `"senderismo"` | `ruta-consulta` |
| Contacto sugerido | `"whatsapp"` | `contacto-busqueda` |
| Password ejemplo (docs) | `Password123` | Login usuario de prueba |
| Email ejemplo (docs) | `usuario@example.com` | Registro |
| Código verificación (docs) | `123456` | Registro / 2FA |
| `id_sitio` / `id_ruta` | Obtener de `GET /sitios/` o `GET /rutas-movil-turismo` | Deben existir y estar activos en BD |

**Credenciales:** no hay usuarios sembrados por defecto. Crear usuario de prueba con `POST /auth/registro/usuario` o usar credenciales del entorno de staging. Para admin con 2FA, solicitar código con `POST /auth/correo/verificacion` (`proposito: login_2fa`).

---

## 5. Plantilla de referencia

Cada endpoint sigue esta estructura:

| Campo | Descripción |
|-------|-------------|
| Nombre funcional | Propósito de negocio |
| Método / Ruta | HTTP method y path |
| `Bearer` | Sí / No |
| Permisos especiales | RBAC u otros |
| Headers obligatorios | Lista |
| Parámetros | Query, path, body |
| Body de ejemplo | JSON si aplica |
| Respuesta esperada | Esquema resumido (200) |
| Códigos de estado | HTTP relevantes |
| Datos válidos de prueba | Valores concretos |
| Restricciones | Límites, side effects |

---

## 6. Health

### Health check API

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/` |
| `Bearer` | No |
| Permisos especiales | Ninguno |

**Headers obligatorios:** ninguno.

**Parámetros:** ninguno.

**Respuesta esperada (200):**

```json
{ "message": "API funcionando" }
```

**Códigos de estado:** `200`

**Datos válidos de prueba:** N/A

**Restricciones:** útil como smoke test antes de la batería de carga; no valida BD ni Redis.

---

## 7. Autenticación

Base: `/api/v1/auth`.

### 7.1 Login

| Campo | Valor |
|-------|-------|
| Nombre funcional | Iniciar sesión y obtener access token + cookie refresh |
| Método | `POST` |
| Ruta | `/api/v1/auth/login` |
| `Bearer` | No |
| Permisos especiales | Ninguno |

**Headers obligatorios:** `Content-Type: application/json`

**Body de ejemplo (usuario móvil):**

```json
{
  "username": "usuario1",
  "password": "Password123"
}
```

**Body de ejemplo (cuenta con 2FA):**

```json
{
  "username": "admin",
  "password": "Password123",
  "codigo_verificacion": "123456",
  "token_verificacion": "jwt-temporal"
}
```

**Respuesta esperada (200):**

```json
{
  "access_token": "eyJ...",
  "token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 900,
  "token_refresh_in": 1800,
  "inactividad_max_segundos": null,
  "rol": "usuario",
  "permisos": [],
  "usuario": {
    "id_usuario": 1,
    "username": "usuario1",
    "email": "usuario@example.com",
    "rol": "usuario",
    "activo": true,
    "autentificacion_doble": false
  }
}
```

Además: header `Set-Cookie: refresh_token=...; HttpOnly; Path=/api/v1/auth`.

**Códigos de estado:** `200`, `401` (credenciales inválidas), `422` (validación), `500`

**Datos válidos de prueba:** usuario activo en BD; para 2FA, flujo previo de verificación correo.

**Restricciones:** access token TTL 15 min; el refresh persistente se guarda por sesion/dispositivo en `conversacion.sesion_usuario`; usar en Setup Thread Group para escenarios autenticados.

---

### 7.2 Renovar sesión (refresh)

| Campo | Valor |
|-------|-------|
| Nombre funcional | Renovar access token con cookie refresh |
| Método | `POST` |
| Ruta | `/api/v1/auth/refresh` |
| `Bearer` | No |
| Permisos especiales | Ninguno |

**Headers obligatorios:** ninguno

**Parámetros:** cookie `refresh_token` (HttpOnly, gestionada por Cookie Manager).

**Body:** ninguno.

**Respuesta esperada (200):** misma estructura que login (`access_token`, `usuario`, etc.).

**Códigos de estado:** `200`, `401` (refresh inválido/expirado/revocado), `500`

**Restricciones:** cada refresh rota el token persistente de la misma sesion; admins con inactividad > 30 min reciben `401 Sesion expirada por inactividad` en rutas del panel o al renovar `X-Admin-Session-Id`.

---

### 7.3 Perfil del usuario autenticado

| Campo | Valor |
|-------|-------|
| Nombre funcional | Obtener datos del usuario logueado |
| Método | `GET` |
| Ruta | `/api/v1/auth/me` |
| `Bearer` | **Sí** |
| Permisos especiales | Usuario activo con JWT válido |

**Headers obligatorios:** `Authorization: Bearer <access_token>`

**Respuesta esperada (200):**

```json
{
  "id_usuario": 1,
  "username": "usuario1",
  "email": "usuario@example.com",
  "rol": "usuario",
  "activo": true,
  "autentificacion_doble": false,
  "foto_url": null,
  "permisos": [],
  "sitios_asignados": []
}
```

**Códigos de estado:** `200`, `401`, `403`

---

### 7.4 Cerrar sesión

| Campo | Valor |
|-------|-------|
| Nombre funcional | Revocar sesión y cookie refresh |
| Método | `POST` |
| Ruta | `/api/v1/auth/logout` |
| `Bearer` | **Sí** |
| Permisos especiales | Ninguno |

**Respuesta esperada (200):**

```json
{ "mensaje": "Sesion cerrada correctamente" }
```

**Códigos de estado:** `200`, `401`

**Restricciones:** usar en teardown; invalida refresh token en BD.

---

### 7.5 Solicitar código de verificación por correo

| Campo | Valor |
|-------|-------|
| Nombre funcional | Enviar código de 6 dígitos por email |
| Método | `POST` |
| Ruta | `/api/v1/auth/correo/verificacion` |
| `Bearer` | No |

**Body de ejemplo (registro):**

```json
{
  "proposito": "registro_usuario",
  "email": "usuario@example.com"
}
```

**Body de ejemplo (2FA login):**

```json
{
  "proposito": "login_2fa",
  "username": "admin"
}
```

**Valores `proposito`:** `registro_usuario`, `login_2fa`, `eliminar_cuenta`, `actualizar_credenciales`, `recuperar_password`

**Respuesta esperada (200):**

```json
{
  "mensaje": "Codigo de verificacion enviado",
  "token_verificacion": "eyJ...",
  "expira_en_minutos": 10
}
```

**Códigos de estado:** `200`, `400`, `422`, `429` (rate limit correo)

**Restricciones:** código TTL 10 min; en pruebas de carga masiva puede saturar el servicio de correo — usar con moderación.

---

### 7.6 Reenviar código de verificación

| Campo | Valor |
|-------|-------|
| Nombre funcional | Reenviar código (invalida el anterior) |
| Método | `POST` |
| Ruta | `/api/v1/auth/correo/reenviar` |
| `Bearer` | No |

Mismo body y respuesta que §7.5.

---

### 7.6.1 Solicitar recuperación de contraseña

| Campo | Valor |
|-------|-------|
| Nombre funcional | Enviar código para cambiar contraseña sin sesión |
| Método | `POST` |
| Ruta | `/api/v1/auth/recuperacion/password/solicitar` |
| `Bearer` | No |

**Body de ejemplo:**

```json
{
  "email": "usuario@example.com"
}
```

**Respuesta esperada (200, genérica):**

```json
{
  "mensaje": "Si el correo corresponde a una cuenta activa, enviaremos un codigo para continuar.",
  "token_verificacion": "eyJ...",
  "expira_en_minutos": 10
}
```

**Códigos de estado:** `200`, `422`, `429` (rate limit correo)

**Restricciones:** no revela si el correo existe.

---

### 7.6.2 Confirmar recuperación de contraseña

| Campo | Valor |
|-------|-------|
| Nombre funcional | Cambiar contraseña con código de recuperación |
| Método | `POST` |
| Ruta | `/api/v1/auth/recuperacion/password/confirmar` |
| `Bearer` | No |

**Body de ejemplo:**

```json
{
  "email": "usuario@example.com",
  "nuevo_password": "Password456",
  "codigo_verificacion": "123456",
  "token_verificacion": "eyJ..."
}
```

**Respuesta esperada (200):**

```json
{
  "mensaje": "Contrasena actualizada correctamente"
}
```

**Códigos de estado:** `200`, `400`, `422`

**Restricciones:** revoca tokens activos y actividad administrativa si aplica.

---

### 7.6.3 Consultar nombre de usuario por correo

| Campo | Valor |
|-------|-------|
| Nombre funcional | Enviar username asociado al correo |
| Método | `POST` |
| Ruta | `/api/v1/auth/recuperacion/usuario/solicitar` |
| `Bearer` | No |

**Body de ejemplo:**

```json
{
  "email": "usuario@example.com"
}
```

**Respuesta esperada (200, genérica):**

```json
{
  "mensaje": "Si el correo corresponde a una cuenta activa, enviaremos el nombre de usuario asociado."
}
```

**Códigos de estado:** `200`, `422`, `429` (demasiados correos distintos desde la misma IP)

**Restricciones:** el username no se devuelve por API; se envía únicamente por correo.
La API aplica una regla central en `core/reglas_seguridad.py` para bloquear
temporalmente una IP cuando intenta consultar muchos correos diferentes en una
ventana corta.

---

### 7.7 Registro de usuario móvil

| Campo | Valor |
|-------|-------|
| Nombre funcional | Crear cuenta `rol=usuario` |
| Método | `POST` |
| Ruta | `/api/v1/auth/registro/usuario` |
| `Bearer` | No |

**Body de ejemplo:**

```json
{
  "username": "usuario_prueba_jmeter",
  "email": "jmeter@example.com",
  "password": "Password123",
  "rol": "usuario",
  "codigo_verificacion": "123456",
  "token_verificacion": "eyJ..."
}
```

**Respuesta esperada (201):** objeto `UsuarioRespuesta` con `id_usuario`, `username`, `email`, `rol`, `activo`.

**Códigos de estado:** `201`, `400`, `409` (username/email duplicado), `422`

**Restricciones:** **carga destructiva** — crea filas en BD; usar usuarios únicos por iteración (`${__threadNum}_${__time()}`) o limitar concurrencia.

---

## 8. App móvil pública

Son endpoints publicos; no requieren `Authorization`.

### 8.1 Listar categorías de sitios

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/sitios/categorias` |
| `Bearer` | No |

**Respuesta esperada (200):**

```json
[
  { "id_categoria": 1, "nombre": "Naturaleza", "activo": true }
]
```

**Códigos de estado:** `200`, `401`

---

### 8.2 Listar subcategorías

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/sitios/subcategorias` |
| `Bearer` | No |

**Parámetros query:**

| Parámetro | Tipo | Obligatorio |
|-----------|------|-------------|
| `id_categoria` | int | **Sí** |

**Ejemplo:** `/api/v1/sitios/subcategorias?id_categoria=1`

**Respuesta esperada (200):** lista de `SubcategoriaSalida` con categoría anidada.

**Códigos de estado:** `200`, `401`, `422`

---

### 8.3 Listar sitios (resumen)

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/sitios/` |
| `Bearer` | No |

**Parámetros query (todos opcionales):**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `id_categoria` | int | Filtrar por categoría |
| `id_subcategoria` | int | Filtrar por subcategoría |
| `nombre` | string | Búsqueda parcial por nombre |

**Respuesta esperada (200):**

```json
[
  {
    "id_sitio": 1,
    "nombre": "Volcan Chimborazo",
    "categoria": "Naturaleza",
    "subcategoria": "Volcanes",
    "descripcion": "...",
    "direccion": "...",
    "img_Url": "/api/v1/imagenes/...",
    "point": { "type": "Point", "coordinates": [-78.8175, -1.4691] }
  }
]
```

**Datos válidos de prueba:** `?nombre=chimborazo` o `?id_categoria=1`

---

### 8.4 Ficha de sitio

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/ficha_sitio/{id_sitio}` |
| `Bearer` | No |

**Parámetros path:** `id_sitio` (int, requerido)

**Respuesta esperada (200):** `SitioDetalleAppSalida` con nombre, categoría, horario_resumen, entrada_resumen, imagenes, servicios.

**Códigos de estado:** `200`, `401`, `404` (`Sitio no encontrado`)

---

### 8.5 Listar rutas turísticas móvil

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/rutas-movil-turismo` |
| `Bearer` | No |

**Respuesta esperada (200):**

```json
{
  "total": 2,
  "rutas": [
    {
      "id_ruta": 1,
      "tipo_ruta": "senderismo",
      "titulo": "Ruta Centro Histórico",
      "color": "#1E88E5",
      "leyenda": "Centro",
      "activo": true,
      "coordenadas": [],
      "puntos": []
    }
  ]
}
```

**Restricciones:** solo rutas activas.

---

### 8.6 Detalle ruta turística móvil

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/rutas-movil-turismo/{id_ruta}` |
| `Bearer` | No |

**Códigos de estado:** `200`, `404`

---

### 8.7 Listar rutas de buses

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/rutas-buses/` |
| `Bearer` | No |

**Parámetros query (opcionales):** `estado`, `linea_bus` (filtro ILIKE)

**Respuesta esperada (200):** lista de `RutaBusSalida` con `geometry` GeoJSON MultiLineString.

---

### 8.8 Leyenda rutas de buses

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/rutas-buses/leyenda` |
| `Bearer` | No |

**Respuesta esperada (200):**

```json
[
  { "linea_bus": "L1", "color": "#1E88E5", "cantidad_rutas": 3 }
]
```

---

### 8.9 Detalle ruta de bus

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/rutas-buses/{id_ruta}` |
| `Bearer` | No |

**Códigos de estado:** `200`, `404` (`Ruta de bus no encontrada`)

---

### 8.10 Noticias vigentes (app móvil)

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/noticias/usuario` |
| `Bearer` | No |

**Respuesta esperada (200):**

```json
{
  "total": 1,
  "noticias": [
    {
      "id_noticia": 1,
      "titulo": "Festival de las Frutas y las Flores 2026",
      "imagen_url": "/api/v1/imagenes/noticias/...",
      "fecha_inicio": "2026-06-01",
      "fecha_fin": "2026-06-30"
    }
  ]
}
```

**Restricciones:** solo noticias con `activa=true`, `fecha_inicio <= hoy`, `fecha_fin` nula o `>= hoy`.

---

### 8.11 Comprobar archivos de sitio

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/comprobar_archivos/{id_sitio}` |
| `Bearer` | No |

**Respuesta esperada (200):**

```json
{ "id_sitio": 1, "tiene_documentos": true }
```

**Códigos de estado:** `200`, `404`

---

### 8.12 Imágenes estáticas

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/imagenes/{path}` |
| `Bearer` | No |

**Ejemplo:** `/api/v1/imagenes/volcan-chimborazo/imagen.jpg`

**Respuesta esperada (200):** binario (image/jpeg, image/png, etc.)

**Códigos de estado:** `200`, `401`, `404`

**Restricciones:** en pruebas de carga, el peso de imágenes impacta ancho de banda; considerar muestreo parcial.

---

## 9. Favoritos (usuario autenticado)

Base: `/api/v1/favoritos`. Todos requieren `Authorization: Bearer`.

### 9.1 Listar favoritos

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/favoritos` |
| `Bearer` | **Sí** |

**Respuesta esperada (200):**

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
      "fecha_agregado": "2026-06-17T10:00:00Z"
    }
  ]
}
```

---

### 9.2 Agregar favorito

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/favoritos/{id_sitio}` |
| `Bearer` | **Sí** |

**Body:** ninguno.

**Respuesta esperada (200):**

```json
{
  "message": "Sitio agregado a favoritos correctamente",
  "id_sitio": 41,
  "es_favorito": true
}
```

**Códigos de estado:** `200`, `400` (`El sitio ya esta en favoritos`), `404` (`Sitio no encontrado`), `401`

**Restricciones:** idempotencia parcial — segundo POST al mismo sitio devuelve 400.

---

### 9.3 Eliminar favorito

| Campo | Valor |
|-------|-------|
| Método | `DELETE` |
| Ruta | `/api/v1/favoritos/{id_sitio}` |
| `Bearer` | **Sí** |

**Respuesta esperada (200):** `message`, `id_sitio`, `es_favorito: false`

---

### 9.4 Verificar estado de favorito

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/favoritos/{id_sitio}/estado` |
| `Bearer` | **Sí** |

**Respuesta esperada (200):**

```json
{ "id_sitio": 41, "es_favorito": true }
```

---

## 10. Historial de conversaciones (usuario autenticado)

Base: `/api/v1/historial`. Requiere `Authorization: Bearer`.

### 10.1 Listar conversaciones

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/historial/conversaciones` |
| `Bearer` | **Sí** |

**Parámetros query:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `tipo` | `general\|sitio\|detalle\|todos` | `todos` | Filtro por tipo |
| `limit` | int (1–200) | `50` | Paginación |
| `offset` | int (≥0) | `0` | Paginación |

**Respuesta esperada (200):**

```json
{
  "items": [
    {
      "id_conversacion": 10,
      "session_id": "uuid-sesion",
      "titulo": "Catedral de Riobamba",
      "tipo": "detalle",
      "total_mensajes": 4,
      "entidad_asociada": {
        "tipo": "sitio",
        "id": 1,
        "nombre": "Catedral de Riobamba"
      }
    }
  ],
  "total": 1
}
```

---

**Nota:** cuando la conversación pertenece a un sitio turístico, `entidad_asociada` se resuelve como `{ tipo: "sitio", id, nombre }` y el `titulo` del resumen prioriza el nombre del sitio.

### 10.2 Obtener mensajes de conversación

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/historial/conversaciones/{id_conversacion}/mensajes` |
| `Bearer` | **Sí** |

**Parámetros query:**

| Parámetro | Tipo | Default |
|-----------|------|---------|
| `tipo` | `general\|detalle\|sitio` | null |
| `limit` | int (1–500) | `200` |
| `offset` | int (≥0) | `0` |

**Respuesta esperada (200):** `ConversacionDetalleRespuesta` con array `mensajes` y `entidad_asociada` cuando corresponda. En mensajes de tipo detalle/sitio, cada item puede llevar `entidad_asociada` con el sitio resuelto.

**Códigos de estado:** `200`, `401`, `404` (`Conversacion no encontrada`)

**Restricciones:** solo conversaciones del `id_usuario` del JWT.

---

## 11. Chatboot — herramientas de exploración

Base: `/api/v1/chatboot/herramientas`. No requiere `Authorization`. Diseñadas para red interna; en JMeter simulan carga del servicio chatboot.

**Campo transversal `ids_consulta`:** array de IDs para encadenar filtros en pipeline. `[]` = universo completo de sitios/rutas activos.

### 11.1 Búsqueda semántica

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/busqueda-semantica-consulta` |

**Body de ejemplo:**

```json
{
  "texto_embeddings": "museo con exposiciones de arte colonial",
  "keywords": ["arte colonial", "colonial"],
  "excluir_terminos": [],
  "ids_consulta": []
}
```

**Respuesta esperada (200):** `ids_sitio[]`, `candidatos[]`, `retroalimentacion` — o `sin_sitios` / `fallo`.

**Restricciones:** `texto_embeddings` obligatorio (1–500 chars); operación costosa (embeddings + BD).

---

### 11.2 Búsqueda por referencia (dirección)

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/busqueda-referencia` |

**Body de ejemplo:**

```json
{
  "direccion_referencia": "jose veloz y morona",
  "ids_consulta": []
}
```

**Respuesta esperada (200):** `ids_sitio` o nombre de parroquia/plataforma.

---

### 11.3 Búsqueda por ubicación

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/busqueda-ubicacion` |

**Body de ejemplo (cercanía a referencia):**

```json
{
  "entidad": "sitio",
  "tipo_busqueda": "cercania",
  "referencia_ubicacion": "mercado la condamine",
  "usar_ubicacion_usuario": false,
  "distancia": null,
  "unidad": "",
  "excluir_zonas": [],
  "ids_consulta": []
}
```

**Body de ejemplo (cercanía a GPS usuario):**

```json
{
  "entidad": "sitio",
  "tipo_busqueda": "cercania",
  "referencia_ubicacion": "",
  "usar_ubicacion_usuario": true,
  "distancia": 400,
  "unidad": "m",
  "ubicacion_usuario": { "lat": -1.6736, "lon": -78.6473 },
  "ids_consulta": []
}
```

---

### 11.4 Búsqueda de contacto

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/contacto-busqueda` |

**Body de ejemplo:**

```json
{
  "contacto_sugerido": "whatsapp",
  "excluir_contactos": [],
  "ids_consulta": []
}
```

---

### 11.5 Consulta de horario

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/horario-consulta` |

**Body de ejemplo (abierto ahora):**

```json
{
  "tipo": "instantaneo",
  "dia_semana": null,
  "hora": null,
  "rango_hora": null,
  "comparador": "",
  "excluir_dias": [],
  "ids_consulta": []
}
```

**Tipos válidos `tipo`:** `instantaneo`, `punto_tiempo`, `bloque_tiempo`, `dias_solamente`, `relacional`

---

### 11.6 Consulta de precio

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/precio-consulta` |

**Body de ejemplo:**

```json
{
  "es_gratuito": true,
  "precio_numero": null,
  "operador": "",
  "etiqueta": "",
  "excluir_etiquetas": [],
  "ids_consulta": []
}
```

**Etiquetas:** `economico`, `moderado`, `alto`, etc.

---

### 11.7 Consulta de tarifa de acceso

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/tarifa-acceso-consulta` |

**Body de ejemplo:**

```json
{
  "entrada_gratuita": true,
  "precio_numero": null,
  "operador": "",
  "etiqueta": "",
  "condicion": "",
  "excluir_condiciones": [],
  "ids_consulta": []
}
```

---

### 11.8 Atributos booleanos

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/atributos-booleanos-consulta` |

**Body de ejemplo:**

```json
{
  "tiene_wifi": true,
  "permite_mascotas": null,
  "accesibilidad": null,
  "parqueadero": null,
  "es_gratuito": null,
  "excluir": [],
  "ids_consulta": []
}
```

**Restricciones:** al menos un booleano distinto de `null` o un término en `excluir`.

---

### 11.9 Consulta GIS (distancia geográfica)

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/gis-consulta` |

**Body de ejemplo:**

```json
{
  "entidad": "sitio",
  "usar_ubicacion_usuario": true,
  "distancia": null,
  "unidad": "",
  "punto_referencia": "",
  "excluir_zonas": [],
  "ubicacion_usuario": { "lat": -1.6736, "lon": -78.6473 },
  "ids_consulta": []
}
```

**`entidad`:** `sitio` o `ruta`. Herramienta típicamente al final del pipeline.

---

### 11.10 Consulta de rutas turísticas

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/ruta-consulta` |

**Body de ejemplo:**

```json
{
  "tipo_ruta": "senderismo",
  "excluir_tipos": [],
  "ids_consulta": []
}
```

---

### 11.11 Resolver sitio por nombre (pregunta directa)

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/pregunta-directa` |

**Body de ejemplo:**

```json
{
  "nombre_entidad": "Museo de la Ciudad",
  "ids_consulta": []
}
```

**Respuesta esperada (200):** `ids_sitio`, `id_sitio`, `nombre`, `score` — o `sin_sitios` / `fallo`.

---

### 11.12 Historial de exploración

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/historial-exploracion` |

**Body de ejemplo:**

```json
{
  "id_usuario": 1,
  "sesion_id": "uuid-sesion",
  "client_message_id": "uuid-mensaje",
  "texto_usuario": "Busco restaurantes con wifi",
  "respuesta_json": {
    "pregunta_chatboot": "exploracion",
    "exploracion": { "mensajes_app": [] }
  },
  "categorias": ["Alimentos y Bebidas"],
  "subcategorias": ["Restaurante"]
}
```

**Respuesta esperada (200):**

```json
{
  "id_conversacion": 10,
  "client_message_id": "uuid-mensaje",
  "usuario_guardado": true,
  "respuesta_guardada": true,
  "mensaje": "Historial de exploración procesado."
}
```

**Restricciones:** **escritura en BD**; idempotente por `id_conversacion + client_message_id + rol`. Si `id_usuario` es null, no persiste usuario. Usar `client_message_id` único por iteración.

---

### 11.13 Historial pregunta directa

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/herramientas/historial-pregunta-directa` |

**Restricciones:** persiste en `conversacion.mensaje_detalle`; operación de escritura. Ver contrato completo en [`chatboot_arquitectura_api.md`](../apis/docs/chatboot_arquitectura_api.md).

---

### 11.14 Opciones fallback exploración

| Campo | Valor |
|-------|-------|
| Método | `GET` |
| Ruta | `/api/v1/chatboot/fallback/opciones-exploracion` |
| `Bearer` | No |

**Respuesta esperada (200):**

```json
{
  "opciones": [
    { "categoria": "Gastronomía", "subcategorias": ["Restaurante", "Cafetería"] }
  ]
}
```

---

## 12. Chatboot — pregunta directa (datos de sitio)

Base: `/api/v1/chatboot/pregunta-directa`. No requiere `Authorization`.

### 12.1 Ficha compacta de sitio

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/pregunta-directa/ficha-sitio` |

**Body:** `{ "id_sitio": 1 }`

**Respuesta esperada (200):** horario, contactos, precio, atributos compactos — o `{ "fallo": "..." }`.

---

### 12.2 Multimedia de sitio

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/pregunta-directa/multimedia` |

**Body:** `{ "id_sitio": 1 }`

**Respuesta esperada (200):** `{ "id_sitio": 1, "imagenes": [{ "url": "...", "es_principal": true }] }`

---

### 12.3 Chunks de documento (RAG)

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/pregunta-directa/chunks-documento` |

**Body de ejemplo:**

```json
{
  "id_sitio": 1,
  "mensaje_chunk": "¿Cuál es el horario de atención?",
  "keywords": ["horario"]
}
```

---

### 12.4 Cómo llegar

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/pregunta-directa/como-llegar` |

**Body:** `{ "id_sitio": 1 }`

---

### 12.5 Ruta a documento

| Campo | Valor |
|-------|-------|
| Método | `POST` |
| Ruta | `/api/v1/chatboot/pregunta-directa/ruta-documento` |

**Body:** `{ "id_sitio": 1 }`

---

## 13. Escenarios JMeter sugeridos

### Escenario A — Carga pública (invitado)

**Thread Group:** 50–200 usuarios, ramp-up 60 s, loop 10.

Secuencia:

1. `GET /` (smoke)
2. `GET /api/v1/sitios/categorias`
3. `GET /api/v1/sitios/subcategorias?id_categoria=1`
4. `GET /api/v1/sitios/`
5. `GET /api/v1/ficha_sitio/${ID_SITIO}` (ID extraído del paso 4)
6. `GET /api/v1/rutas-movil-turismo`
7. `GET /api/v1/rutas-buses/leyenda`
8. `GET /api/v1/noticias/usuario`

Sin `Authorization`.

---

### Escenario B — Carga usuario autenticado

**Setup Thread Group (1 usuario):** login → extraer `ACCESS_TOKEN`.

**Thread Group principal:**

1. `GET /api/v1/auth/me`
2. `GET /api/v1/favoritos`
3. `GET /api/v1/favoritos/${ID_SITIO}/estado`
4. `POST /api/v1/favoritos/${ID_SITIO}` (opcional, escritura)
5. `GET /api/v1/historial/conversaciones?tipo=todos&limit=20`
6. `GET /api/v1/historial/conversaciones/${ID_CONVERSACION}/mensajes`

**Teardown:** `POST /api/v1/auth/logout`

---

### Escenario C — Carga chatboot (pipeline)

Simula el ejecutor del chatboot encadenando herramientas:

1. `POST .../busqueda-semantica-consulta` → JSON Extractor `$.ids_sitio` → `IDS_CONSULTA`
2. `POST .../horario-consulta` con `"ids_consulta": ${IDS_CONSULTA}`
3. `POST .../gis-consulta` con `"ids_consulta": ${IDS_CONSULTA}`

**Notas:** semántica y GIS son los más costosos; ajustar concurrencia según CPU/BD. Separar thread group de escritura (`historial-exploracion`) para no mezclar lectura/escritura.

---

## 14. Códigos de estado y errores comunes

| HTTP | Causa típica | `detail` ejemplo |
|------|--------------|------------------|
| `401` | JWT ausente, expirado o revocado | `No se pudieron validar las credenciales` |
| `401` | Admin inactivo > 30 min | `Sesion expirada por inactividad` |
| `403` | Sin permisos (no aplica en alcance móvil) | `No tiene permiso para ...` |
| `404` | Recurso inexistente | `Sitio no encontrado`, `Conversacion no encontrada` |
| `409` | Conflicto | Username/email duplicado en registro |
| `422` | Validación Pydantic | Array `detail` con `loc`, `msg`, `type` |
| `500` | Error interno | `Internal Server Error` |

**Validación 422 (ejemplo):**

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["query", "id_categoria"],
      "msg": "Field required"
    }
  ]
}
```

---

## 15. Checklist pre-ejecución

- [ ] Usuario de prueba existe y está activo (escenario B)
- [ ] `ID_SITIO` / `ID_RUTA` válidos en la BD del entorno
- [ ] Cookie Manager habilitado si se prueba refresh
- [ ] Endpoints de escritura (favoritos POST, historial-exploracion, registro) con concurrencia controlada
- [ ] Entorno de staging aislado de producción

---

## 16. Referencias

| Documento | Contenido |
|-----------|-----------|
| [`apis/docs/contratos_apis.md`](../apis/docs/contratos_apis.md) | Contrato completo incluyendo panel admin |
| [`apis/docs/autentificacion.md`](../apis/docs/autentificacion.md) | Modelo de capas, TTL, refresh, 2FA |
| [`apis/docs/chatboot_arquitectura_api.md`](../apis/docs/chatboot_arquitectura_api.md) | Detalle H1–H13, pipelines, historial |
| [`apis/tests/probar_apis_chatboot.py`](../apis/tests/probar_apis_chatboot.py) | Casos de prueba interactivos por herramienta |
| [`apis/docs/README.md`](../apis/docs/README.md) | OpenAPI en `/docs` y `/redoc` |
