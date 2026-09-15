# Contrato App Movil - Chatboot

Este documento describe el contrato que debe consumir la app movil para los dos
canales del chatboot:

- `exploracion`: busqueda turistica general, recomendaciones, filtros, cercania,
  rutas y delegacion hacia un sitio.
- `pregunta_directa`: chatbot especifico de un sitio ya identificado.

El canal se decide por la ruta WebSocket. La app envia el mensaje plano; el
backend lo envuelve internamente con `pregunta_chatboot`.

## 1. Rutas WebSocket

| Canal | Ruta | Uso |
|---|---|---|
| Exploracion | `/ws/exploracion` | Recomendar o buscar sitios/rutas en el catalogo turistico. |
| Pregunta directa | `/ws/pregunta_directa` | Preguntar sobre un sitio activo con `id_sitio` y `nombre_sitio`. |

Al abrir el socket, el backend emite dos eventos de conexion:

```json
{
  "tipo": "conexion",
  "estado": "inicializando",
  "canal": "exploracion",
  "pregunta_chatboot": "exploracion"
}
```

```json
{
  "tipo": "conexion",
  "estado": "conectado",
  "canal": "exploracion",
  "pregunta_chatboot": "exploracion",
  "warmup": {
    "ok": true,
    "rutas": ["exploracion"]
  }
}
```

Reglas de app:

- No pintar estos eventos como mensajes del chat.
- Mostrar estado "inicializando" mientras llega el warmup.
- Habilitar el input cuando llegue `estado = "conectado"`.
- Guardar `canal` y `pregunta_chatboot` solo para debug.

## 2. Mensaje Que Envia La App

La app envia un JSON plano por cada mensaje. No debe incluir
`pregunta_chatboot`; la ruta WebSocket ya define el canal.

### 2.1 Exploracion

Enviar a `/ws/exploracion`:

```json
{
  "mensaje_usuario": "Busco un museo y un parque para visitar en familia",
  "id_usuario": 1,
  "client_message_id": "550e8400-e29b-41d4-a716-446655440000",
  "sesion_Id": "uuid-sesion-devuelto-por-backend-o-null",
  "ubicacion_usuario": {
    "lat": -1.6736,
    "lng": -78.6473
  }
}
```

### 2.2 Pregunta directa

Enviar a `/ws/pregunta_directa`. Ademas de los campos base, se requiere
`id_sitio` y `nombre_sitio`.

```json
{
  "mensaje_usuario": "Cuentame sobre el mercado",
  "id_usuario": 1,
  "client_message_id": "550e8400-e29b-41d4-a716-446655440001",
  "sesion_Id": "uuid-sesion-devuelto-por-backend-o-null",
  "ubicacion_usuario": {
    "lat": -1.6736,
    "lng": -78.6473
  },
  "id_sitio": 68,
  "nombre_sitio": "Mercado de la Merced"
}
```

Valores por defecto recomendados para pruebas de pregunta directa:

```json
{
  "id_sitio": 68,
  "nombre_sitio": "Mercado de la Merced"
}
```

### 2.3 Campos de entrada

| Campo | Tipo | Obligatorio | Canal | Regla |
|---|---:|---:|---|---|
| `mensaje_usuario` | string | Si | Ambos | Texto del usuario. No puede estar vacio. |
| `client_message_id` | string | Si | Ambos | UUID generado por la app por cada mensaje enviado. No reutilizar. |
| `sesion_Id` | string/null | No | Ambos | En el primer mensaje puede ir `null`; luego reenviar el `sesion_id` devuelto por backend. |
| `id_usuario` | number/null | Recomendado | Ambos | Si falta, el chat responde pero no guarda historial en PostgreSQL. |
| `ubicacion_usuario` | object | Si | Ambos | Puede ser `{}` si el usuario no dio permiso. Para GIS enviar `lat` y `lng`. |
| `id_sitio` | number | Si | Pregunta directa | Entero positivo del sitio activo. |
| `nombre_sitio` | string | Si | Pregunta directa | Nombre visible del sitio. No puede estar vacio. |

Notas:

- El backend tambien acepta `sesion_id`, pero la app debe preferir `sesion_Id`
  para mantener compatibilidad con el contrato actual.
- Para ubicacion se recomienda `lng`; internamente puede normalizarse a `lon`.
- Campos extra pueden provocar error de validacion en la capa interna. Evitar
  enviar propiedades no documentadas.
