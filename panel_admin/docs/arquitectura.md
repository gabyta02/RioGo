# Arquitectura del Panel Admin

## Stack

- React 18 con Vite.
- Tailwind CSS para estilos.
- Axios para llamadas HTTP.
- Recharts para graficos del dashboard.
- MapLibre GL JS para edición controlada de geometría de rutas.
- React Quill + Turndown para contenido Markdown de chatbots.
- Build publicado bajo `/admin/` y reutilizado públicamente bajo `/account/`.
- API consumida desde `/api/v1`.

## Estructura principal

```txt
src/
  App.jsx
  main.jsx
  index.css

    core/
    api/
      client.js
      errors.js

    theme.js

    typography.js

    auth/
      AccountRecoveryPage.jsx
      AdminSessionPage.jsx
      LoginPage.jsx
      VerificationCodePage.jsx
      authService.js
      authStorage.js

    layouts/
      AdminLayout.jsx
      AuthLayout.jsx

    ui/
      ActionTypeBadge.jsx
      AdminControls.jsx
      AdminModal.jsx
      ConfirmDialog.jsx
      EntityStatusBadge.jsx
      ExpandToggleButton.jsx
      IconButton.jsx
      JsonDiffView.jsx
      jsonDiff.js
      Panel.jsx
      PanelHeader.jsx
      PanelToolbar.jsx
      Pagination.jsx
      PasswordInput.jsx
      PrimaryButton.jsx
      RepositoryCard.jsx
      SearchBox.jsx
      StatCard.jsx
      TextInput.jsx
      UserAvatar.jsx
      icons.jsx

  modules/
    action_log/
      ActionLogPage.jsx
      actionLogService.js
    admin_accounts/
      AdminAccountsPage.jsx
      adminAccountsService.js
    analytics/
      QueriesAnalysisPage.jsx
      queriesAnalysisService.js
    attractions/
      AttractionsPage.jsx
      attractionsService.js
    categories/
      CategoriesPage.jsx
      categoriesService.js
    chatbot_content/
      ChatbotContentPage.jsx
      chatbotContentService.js
    dashboard/
      DashboardPage.jsx
      dashboardService.js
    routes/
      RouteGeometryPage.jsx
      RoutesPage.jsx
      routesService.js
```

## Responsabilidades

`main.jsx` monta React sobre el `root` del HTML.

`App.jsx` decide la pantalla activa:

- Recuperación pública de cuenta en `/account/`.
- Login.
- Verificacion de codigo para cuentas con 2FA.
- Sesion administrativa iniciada.

`core/api/client.js` centraliza Axios e inyecta el JWT desde `localStorage`.

`core/api/errors.js` expone `getApiErrorMessage()` para normalizar errores FastAPI
y evitar pantallas en blanco cuando `detail` llega como arreglo u objeto.

`core/auth` contiene pantallas, almacenamiento de sesion, servicios de login y
recuperación pública de cuenta.

`core/layouts` contiene estructuras reutilizables de pagina.

`core/ui` contiene piezas visuales reutilizables.

`core/theme.js` centraliza la paleta de colores del panel. `tailwind.config.js`
importa esos tokens para generar las clases `app-*`.

`core/typography.js` centraliza tamaños y pesos de texto (`text.entityTitle`,
`text.entityMeta`, `text.sectionLabel`, etc.) y espaciado de tarjetas (`layout`).

`PanelToolbar` define la barra superior estándar: búsqueda compacta a la
izquierda (`sm:max-w-xs`), filtros y acciones alineados a la derecha, y una
franja opcional de metadatos debajo.

`modules` contiene las secciones internas del panel. Cada modulo mantiene su
servicio HTTP junto a la vista.

## Autorizacion y menu lateral

El panel admite dos roles de acceso:

- `super-admin`: ve todos los modulos activos y gestiona cuentas administrativas.
- `admin`: ve solo los modulos incluidos en `session.permisos`.

`authStorage.js` define:

- `esSesionPanel()`
- `puedeAccederVista(session, viewId)`
- `primeraVistaPermitida(session)`

`AdminLayout.jsx` filtra el menu con esas funciones.

La tarjeta de usuario del sidebar abre `ProfileSettingsModal` (pestañas Perfil y
Seguridad). Cualquier usuario del panel puede gestionar su propia cuenta: foto,
username, correo, contraseña y 2FA. Rol, cargo y permisos son solo lectura.

Componentes reutilizables de perfil:

| Componente | Archivo |
|------------|---------|
| Tarjeta sidebar | `core/ui/ProfileSidebarCard.jsx` |
| Avatar con foto | `core/ui/ProfileAvatar.jsx` |
| Pestañas | `core/ui/TabGroup.jsx` |
| Verificación correo | `core/ui/VerificationCodeFlow.jsx` |
| Campo solo lectura | `core/ui/ReadOnlyField.jsx` |

Módulo: `modules/profile/` (`ProfileSettingsModal`, `ProfileTab`, `SecurityTab`, `profileService.js`).

Opciones activas actuales:

| Vista | id | Permiso API |
|-------|----|-------------|
| Dashboard | `dashboard` | `dashboard` |
| Analisis de consultas | `analytics` | `analytics` |
| Atractivos turisticos | `attractions` | `attractions` |
| Categorias y subcategorias | `categories` | `categories` |
| Rutas turisticas | `routes` | `routes` |
| Noticias turisticas | `noticias` | `noticias` |
| Contenido para chatbots | `chatbot_content` | `chatbot_content` |
| Registro de acciones | `action_log` | `action_log` |
| Cuentas administrativas | `admin_accounts` | solo `super-admin` |

`AdminSessionPage.jsx` redirige automaticamente si el usuario intenta abrir una
vista sin permiso.

El bloque inferior del menu muestra `nombre_completo`, cargo y foto de perfil si existe.
Al hacer clic se abre el modal de configuración de cuenta.

## Flujo de autenticacion

1. El usuario ingresa `username` y `password`.
2. El panel llama a `POST /api/v1/auth/login`.
3. Si la cuenta es `admin` o `super-admin`, la API devuelve `token`, `rol` y
   `permisos[]`.
4. Si la cuenta tiene autentificacion doble (`super-admin`), la API pide codigo.
5. El panel solicita el codigo con `POST /api/v1/auth/correo/verificacion`
   usando `proposito: "login_2fa"`.
6. El usuario escribe el codigo en `VerificationCodePage`.
7. Cuando el codigo llega a 6 digitos, el panel intenta login automaticamente.
8. Si el rol no es de panel, se rechaza la sesion.
9. Al cerrar sesion, el panel llama a `POST /api/v1/auth/logout`, la API revoca
   la fila activa de `conversacion.sesion_usuario`, limpia la cookie refresh y
   luego el panel borra `localStorage`.

## Recuperacion publica de cuenta

La ruta `/account/` es una vista pública servida por el mismo bundle del panel.
No requiere sesión y es neutral para administradores y usuarios móviles.
La app móvil debe abrir `https://<dominio-publico>/account/` para que el usuario
pueda cambiar contraseña o consultar su usuario sin una pantalla nativa separada.

Modos disponibles:

| Modo | API |
|------|-----|
| Cambiar contraseña | `POST /api/v1/auth/recuperacion/password/solicitar` y `POST /api/v1/auth/recuperacion/password/confirmar` |
| Consultar usuario | `POST /api/v1/auth/recuperacion/usuario/solicitar` |

Reglas de UX y seguridad:

- En cambiar contraseña, primero se capturan correo, nueva contraseña y
  confirmación; después se solicita el código y se valida en una pantalla
  separada al completar 6 dígitos, igual que el flujo de verificación del login.
- No redirige automáticamente a `/admin/` al terminar.
- No muestra el nombre de usuario en pantalla; el backend lo envía por correo.
- Los mensajes son genéricos para no confirmar si un email existe.
- La consulta de usuario puede recibir `429` si una misma IP intenta muchos
  correos distintos en una ventana corta.
- La vista se selecciona en `App.jsx` con `window.location.pathname.startsWith("/account")`.

Despliegue:

- `ngix/nginx.conf` publica `/account/` hacia el servicio `panel-admin`.
- `panel_admin/nginx.conf` hace fallback SPA para `/account/` usando el mismo
  `index.html` del bundle construido en `/admin`.

## Sesion

La sesion se guarda en `localStorage` con la clave:

```txt
riobambatour_admin_session
```

Contenido relevante:

- `token`
- `rol`
- `permisos`
- `usuario` con `nombre_completo`, `cargo_nombre`, `email`, etc.

`core/auth/SessionManager.js` mantiene la sesion activa en dos capas:

- Actualiza actividad local ante eventos visibles del usuario (`click`,
  `keydown`, `mousemove`, `scroll`, `touchstart`) para controlar el aviso de
  inactividad en UI.
