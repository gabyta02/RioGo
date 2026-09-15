# Chatboot

Este documento registra la infraestructura actual del `chatboot`, el contrato para consumir los canales WebSocket desde la app móvil y las reglas de pintado de globos, streams, cards, opciones e IDs asociados.

## Infraestructura Actual

El punto central de procesamiento es `application/orquestador.py`. La capa WebSocket pública recibe el mensaje plano, lo envuelve internamente con `pregunta_chatboot` según la ruta y lo valida con Pydantic antes de pasarlo al flujo compartido.

Flujo general:

1. Recepción del mensaje plano en `/ws/exploracion` o `/ws/pregunta_directa`.
2. Construcción del paquete interno con `pregunta_chatboot` y `mensaje`.
3. Validación del paquete interno.
4. `shared_flow`: limpieza, detección de prompt injection e inyección de palabras turísticas coloquiales.
5. Si el mensaje queda bloqueado por `shared_flow`, se devuelve `clasificacion_final` con `mensaje_app` y no se ejecuta el canal.
6. Si el canal es `exploracion`, se ejecuta el flujo de exploración.
7. Si el canal es `pregunta_directa`, se ejecuta el flujo del chatbot específico del sitio.
8. Si llega `id_usuario`, se guarda historial mediante las APIs internas.

### Flujo Compartido

El flujo compartido vive en `application/shared/flow.py` y usa `StateGraph` de LangGraph:

```text
START
  -> limpieza_texto
  -> promp_inyection
  -> inyectar_palabra
  -> inyectar_fecha
  -> finalizacion
  -> END
```

Reglas actuales de limpieza, configuradas en `infrastructure/config/settings.json`:

| Parámetro | Valor | Uso |
|---|---:|---|
| `max_palabras_mensaje` | `80` | Bloquea mensajes demasiado largos. |
| `max_repeticion_caracter` | `2` | Reduce repeticiones como `holaaaa` a máximo 2 caracteres repetidos. |
| `max_saltos_linea_consecutivos` | `2` | Normaliza saltos de línea excesivos. |
| `min_digitos_sin_contexto` | `5` | Bloquea números largos sin contexto. |

La detección de prompt injection bloquea cuando el score alcanza `umbral_bloqueo: 0.8`. La inyección de palabras usa RapidFuzz para mapear términos coloquiales con significado turístico.

El nodo `inyectar_fecha` agrega `contexto_temporal` al mensaje compartido con zona horaria, fecha actual, día actual, hora actual, los próximos días y la próxima ocurrencia de lunes a domingo. Por defecto usa `America/Guayaquil`; puede sobrescribirse con `CHATBOOT_TIMEZONE`.

### Flujo De Exploración

El flujo de exploración vive en `application/nodes/chatboot_exploracion/flow.py`. Si LangGraph está disponible usa `StateGraph`; si no, cae a un ejecutor secuencial equivalente.

```text
START
  -> cargar_memoria
  -> crear_plan
  -> ejecutar_plan
  -> guardar_memoria
  -> END
```

`crear_plan` llama al LLM de la ruta `exploracion_plan`, exige JSON y luego sanitiza el plan. `ejecutar_plan` corre consultas en paralelo y herramientas dentro de cada consulta en orden. `guardar_memoria` actualiza memoria temporal; el historial persistente se guarda desde el orquestador.

### Flujo De Pregunta Directa

El canal `/ws/pregunta_directa` usa el flujo específico del sitio:

```text
cargar_memoria_pregunta
  -> crear_plan_pregunta_directa
  -> ejecutar_plan_pregunta
  -> guardar_memoria_pregunta
```

Este canal requiere `id_sitio` y `nombre_sitio`. El alcance de la respuesta queda fijado a ese sitio.

### LLM Y Configuración

La configuración actual está en `infrastructure/config/settings.json`.

| Ruta LLM | Uso | JSON |
|---|---|---|
| `exploracion_plan` | Planificador de exploración. | Sí |
| `exploracion` | Redactor de resultados de exploración. | No |
| `exploracion_fallback` | Redactor de fallback. | Sí |
| `sitio` | Chatbot específico de un sitio. | No |

El proveedor configurado por defecto es `deepseek`, modelo `deepseek-v4-flash`, usando SDK compatible con OpenAI.

## Rutas WebSocket