- Si se envia texto plano en vez de JSON, el backend lo interpreta como mensaje,
  pero no habra `client_message_id`; la app movil no debe usar ese modo.

## 3. Eventos Que Recibe La App

### 3.1 `conexion`

Evento tecnico del ciclo de vida del socket.

```json
{
  "tipo": "conexion",
  "estado": "conectado",
  "canal": "pregunta_directa",
  "pregunta_chatboot": "pregunta_directa",
  "warmup": {
    "ok": true,
    "rutas": ["exploracion", "sitio"]
  }
}
```

Reglas de app:

- No guardar en historial local.
- No pintar como burbuja.
- Usar para estado de conexion y diagnostico.

### 3.2 `stream`

Evento temporal. Puede ser un progreso simulado mientras se ejecutan herramientas
o un stream real del redactor en pregunta directa.

```json
{
  "tipo": "stream",
  "canal": "pregunta_directa",
  "client_message_id": "550e8400-e29b-41d4-a716-446655440001",
  "payload": {
    "tipo": "stream",
    "mensaje": {
      "origen": "redactor_pregunta_directa",
      "fase": "redactando_respuesta",
      "texto": "El Mercado de la Merced es..."
    }
  }
}
```

Reglas de app:

- Asociar siempre por `client_message_id`.
- Mostrar un solo globo temporal del asistente para ese mensaje.
- Cada nuevo stream reemplaza o actualiza el texto del globo temporal.
- No persistir como respuesta final.
- Eliminar o convertir el temporal cuando llegue `clasificacion_final`.

### 3.3 `clasificacion_final`

Evento definitivo del turno.

```json
{
  "tipo": "clasificacion_final",
  "canal": "exploracion",
  "payload": {
    "pregunta_chatboot": "exploracion",
    "client_message_id": "550e8400-e29b-41d4-a716-446655440000",
    "sesion_id": "6e93e2dd-66fe-4705-b610-6d508a2f651d",
    "id_usuario": 1,
    "ubicacion_usuario": {
      "lat": -1.6736,
      "lng": -78.6473
    },
    "mensaje": {
      "mensaje_usuario": "Busco un museo y un parque para visitar en familia",
      "texto_limpio": "Busco un museo y un parque para visitar en familia",
      "riesgo_prompt_inyection": {
        "score": 0,
        "porcentaje": 0,
        "bloqueado": false,
        "coincidencias": [],
        "motivo_principal": null
      },
      "palabras_inyectadas": []
    },
    "mensaje_app": {
      "tipo": "globo",
      "mensaje": {
        "texto": "Claro, abajo te muestro opciones que pueden servirte.",
        "origen": "redactor_exploracion"
      }
    },
    "exploracion": {
      "plan_valido": true,
      "plan": {
        "consultas": []
      },
      "errores_formato": [],
      "estados_herramientas": [],
      "ids_asociados": [12, 68],
      "mensajes_app": []
    }
  }
}
```

Reglas de app:

- Guardar `payload.sesion_id` y reenviarlo como `sesion_Id` en el siguiente
  mensaje del mismo chat.
- Usar `payload.client_message_id` para cerrar el turno pendiente.
- Pintar con `payload.exploracion.mensajes_app` si el canal es exploracion.
- Pintar con `payload.pregunta_directa.mensajes_app` si el canal es pregunta
  directa.
- Si no hay lista de `mensajes_app`, usar `payload.mensaje_app` como fallback.

### 3.4 `error_validacion`

Evento de error para un mensaje que no pudo procesarse.

```json
{
  "tipo": "error_validacion",
  "canal": "exploracion",
  "client_message_id": "550e8400-e29b-41d4-a716-446655440000",
  "sesion_id": "6e93e2dd-66fe-4705-b610-6d508a2f651d",
  "mensaje": "El mensaje no pudo procesarse con la estructura requerida.",
  "detalle": "client_message_id es obligatorio."
}
```

Reglas de app:

- Eliminar el stream temporal de ese `client_message_id`.
- Pintar `mensaje` como globo de error.
- Mostrar `detalle` solo en modo debug; no exponer errores tecnicos al usuario
  final.
- No habilitar botones de catalogo, mapa ni acciones del sitio para ese turno.

## 4. Payload Comun De Respuesta