- Renueva explicitamente la sesion administrativa de Redis con
  `POST /auth/admin-session/refresh` y `X-Admin-Session-Id` cuando hubo actividad
  real dentro de la ventana de 30 minutos.

El refresh de access token no debe considerarse actividad de usuario. El panel lo
programa antes de la expiracion real del access token (`expires_in`) y lo mantiene
separado de la ventana de inactividad administrativa.

## Dashboard

`modules/dashboard/DashboardPage.jsx` consume `/api/v1/admin/dashboard` para
construir indicadores, series, distribuciones y rankings con `recharts`.

## Analisis de consultas

`modules/analytics/QueriesAnalysisPage.jsx` consume el endpoint semantico del
dashboard para agrupar preguntas similares usando embeddings.

Estandar visual actual:

- Al abrir la pantalla no se consulta automaticamente la API semantica.
- Primero se muestran los filtros de periodo (`Hoy`, `Semana`, `Mes`, `Año`,
  `Todo`, `Personalizado`) y un estado neutral.
- La llamada a `/api/v1/admin/dashboard/semantica` ocurre solo al presionar
  `Aplicar filtros`.
- `Limpiar` vuelve al estado inicial sin resultados y sin disparar una busqueda.
- Los filtros secundarios (`Canal`, `Categoria`, `Subcategoria`) aparecen tras
  recibir resultados.
- Solo se muestran grupos semanticos con al menos 20 consultas relacionadas.
- Cada fila muestra una pregunta principal y se despliega con `ExpandToggleButton`
  ubicado al lado derecho.
- El despliegue lista las preguntas relacionadas por variante textual y muestra
  cuantas consultas corresponden a cada una.
- Solo puede haber un grupo desplegado a la vez.
- Las cargas largas usan `core/ui/ProgressStatusSequence.jsx`, que muestra cinco
  estados secuenciales de avance, uno por segundo, sin repetir la secuencia y
  quedandose en el ultimo estado hasta recibir la respuesta.

## Atractivos turisticos

`modules/attractions/AttractionsPage.jsx` implementa tabla, filtros y modal con
pestanas:

- General
- Clasificacion
- Ubicacion
- Horarios
- Servicios
- Contacto
- Imagenes
- Precios

En **Horarios** el formulario permite:

- Abierto 24 horas.
- Rango horario por defecto mas dias de atencion.
- Horario personalizado por cada dia seleccionado, con opcion "Cerrado"
  para marcar dias inactivos.