| Canal | Ruta | Uso |
|---|---|---|
| Exploración | `/ws/exploracion` | Búsqueda turística conversacional, recomendaciones, filtros, cercanía y rutas. |
| Pregunta directa | `/ws/pregunta_directa` | Canal del chatbot específico de un sitio; recibe `id_sitio` y `nombre_sitio`. |

Al abrir el socket, el backend responde:

```json
{
  "tipo": "conexion",
  "estado": "conectado",
  "canal": "exploracion",
  "pregunta_chatboot": "exploracion"
}
```

## Envío Desde La App

La app móvil envía JSON plano. La ruta WebSocket define el canal; la app no necesita enviar `pregunta_chatboot`.

```json
{
  "mensaje_usuario": "Quiero museos abiertos cerca de mí",
  "id_usuario": 1,
  "client_message_id": "uuid-generado-en-app",
  "sesion_Id": null,
  "ubicacion_usuario": {
    "lat": -1.6736,
    "lng": -78.6473
  }
}
```

Reglas:

- `id_usuario` identifica al usuario autenticado y permite persistir el historial de exploración.
- `client_message_id` lo genera la app por cada mensaje.
- `sesion_Id` puede ir `null`; el backend genera una sesión y la devuelve como `sesion_id`.
- En turnos siguientes, la app debe reenviar el `sesion_id` recibido para conservar memoria.
- `ubicacion_usuario` debe enviarse siempre que la app la tenga disponible.
- El cliente puede enviar `lng`; el ejecutor normaliza a `lon` cuando una herramienta GIS lo necesita.

Para `/ws/pregunta_directa`, además se envía:

```json
{
  "mensaje_usuario": "¿Cuál es el horario?",
  "id_usuario": 1,
  "client_message_id": "uuid-generado-en-app",
  "sesion_Id": "uuid-sesion",
  "ubicacion_usuario": {
    "lat": -1.6736,
    "lng": -78.6473
  },
  "id_sitio": 68,
  "nombre_sitio": "Mercado de la Merced"
}
```

Ambos campos son obligatorios para pregunta directa: `id_sitio` identifica la ficha del sitio y `nombre_sitio` fija el alcance del chatbot específico.

Internamente, la capa WebSocket transforma el mensaje plano a:

```json
{
  "pregunta_chatboot": "exploracion",
  "mensaje": {
    "mensaje_usuario": "Quiero museos abiertos cerca de mí",
    "id_usuario": 1,
    "client_message_id": "uuid-generado-en-app",
    "sesion_id": "uuid-sesion",
    "ubicacion_usuario": {
      "lat": -1.6736,
      "lng": -78.6473
    }
  }
}
```

Ese paquete interno es el que consume `application/orquestador.py`.

## Eventos Que Recibe La App

### 1. Stream De Progreso

Mientras el backend clasifica, ejecuta herramientas y redacta, el WebSocket puede enviar eventos de progreso:

```json
{
  "tipo": "stream",
  "canal": "exploracion",
  "client_message_id": "uuid-generado-en-app",
  "payload": {
    "tipo": "stream",
    "mensaje": {
      "origen": "pensamiento_fake",
      "fase": "analizando_intencion",
      "texto": "Estoy analizando qué tipo de búsqueda turística necesitas.",
      "indice": 2,
      "total": 6
    }
  }
}
```

La app debe pintarlo como un globo temporal de progreso, visualmente distinto del mensaje final. No debe tratarse como respuesta definitiva.

Regla de UI actual:

- Mantener un solo contenedor de stream por mensaje del usuario.
- Cada evento `stream` reemplaza el texto/fase del contenedor anterior.
- Cuando llega `clasificacion_final` o `error_validacion`, eliminar ese contenedor temporal.

### 2. Respuesta Final

Cuando termina el procesamiento, llega:

```json
{
  "tipo": "clasificacion_final",
  "canal": "exploracion",
  "payload": {
    "pregunta_chatboot": "exploracion",
    "mensaje": {
      "mensaje_usuario": "Quiero museos abiertos cerca de mí",
      "texto_limpio": "quiero museos abiertos cerca de mí",
      "riesgo_prompt_inyection": {},
      "palabras_inyectadas": [],
      "contexto_temporal": {
        "zona_horaria": "America/Guayaquil",
        "fecha_actual": "2026-07-13",
        "dia_actual": "lunes",
        "dia_actual_etiqueta": "lunes",
        "hora_actual": "08:30",
        "dias": [],
        "proxima_ocurrencia": {
          "lunes": "2026-07-13",
          "martes": "2026-07-14"
        }
      }
    },
    "client_message_id": "uuid-generado-en-app",
    "sesion_id": "uuid-sesion",
    "ubicacion_usuario": {
      "lat": -1.6736,
      "lng": -78.6473
    },
    "mensaje_app": {
      "tipo": "globo",
      "mensaje": {
        "texto": "Encontré 2 opciones que pueden servirte...",
        "origen": "redactor_exploracion"
      }
    },
    "exploracion": {
      "plan_valido": true,
      "plan": {},
      "errores_formato": [],
      "estados_herramientas": [],
      "ids_asociados": [12, 45],
      "mensajes_app": []
    }
  }
}
```

La app debe preferir `payload.exploracion.mensajes_app` si existe y tiene elementos. Si no existe, debe pintar `payload.mensaje_app`.

## Historial De Exploración

Al terminar una respuesta de exploración, el chatboot guarda el turno en la API interna `POST /api/v1/chatboot/herramientas/historial-exploracion`.

Por cada `client_message_id` se crean dos registros en `conversacion.mensaje_explorador`:

| Rol | Contenido | Embedding |
|---|---|---|
| `usuario` | Texto limpio de la pregunta del usuario. | Sí, vector de 1024 dimensiones. |
| `conversacion_general` | JSON final completo que recibe la app móvil para pintar globos, cards, acciones e IDs. | `NULL` |

Ambos registros comparten `client_mensaje_id`, `categoria` y `subcategoria`. La app puede reconstruir el historial agrupando por ese identificador y pintando el JSON guardado en el registro `conversacion_general`.

Si `id_usuario` no llega en el WebSocket, la conversación se responde normalmente, pero no se persiste en PostgreSQL.

### 3. Error De Validación

```json
{
  "tipo": "error_validacion",
  "canal": "exploracion",
  "mensaje": "El mensaje no pudo procesarse con la estructura requerida.",
  "detalle": "..."
}
```

La app debe pintarlo como globo de error no persistente.

## Tipos De `mensaje_app`

### Globo

```json
{
  "tipo": "globo",
  "mensaje": {
    "texto": "Encontré algunas opciones para ti.",
    "origen": "redactor_exploracion"
  }
}
```

Uso:

- Respuesta final redactada.
- Fallback.
- Conversacional.
- Errores suaves.

Pintado móvil recomendado:

- Burbuja del asistente.
- Mostrar `texto`.
- `origen` puede usarse solo para debug; en producción no es necesario mostrarlo.

### Stream

```json
{
  "tipo": "stream",
  "mensaje": {
    "origen": "pensamiento_fake",
    "fase": "consultando_catalogo",
    "texto": "Estoy consultando la información turística disponible.",
    "indice": 4,
    "total": 6
  }
}
```

Uso:

- Progreso visual.
- No representa pensamiento interno real del LLM.
- Es un guion controlado para informar estado al usuario.

Pintado móvil recomendado:

- Burbuja pequeña, tenue o con indicador de actividad.
- Reemplazar el contenido con el último stream recibido para evitar saturar el chat.
- Ocultarlo cuando llega `clasificacion_final`.

### Card

```json
{
  "tipo": "card",
  "mensaje": {
    "nombre_sitio": "Museo de la Ciudad",
    "categoria": "Manifestaciones Culturales",
    "direccion": "Centro histórico",
    "imagen_url": "/api/v1/imagenes/museo/portada.jpg"
  }
}
```

Uso:

- Resultados de sitios turísticos.
- Máximo 5 cards por respuesta.

Pintado móvil recomendado:

- Tarjeta con nombre como título.
- Categoría como subtítulo.
- Imagen principal arriba si llega `imagen_url`.
- Dirección debajo; si llega vacía, mostrar “Dirección no disponible”.
- Si `imagen_url` es relativa (`/api/v1/imagenes/...`), resolverla contra el host HTTP de la API/app.

### IDs Asociados

```json
{
  "tipo": "ids_asociados",
  "mensaje": {
    "ids_asociados": [12, 45, 78]
  }
}
```

Uso:

- Conectar la respuesta del chat con catálogo y mapa.
- Siempre contiene todos los IDs válidos, aunque solo se pinten 5 cards.