`clasificacion_final.payload` siempre contiene estos campos base:

| Campo | Tipo | Uso |
|---|---:|---|
| `pregunta_chatboot` | string | `exploracion` o `pregunta_directa`. |
| `client_message_id` | string | Correlacion con el mensaje de la app. |
| `sesion_id` | string | Sesion real asignada por backend. |
| `id_usuario` | number/null | Usuario recibido. Puede faltar si no se envio. |
| `ubicacion_usuario` | object | Ubicacion recibida. |
| `id_sitio` | number/null | Presente en pregunta directa o cuando aplica. |
| `nombre_sitio` | string/null | Presente en pregunta directa o cuando aplica. |
| `mensaje` | object | Texto original, texto limpio y analisis de seguridad. |
| `mensaje_sistema` | string/null | Texto final o mensaje tecnico interno. No usar como primera opcion de pintado. |
| `mensaje_app` | object/null | Mensaje principal para fallback de pintado. |
| `exploracion` | object/null | Resultado del canal exploracion. |
| `pregunta_directa` | object/null | Resultado del canal especifico. |

`payload.mensaje`:

```json
{
  "mensaje_usuario": "texto original",
  "texto_limpio": "texto despues de limpieza",
  "riesgo_prompt_inyection": {
    "score": 0,
    "porcentaje": 0,
    "bloqueado": false,
    "coincidencias": [],
    "motivo_principal": null
  },
  "palabras_inyectadas": []
}
```

Si `riesgo_prompt_inyection.bloqueado = true`, normalmente habra un `globo` de
seguridad en `mensaje_app`; la app debe pintarlo como respuesta final y no mostrar
cards.

## 5. Resultado De Exploracion

El bloque `payload.exploracion` resume la ejecucion de herramientas generales.

```json
{
  "plan_valido": true,
  "plan": {
    "consultas": [
      {
        "ejecucion_herramienta": [
          {
            "orden": 1,
            "herramienta": {
              "nombre": "busqueda_semantica",
              "parametros": {
                "texto_embeddings": "museos para visitar en familia",
                "keywords": ["museo", "familia"]
              }
            }
          }
        ]
      }
    ]
  },
  "errores_formato": [],
  "estados_herramientas": [
    {
      "herramienta": "busqueda_semantica",
      "orden": 1,
      "status": "ok",
      "ids": [10, 11, 12],
      "payload": {},
      "nota": "Sitios encontrados."
    }
  ],
  "ids_asociados": [10, 11, 12],
  "mensajes_app": [
    {
      "tipo": "globo",
      "mensaje": {
        "texto": "Claro, abajo te muestro opciones que pueden servirte.",
        "origen": "redactor_exploracion"
      }
    },
    {
      "tipo": "card",
      "mensaje": {
        "id_sitio": 10,
        "nombre_sitio": "Museo y Centro Cultural de Riobamba",
        "categoria": "Manifestaciones Culturales",
        "direccion": "Calle Veloz s/n, entre Juan Montalvo y Carabobo",
        "imagen_url": "https://example.com/museo.jpg"
      }
    },
    {
      "tipo": "ids_asociados",
      "mensaje": {
        "ids_asociados": [10, 11, 12]
      }
    }
  ]
}
```

Campos de exploracion:

| Campo | Tipo | Uso |
|---|---:|---|
| `plan_valido` | boolean | Indica si el plan JSON paso validacion. |
| `plan` | object/null | Plan saneado que se ejecuto. Solo debug. |
| `errores_formato` | array | Advertencias o errores del plan. Mostrar solo en debug. |
| `estados_herramientas` | array | Estado por herramienta ejecutada. Solo debug o analitica. |
| `ids_asociados` | array<number> | IDs finales validos para catalogo/mapa. |
| `mensajes_app` | array | Lista ordenada para pintar. |

Reglas de exploracion:

- El formato visual esperado es un solo globo principal y uno o mas bloques de
  cards.
- Si una consulta produce varias ejecuciones, el backend conserva estados y sigue
  con las herramientas posibles aunque una falle.
- Puede haber varios bloques de cards separados por `ids_asociados`.
- `ids_asociados` del bloque raiz puede contener todos los IDs validados; las
  cards visibles pueden ser una muestra.
- `errores_formato` puede incluir herramientas descartadas por venir vacias; eso
  no necesariamente significa que la respuesta fallo.