- Comentario opcional de hasta 200 caracteres (por ejemplo, "Solo con
  reservacion previa"), persistido en `turismo.horario.comentario`.

En **Precios** el formulario aplica reglas de exclusividad:

- Sitio gratuito: no se envia rango de precio ni tarifa de acceso.
- Sitio pagado: exactamente uno de los dos, rango de precio (min/max mas
  etiqueta) o tarifa de acceso (mas condicion opcional). Si se llenan
  ambos, el frontend y el backend rechazan el guardado.

Las eliminaciones y cambios de estado usan `ConfirmDialog`.

## Categorias y subcategorias

`modules/categories/CategoriesPage.jsx` implementa CRUD visual con modales
reutilizables, `PanelToolbar`, busqueda por categoria o subcategoria, tarjetas
colapsables y cambios de estado activo/inactivo. Usa `ExpandToggleButton` para
desplegar subcategorias sin abrir ninguna por defecto al entrar.

## Rutas turisticas

`modules/routes/RoutesPage.jsx` implementa listado y modal base de ruta.

`modules/routes/RouteGeometryPage.jsx` administra una única polilínea continua
sobre mapa con MapLibre y Turf.js. El editor mantiene un estado normalizado en
frontend con:

- `vertices`: lista ordenada de coordenadas `{ id, latitud, longitud }`.
- `puntos`: puntos de control `{ id, vertexId|null, tipo, id_sitio, ... }`.

Los IDs de vértices existen solo durante la sesión del editor para mantener
sincronizados marcadores, línea y panel lateral. Al guardar, no se persisten como
registros separados: se serializan como coordenadas ordenadas en `linea`, que el
backend almacena en `gis.rutas_turistica.geom_linea` como `LINESTRING`.

Flujos soportados:

- `Crear punto`: crea un marcador suelto que puede conectarse después.
- `Trazar puntos`: cada clic crea un punto conectado al final de la ruta.
- `Editar vértices`: permite mover vértices intermedios existentes, crear un
  vértice con clic sobre la línea y eliminar un vértice intermedio con clic
  derecho cerca del vértice.

Los sitios son paradas intermedias ancladas a la ubicación oficial del sitio; el
origen y el destino son puntos libres conectados al primer y último vértice. El
guardado rechaza puntos sueltos y conserva una sola ruta continua, sin
bifurcaciones.

El editor mantiene historial local de geometría para `Ctrl+Z`/`Cmd+Z` y el boton
`Deshacer`. Si hay cambios sin guardar, el botón de volver abre `ConfirmDialog`
antes de abandonar la pantalla. El cierre/recarga del navegador usa el aviso
nativo permitido por el browser.

## Contenido para chatbots

`modules/chatbot_content/ChatbotContentPage.jsx` administra repositorios y
documentos Markdown con secciones editables mediante React Quill. Las tarjetas
de repositorio usan `ExpandToggleButton` y `RepositoryCard`.

El editor de contenido usa el historial nativo de Quill para `Ctrl+Z`/`Cmd+Z`.
Mientras el Markdown actual difiera del último contenido cargado o guardado,
`Cancelar` y el botón de volver abren `ConfirmDialog` para evitar perder cambios.
El cierre/recarga del navegador usa el aviso nativo permitido por el browser.

Para cuentas con cargo Dueño o permisos con alcance por sitio, el repositorio del
sitio se crea automáticamente al asignar el sitio y también se asegura al listar
contenido. El dueño no puede crear, renombrar ni eliminar el repositorio; solo
puede crear, editar, eliminar documentos y editar el contenido Markdown dentro de
sus sitios asignados.

## Cuentas administrativas

`modules/admin_accounts/AdminAccountsPage.jsx` implementa:

- Tabla con busqueda, filtros por cargo/estado y paginacion.
- Modal de creacion/edicion con toggles de permisos por modulo.
- Inactivacion y eliminacion con `ConfirmDialog`.

Solo visible para `super-admin`.

Al crear una cuenta, la API genera una contrasena temporal y la envia al correo
indicado. El panel no muestra la contrasena en pantalla.

## Registro de acciones

`modules/action_log/ActionLogPage.jsx` consume `/api/v1/admin/registro-acciones`
para listar acciones administrativas con filtros, paginacion y detalle.

Columnas visibles:

- Administrador (avatar con iniciales).
- Accion (badge por tipo).
- Modulo.
- Fecha y hora.
- Direccion (IP del administrador).
- Detalle (modal con comparacion JSON).

Componentes reutilizables usados:

- `UserAvatar` para la columna de administrador.
- `ActionTypeBadge` para tipos de accion.
- `JsonDiffView` para comparar `datos_anteriores` y `datos_nuevos` en dos
  columnas con resaltado tipo GitHub.
- `Pagination` con numeros de pagina visibles.

## Servicios HTTP

- `dashboardService.js`
- `queriesAnalysisService.js`
- `attractionsService.js`
- `categoriesService.js`
- `routesService.js`
- `chatbotContentService.js`
- `actionLogService.js`
- `adminAccountsService.js`
- `authService.js`

## Manejo de errores

Todos los modulos deben usar `getApiErrorMessage()` desde `core/api/errors.js`
para mostrar mensajes legibles cuando FastAPI responde `422`, `403`, `409` o
`502`.

## Colores Tailwind

Los colores estan definidos en `tailwind.config.js` dentro de `theme.extend.colors.app`.

```txt
app-primario: #0D5A38
app-primario-claro: #EAF4EF
app-fondo: #F9FAFB
app-acento: #FF7A00
app-tarjeta: #FFFFFF
app-error: #EF4444
app-exito: #10B981
app-texto-primario: #1E293B
app-texto-secundario: #64748B
app-borde: #E2E8F0
app-notificacion-fondo: #F1E9D8
```

## Convenciones

- Las llamadas a la API deben vivir en `authService.js` o en el servicio del
  modulo correspondiente.
- Componentes visuales genericos van en `core/ui`.
- Formularios y modales deben reutilizar `AdminControls.jsx`, `AdminModal.jsx`
  y `ConfirmDialog.jsx`.
- Pantallas completas de autenticacion van en `core/auth`.
- Las pantallas del panel deben vivir dentro de `modules/{dominio}`.
- `App.jsx` debe mantenerse como orquestador, no como contenedor de logica
  visual extensa.
- Los errores HTTP deben normalizarse con `getApiErrorMessage()`.