Pintado móvil recomendado:

- No hace falta mostrarlo como texto al usuario final.
- Usarlo para habilitar botones como “Ver en catálogo” o “Ver en mapa”.

### Opciones

```json
{
  "tipo": "opciones",
  "mensaje": {
    "opciones": ["senderismo", "ciclismo", "caminata urbana"]
  }
}
```

Uso:

- Fallback con sugerencias.
- Consultas ambiguas.

Pintado móvil recomendado:

- Chips seleccionables.
- Al tocar un chip, enviar un nuevo mensaje usando ese valor o completar la caja de texto.

### Acción

```json
{
  "tipo": "accion",
  "mensaje": {
    "accion": "abrir_chatbot_sitio",
    "label": "Abrir chatbot del sitio",
    "id_sitio": 69,
    "nombre_sitio": "Casa Museo de Riobamba"
  }
}
```

Uso:

- Delegar una `pregunta_directa` al chatbot específico de un sitio.
- No representa una card ni un resultado de catálogo.

Pintado móvil recomendado:

- Botón debajo del globo del asistente.
- Al tocarlo, abrir el flujo específico del sitio con `id_sitio` y `nombre_sitio`.
- Si el flujo específico usa WebSocket, conectar a `/ws/pregunta_directa` enviando el mismo `id_sitio` y `nombre_sitio`.

## Flujo Interno Actual

Para `/ws/exploracion`, si el flujo compartido no bloquea:

1. `cargar_memoria`: lee turnos y entidades previas desde Redis.
2. `crear_plan`: llama al LLM clasificador y valida JSON.
3. `ejecutar_plan`: ejecuta herramientas según el plan.
4. `guardar_memoria`: guarda el turno y entidades resueltas.

El ejecutor:

- Ejecuta cada elemento de `consultas` en paralelo.
- Ejecuta las herramientas de cada consulta secuencialmente por `orden`.
- Pasa `ids_consulta` entre herramientas.
- Registra cada herramienta con:

```json
{
  "herramienta": "busqueda_semantica",
  "orden": 1,
  "status": "ok",
  "ids": [12, 45],
  "payload": {},
  "nota": ""
}
```

## Herramientas De Exploración

Las herramientas HTTP consumen las APIs documentadas en [`apis/docs/chatboot_arquitectura_api.md`](../../apis/docs/chatboot_arquitectura_api.md).

Todas las llamadas internas `chatboot -> apis` pasan por `herramientas/cliente_http.py`.

| Herramienta del plan | Archivo del ejecutor | Endpoint API |
|---|---|---|
| `busqueda_referencia` | `herramientas/busqueda_referencia.py` | `/api/v1/chatboot/herramientas/busqueda-referencia` |
| `contactos` | `herramientas/contacto_busqueda.py` | `/api/v1/chatboot/herramientas/contacto-busqueda` |
| `horario` | `herramientas/horario_consulta.py` | `/api/v1/chatboot/herramientas/horario-consulta` |
| `precio` | `herramientas/precio_consulta.py` | `/api/v1/chatboot/herramientas/precio-consulta` |
| `tarifa_acceso` | `herramientas/tarifa_acceso_consulta.py` | `/api/v1/chatboot/herramientas/tarifa-acceso-consulta` |
| `atributos_booleanos` | `herramientas/atributos_booleanos_consulta.py` | `/api/v1/chatboot/herramientas/atributos-booleanos-consulta` |
| `ruta` | `herramientas/ruta_consulta.py` | `/api/v1/chatboot/herramientas/ruta-consulta` |
| `gis` | `herramientas/gis_consulta.py` | `/api/v1/chatboot/herramientas/gis-consulta` |
| `busqueda_semantica` | `herramientas/busqueda_semantica_consulta.py` | `/api/v1/chatboot/herramientas/busqueda-semantica-consulta` |
| `pregunta_directa` | `herramientas/pregunta_directa.py` | `/api/v1/chatboot/herramientas/pregunta-directa` |
| `conversacional` | `herramientas/conversacional.py` | Interna |
| `fallback` | `herramientas/fallback.py` | Interna |
| `pensamiento_fake` | `herramientas/pensamiento_fake.py` | Interna / guion stream |

Reglas relevantes:

- GIS requiere candidatos previos; si no hay `ids_consulta`, no se llama la API.
- En pipeline `ruta -> gis`, el ejecutor fuerza `entidad: "ruta"`.
- `busqueda_semantica` puede ampliar a catálogo global desde la API; el ejecutor conserva los IDs devueltos.
- Preguntas turísticas demasiado abiertas como “recomienda algo bonito para visitar” deben ir a `fallback`, no a búsqueda semántica.
- Si el mensaje combina una intención ejecutable con otra demasiado abierta, la parte abierta va en otra consulta con `fallback`.
- `pregunta_directa` genera salida determinística: si resuelve un sitio con alta confianza, envía globo + acción `abrir_chatbot_sitio`; si solo hay coincidencias medias, envía globo + opciones para que el usuario confirme. No genera cards ni usa redactor exploratorio.
- Horarios con varios días usan `dias_semana`; por ejemplo, fines de semana en la tarde debe enviarse como `tipo:"bloque_tiempo"`, `dias_semana:[6,7]`, `rango_hora:["12:00","17:59"]`.

Aliases aceptados por el registro de exploración:

| Nombre principal | Aliases |
|---|---|
| `busqueda_ubicacion` | `busqueda_ubicacion_consulta` |
| `contactos` | `contacto_busqueda` |
| `horario` | `horario_consulta` |
| `precio` | `precio_consulta` |
| `tarifa_acceso` | `tarifa_acceso_consulta` |
| `atributos_booleanos` | `atributos_booleanos_consulta` |
| `ruta` | `ruta_consulta` |
| `gis` | `gis_consulta` |
| `busqueda_semantica` | `busqueda_semantica_consulta` |
| `pregunta_directa` | `pregunta-directa` |

## Herramientas De Pregunta Directa

El chatbot específico de sitio usa herramientas propias:

| Herramienta | Uso |
|---|---|
| `documento_sitio` | Busca en el documento principal del sitio. |
| `ficha_sitio` | Consulta datos estructurados de la ficha. |
| `chunk_documento` | Busca chunks del documento. |
| `multimedia` | Recupera recursos multimedia asociados. |
| `como_llegar` | Resuelve indicaciones relacionadas con llegada/ubicación. |
| `conversacional` | Respuesta interna conversacional. |
| `fallback` | Respuesta interna cuando no se puede resolver. |

Alias: `chuck_documento` se mantiene como alias de `chunk_documento`.

## Probador Web

El probador vive en:

```text
chatboot/docs/probar_chatboot/
```

Abrir:

```text
chatboot/docs/probar_chatboot/chatboot.html
```

El probador simula la app móvil:

- Permite elegir `/ws/exploracion` o `/ws/pregunta_directa`.
- Incluye escenarios rápidos: pregunta directa en exploración, museos cerca, y preguntas en chat del sitio.
- Simula el flujo móvil completo: exploración → botón `abrir_chatbot_sitio` → reconexión a `/ws/pregunta_directa` con `id_sitio` y `nombre_sitio`.
- Para pruebas directas usa por defecto `id_sitio: 68` y `nombre_sitio: "Mercado de la Merced"`.
- Muestra barra de contexto del sitio, botón **Volver** a exploración, `id_sitio` y `nombre_sitio` en el compositor del canal del sitio.
- Muestra arriba la URL WebSocket, estado, tiempo de respuesta y cantidad de streams.
- Renderiza chat con globos (soporta negritas `**texto**`), streams, cards, multimedia, opciones (chips tocables), acciones e IDs asociados solo en el panel técnico.
- Muestra en un panel lateral la clasificación del LLM: plan, errores, texto limpio e inyección.
- Muestra en otro panel la ejecución: estados de herramientas, IDs, mensajes renderizables y último payload enviado.

## Contrato Para El Frontend Móvil

La app debe mantener dos capas:

- Capa visual: pinta `stream`, `globo`, `card`, `multimedia`, `opciones` y acciones.
- Capa funcional: conserva `sesion_id` e `ids_asociados` para memoria, catálogo y mapa.

Orden recomendado al recibir la respuesta final:

1. Si llega `exploracion.mensajes_app`, iterar y pintar en orden.
2. Si no llega, pintar `payload.mensaje_app`.
3. Guardar `payload.sesion_id`.
4. Guardar `exploracion.ids_asociados`.
5. Usar `exploracion.estados_herramientas` solo para debug/observabilidad, no para UI final.