Ejemplos de `errores_formato` no fatales:

```json
[
  {
    "tipo": "herramienta_sin_valor",
    "consulta": 1,
    "paso": 1,
    "herramienta": "busqueda_semantica",
    "detalle": "La herramienta no tenia parametros utiles y fue descartada."
  }
]
```

## 6. Resultado De Pregunta Directa

El bloque `payload.pregunta_directa` resume la ejecucion del chatbot especifico
del sitio.

```json
{
  "plan_valido": true,
  "plan": {
    "consultas": [
      {
        "ejecucion_herramienta": [
          {
            "orden": 1,
            "herramienta": {
              "nombre": "documento_sitio",
              "parametros": {}
            }
          }
        ]
      }
    ]
  },
  "errores_formato": [],
  "estados_herramientas": [
    {
      "herramienta": "documento_sitio",
      "orden": 1,
      "status": "ok",
      "ids": [68],
      "payload": {},
      "nota": "Documento del sitio obtenido."
    }
  ],
  "ids_asociados": [68],
  "mensajes_app": [
    {
      "tipo": "globo",
      "mensaje": {
        "texto": "El Mercado de la Merced es un punto tradicional de Riobamba...",
        "origen": "redactor_pregunta_directa"
      }
    }
  ],
  "entidades_resueltas": ["Mercado de la Merced"]
}
```

Campos de pregunta directa:

| Campo | Tipo | Uso |
|---|---:|---|
| `plan_valido` | boolean | Indica si el plan especifico fue valido. |
| `plan` | object/null | Plan saneado del LLM. Solo debug. |
| `errores_formato` | array | Advertencias o errores del plan. Solo debug. |
| `estados_herramientas` | array | Estado por herramienta especifica. |
| `ids_asociados` | array<number> | Normalmente contiene el `id_sitio`. |
| `mensajes_app` | array | Lista ordenada para pintar. |
| `entidades_resueltas` | array<string> | Nombres resueltos por el flujo. |

Herramientas especificas esperadas:

| Herramienta | Salida visual | Redactor LLM |
|---|---|---:|
| `conversacional` | `globo` desde plantilla | No |
| `fallback` | `globo` con `respuesta_sugerida` | No |
| `documento_sitio` | `globo` redactado | Si |
| `ficha_sitio` | `globo` redactado | Si |
| `chuck_documento` | `globo` redactado | Si |
| `multimedia` | `multimedia` | No |
| `como_llegar` | `globo` + `accion` Google Maps | No |

Reglas de pregunta directa:

- Este canal no debe pintar cards de catalogo como resultado principal.
- Para informacion textual, pintar globos.
- Para imagenes, pintar `multimedia`.
- Para indicaciones de llegada, pintar el globo y el boton de Google Maps.
- El stream del redactor puede llegar token a token antes del globo definitivo.

## 7. Tipos De `mensajes_app`

La app debe recorrer `mensajes_app` en orden y renderizar segun `tipo`.

### 7.1 `globo`

```json
{
  "tipo": "globo",
  "mensaje": {
    "texto": "Abajo te muestro opciones relacionadas que pueden servirte.",
    "origen": "redactor_exploracion"
  }
}
```

Pintado:

- Burbuja del asistente.
- Mostrar `mensaje.texto`.
- `origen` es tecnico; no mostrar al usuario final.
- El texto puede venir con emojis y marcas simples tipo `**texto**`; la app puede
  renderizar negrita si su componente lo soporta.

### 7.2 `card`

```json
{
  "tipo": "card",
  "mensaje": {
    "id_sitio": 10,
    "nombre_sitio": "Museo y Centro Cultural de Riobamba",
    "categoria": "Manifestaciones Culturales",
    "direccion": "Calle Veloz s/n, entre Juan Montalvo y Carabobo",
    "imagen_url": "https://example.com/museo.jpg"
  }
}
```

Pintado:

- Agrupar cards consecutivas en un bloque "Resultados".
- Usar carrusel horizontal o lista compacta.
- Si falta `imagen_url`, mostrar placeholder.
- Si falta `direccion`, mostrar "Direccion no disponible".
- Al tocar una card, la app puede abrir ficha del sitio por `id_sitio`.

### 7.3 `ids_asociados`

```json
{
  "tipo": "ids_asociados",
  "mensaje": {
    "ids_asociados": [10, 11, 12, 13, 14, 15]
  }
}
```

Uso funcional:

- No pintar como texto visible.
- Actualizar `ids_finales` del turno.
- Estos IDs pueden ser mas que las cards visibles.
- Usar para botones:
  - `Ver en catalogo`
  - `Ver en mapa`

Reglas:

- Si `ids_finales.length > 0`, habilitar botones de catalogo/mapa.
- Si `ids_finales.length == 1`, se puede abrir directamente la ficha o centrar el
  mapa en ese sitio.
- Si no hay IDs, ocultar esos botones.

### 7.4 `multimedia`

```json
{
  "tipo": "multimedia",
  "mensaje": {
    "origen": "multimedia",
    "imagenes": [
      {
        "url": "https://example.com/mercado.jpg",
        "titulo": "Fachada del mercado",
        "descripcion": "Imagen del Mercado de la Merced",
        "es_principal": true
      }
    ]
  }
}
```

Pintado:

- Galeria horizontal o grid de imagenes.
- Usar `url` como fuente principal.
- `titulo`, `descripcion` y `es_principal` son opcionales segun API.
- Si `imagenes` esta vacio, no pintar galeria.

### 7.5 `opciones`

```json
{
  "tipo": "opciones",
  "mensaje": {
    "opciones": ["museos", "restaurantes", "parques"]
  }
}
```

Pintado:

- Chips o botones pequenos debajo del globo.
- Al tocar una opcion:
  - llenar el input, o
  - enviar un nuevo mensaje con esa opcion como `mensaje_usuario`.

### 7.6 `accion`

Accion para abrir el chatbot especifico desde exploracion:

```json
{
  "tipo": "accion",
  "mensaje": {
    "accion": "abrir_chatbot_sitio",
    "label": "Abrir chatbot del sitio",
    "id_sitio": 68,
    "nombre_sitio": "Mercado de la Merced"
  }
}
```

Accion para Google Maps desde pregunta directa:

```json
{
  "tipo": "accion",
  "mensaje": {
    "accion": "abrir_google_maps",
    "label": "Abrir Google Maps",
    "url": "https://www.google.com/maps/search/?api=1&query=-1.67,-78.64",
    "lat": -1.67,
    "lon": -78.64,
    "nombre_sitio": "Mercado de la Merced"
  }
}
```

Pintado:

- Boton debajo del globo o del bloque relacionado.
- Texto del boton: `mensaje.label`.
- Si `accion = "abrir_chatbot_sitio"`, cambiar a la pantalla/canal de pregunta
  directa y conectar a `/ws/pregunta_directa`.
- Si `accion = "abrir_google_maps"`, abrir `mensaje.url` con el manejador externo
  del dispositivo.

### 7.7 `stream`

Normalmente llega como evento WebSocket de nivel superior. Si aparece dentro de
`mensajes_app`, tratarlo igual como temporal.

```json
{
  "tipo": "stream",
  "mensaje": {
    "origen": "pensamiento_fake",
    "fase": "analizando_intencion",
    "texto": "Estoy analizando tu consulta.",
    "indice": 1,
    "total": 6
  }
}
```

## 8. Orden De Pintado Recomendado

Al recibir `clasificacion_final`:

1. Buscar el turno por `client_message_id`.
2. Eliminar o cerrar el globo temporal de stream.
3. Guardar `payload.sesion_id` para siguientes mensajes.
4. Elegir la lista visual:
   - `payload.exploracion.mensajes_app` si existe y el canal es exploracion.
   - `payload.pregunta_directa.mensajes_app` si existe y el canal es pregunta directa.
   - `payload.mensaje_app` como fallback.
5. Recorrer la lista en orden.
6. Agrupar `card` consecutivas en un bloque de resultados.
7. Cuando aparezca `ids_asociados`, actualizar `ids_finales`.
8. Renderizar `multimedia`, `opciones` y `accion` segun su tipo.
9. Habilitar botones de catalogo/mapa solo si hay `ids_finales`.

Estado local recomendado por turno:

```json
{
  "client_message_id": "550e8400-e29b-41d4-a716-446655440000",
  "sesion_id": "6e93e2dd-66fe-4705-b610-6d508a2f651d",
  "canal": "exploracion",
  "ids_finales": [10, 11, 12],
  "estado": "respondido"
}
```

## 9. Historial Y Sesion

El backend persiste historial solo cuando llega `id_usuario`.

### 9.1 Exploracion

Tabla: `conversacion.mensaje_explorador`.

Por cada `client_message_id` se guardan hasta dos filas:

| Rol | Contenido |
|---|---|
| `usuario` | Texto limpio de la pregunta. |
| `conversacion_general` | JSON final completo enviado a la app. |

El backend reutiliza o crea la conversacion por:

```txt
id_usuario + sesion_id
```

La idempotencia evita duplicar por:

```txt
id_conversacion + client_mensaje_id + rol
```

### 9.2 Pregunta directa

Tabla: `conversacion.mensaje_detalle`.

Por cada `client_message_id` se guardan hasta dos filas:

| Rol | Contenido | Entidad |
|---|---|---|
| `usuario` | Texto limpio de la pregunta. | `nombre_sitio` |
| `conversacion_sitio_especifico` | JSON final completo enviado a la app. | `nombre_sitio` |

Tambien usa:

```txt
id_usuario + sesion_id
```

y evita duplicar por:

```txt
id_conversacion + client_mensaje_id + rol
```

Reglas de app:

- Generar un `client_message_id` nuevo por cada mensaje enviado.
- No reutilizar `client_message_id` entre sesiones.
- Reenviar siempre el `sesion_id` devuelto por backend como `sesion_Id`.
- Mantener sesiones separadas si la UI separa exploracion y sitio especifico.
- Para reconstruir historial, agrupar por `client_mensaje_id`: pintar la fila
  `usuario` y luego parsear el JSON de la fila de respuesta.

## 10. Errores Y Fallbacks

Errores de validacion de entrada llegan como `error_validacion`.

Errores internos de herramientas normalmente no deben llegar como excepcion al
usuario. Se reportan en:

```json
{
  "estados_herramientas": [
    {
      "herramienta": "busqueda_semantica",
      "orden": 1,
      "status": "sin_resultados",
      "ids": [],
      "payload": {
        "sin_sitios": "No se encontraron sitios relacionados."
      },
      "nota": "No se encontraron sitios relacionados."
    }
  ]
}
```

Reglas:

- `status = "ok"`: la herramienta encontro informacion util.
- `status = "sin_resultados"`: no hubo datos, pero el flujo puede responder con
  fallback.
- `status = "error"`: fallo esa herramienta; el flujo intenta continuar cuando es
  posible.
- No mostrar `payload.fallo`, errores HTTP, scores, embeddings ni SQL al usuario.
- El redactor debe producir un globo amable cuando no hay resultados exactos.

## 11. Checklist Para Integracion Movil

- Abrir `/ws/exploracion` para busqueda general.
- Abrir `/ws/pregunta_directa` solo si ya existe `id_sitio` y `nombre_sitio`.
- Enviar siempre `mensaje_usuario`, `client_message_id` y `ubicacion_usuario`.
- Enviar `id_usuario` para persistir historial.
- Guardar `sesion_id` recibido y reenviarlo como `sesion_Id`.
- Asociar `stream`, `clasificacion_final` y `error_validacion` por
  `client_message_id`.
- Pintar segun `mensajes_app` y no segun `estados_herramientas`.
- En exploracion, usar `ids_asociados` para catalogo/mapa.
- En pregunta directa, no pintar cards como respuesta principal; usar globos,
  multimedia y acciones.
- Mostrar detalles tecnicos solo en pantallas de debug.

## 12. Resumen Rapido

```txt
Enviar exploracion:
  /ws/exploracion
  mensaje_usuario, id_usuario, client_message_id, sesion_Id, ubicacion_usuario

Enviar pregunta directa:
  /ws/pregunta_directa
  mensaje_usuario, id_usuario, client_message_id, sesion_Id, ubicacion_usuario,
  id_sitio, nombre_sitio

Recibir:
  conexion            -> estado del socket, no pintar
  stream              -> globo temporal por client_message_id
  clasificacion_final -> respuesta definitiva
  error_validacion    -> globo de error amable

Pintar:
  globo          -> burbuja asistente
  card           -> bloque/carrusel de resultados
  ids_asociados  -> estado interno para catalogo/mapa
  multimedia     -> galeria
  opciones       -> chips
  accion         -> boton
  stream         -> temporal
```
