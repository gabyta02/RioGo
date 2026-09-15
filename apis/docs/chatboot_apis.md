# APIs Chatboot

> **Documentación vigente (herramientas H1–H13):** [`chatboot_arquitectura_api.md`](chatboot_arquitectura_api.md)  
> Base nueva: `/api/v1/chatboot/herramientas/*` · Probador: `tests/probar_apis_chatboot.py`

Este archivo describe el **monolito legacy** `POST /api/v1/chatboot/*` en
`servicios/chatboot_reutilizar.py` (router comentado en `main.py`). Se mantiene como
referencia hasta migrar el ejecutor del chatboot a las herramientas modulares.

Endpoints internos consumidos por el servicio `chatboot`. Base legacy: `/api/v1/chatboot`.

No requieren autenticacion JWT; deben exponerse solo en la red interna del proyecto.

## Herramientas modulares (reemplazo)

| Legacy | Nueva ruta | Estado |
|--------|------------|--------|
| `busqueda_aproximada` | `.../busqueda-referencia` | H2 implementada |
| `campos_parametrizados` | `.../atributos-booleanos-consulta` | H7 implementada |
| `contactos` | `.../contacto-busqueda` | H3 implementada |
| `horario` | `.../horario-consulta` | H4 implementada |
| `precio` | `.../precio-consulta` | H5 implementada |
| `tarifa_acceso` | `.../tarifa-acceso-consulta` | H6 implementada |
| `ruta` | `.../ruta-consulta` | H9 implementada |
| `gis` | `.../gis-consulta` | H8 implementada (`entidad`: sitio/ruta) |
| `busqueda_semantica` | `.../busqueda-semantica-consulta` | H10 implementada (chunks RAG) |
| — | `.../categoria-subcategoria` | H1 (nueva) |

## Tests manuales (legacy)

Scripts interactivos en [`apis/docs/`](.):

| Herramienta | Script | Ejecucion |
|-------------|--------|-----------|
| H1 `busqueda_aproximada` | `test_herramienta_01.py` | `python docs/test_herramienta_01.py` |
| H3 `campos_parametrizados` | `test_herramienta_02.py` | `python docs/test_herramienta_02.py` |
| H4 `contactos` | `test_herramienta_03.py` | `python docs/test_herramienta_03.py` |
| H5 `horario` | `test_herramienta_04.py` | `python docs/test_herramienta_04.py` |
| H6 `precio` | `test_herramienta_05.py` | `python docs/test_herramienta_05.py` |
| H7 `tarifa_acceso` | `test_herramienta_06.py` | `python docs/test_herramienta_06.py` |
| H8 `ruta` | `test_herramienta_07.py` | `python docs/test_herramienta_07.py` |
| H9 `gis` | `test_herramienta_08.py` | `python docs/test_herramienta_08.py` |
| H12 `busqueda_semantica` | `test_herramienta_09.py` | `python docs/test_herramienta_09.py` |

Dentro del contenedor:

```bash
docker exec -it riobambago-apis python docs/test_herramienta_01.py
docker exec -it riobambago-apis python docs/test_herramienta_02.py
docker exec -it riobambago-apis python docs/test_herramienta_03.py
docker exec -it riobambago-apis python docs/test_herramienta_04.py
docker exec -it riobambago-apis python docs/test_herramienta_05.py
docker exec -it riobambago-apis python docs/test_herramienta_06.py
docker exec -it riobambago-apis python docs/test_herramienta_07.py
docker exec -it riobambago-apis python docs/test_herramienta_08.py
docker exec -it riobambago-apis python docs/test_herramienta_09.py
```

---

## Alcance de sitios (comun H1–H7, H9, H12)

Ambas APIs aceptan parametros opcionales para limitar **sobre que sitios** se aplican los filtros.

Prioridad:

1. **`ids_sitios_candidatos`** — si el LLM u otra herramienta ya devolvio IDs candidatos, los filtros solo se aplican a esos sitios.
2. **`categoria` / `subcategoria`** — si no hay IDs, se resuelven por trigramas contra `turismo.categoria` y `turismo.subcategoria` y se filtran los sitios de ese catalogo.
3. **Sin alcance** — se consulta el universo de sitios activos.

Campos de respuesta relacionados:

- `alcance_aplicado`: `todos` | `categoria` | `subcategoria` | `ids_candidatos`
- `categoria_resuelta`, `subcategoria_resuelta`
- `ids_sitios_candidatos_aplicados`

---

## H1 · busqueda_aproximada

**Herramienta del planificador:** filtra por direccion, calle, parroquia o plataforma.

```http
POST /api/v1/chatboot/busqueda-aproximada
```

### Request

```json
{
  "direccion_referencia": "jose veloz y morona",
  "excluir": [],
  "categoria": "hospedaje",
  "subcategoria": "hotel",
  "ids_sitios_candidatos": []
}
```

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `direccion_referencia` | `string` | Texto de direccion, calle, parroquia o plataforma (obligatorio). |
| `excluir` | `string[]` | Zonas o terminos a penalizar/excluir. |
| `categoria` | `string \| null` | Nombre de categoria inferida por el LLM. Limita busqueda por direccion. |
| `subcategoria` | `string \| null` | Nombre de subcategoria inferida por el LLM. |
| `ids_sitios_candidatos` | `int[]` | IDs de sitios previos; tiene prioridad sobre categoria/subcategoria. |

### Logica

1. Quita prefijos de via (`calle`, `avenida`, `av.`, etc.) para comparar direcciones.
2. Busca en PostgreSQL con `pg_trgm` (top 5 candidatos por direccion).
3. Revalora con `rapidfuzz` (cobertura por tokens, no solo coincidencia parcial).
4. Compara tambien parroquia y plataforma por nombre.
5. Si gana **direccion** y score >= 70%: devuelve hasta **5 IDs de sitios**.
6. Si gana **parroquia** o **plataforma**: devuelve **un solo nombre** en `nombre`.

El alcance (`categoria`, `subcategoria`, `ids_sitios_candidatos`) aplica **solo a la busqueda por direccion**, no a parroquia/plataforma.

### Response

```json
{
  "ok": true,
  "direccion_referencia_consultada": "calles jose veloz y morona",
  "texto_sin_prefijos_via": "jose veloz y morona",
  "tipo_resultado": "sitio",
  "fuente": "direccion",
  "ids_sitios": [1],
  "nombre": null,
  "alcance_aplicado": "subcategoria",
  "categoria_resuelta": "Hospedaje",
  "subcategoria_resuelta": "Hotel",
  "ids_sitios_candidatos_aplicados": [],
  "excluir_aplicado": [],
  "top_sitios_direccion": [],
  "tiempo_ms": 24.5,
  "mensaje": "Se encontraron 1 sitio(s) por similitud en direccion con score >= 70%."
}
```

| `tipo_resultado` | Campo principal | Contenido |
|------------------|-----------------|-----------|
| `sitio` | `ids_sitios` | Lista de IDs (max. 5) |
| `parroquia` | `nombre` | Nombre de la parroquia |
| `plataforma` | `nombre` | Nombre de la plataforma |
| `ninguno` | — | Sin coincidencia util |

`top_sitios_direccion` es informacion de depuracion (scores trgm + rapidfuzz); el chatboot consume `ids_sitios` o `nombre`.

---

## H3 · campos_parametrizados

**Herramienta del planificador:** filtra sitios por caracteristicas booleanas.

```http
POST /api/v1/chatboot/campos-parametrizados
```

### Request

```json
{
  "tiene_wifi": true,
  "permite_mascotas": null,
  "accesibilidad": null,
  "parqueadero": false,
  "es_gratuito": null,
  "excluir": ["mascotas"],
  "categoria": "gastronomia",
  "subcategoria": "restaurante",
  "ids_sitios_candidatos": []
}
```

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `tiene_wifi` | `true \| false \| null` | Solo si el usuario lo menciona. |
| `permite_mascotas` | `true \| false \| null` | Solo si el usuario lo menciona. |
| `accesibilidad` | `true \| false \| null` | Solo si el usuario lo menciona. |
| `parqueadero` | `true \| false \| null` | Solo si el usuario lo menciona. |
| `es_gratuito` | `true \| false \| null` | Solo si el usuario lo menciona. |
| `excluir` | `string[]` | Caracteristicas a evitar (`wifi`, `mascotas`, `parqueadero`, `gratuito`, `accesibilidad`). |
| `categoria` | `string \| null` | Alcance por categoria. |
| `subcategoria` | `string \| null` | Alcance por subcategoria. |
| `ids_sitios_candidatos` | `int[]` | Alcance por IDs previos (prioridad maxima). |

Debe indicarse al menos un campo booleano distinto de `null` o un termino en `excluir`.

### Logica

- `true` / `false` filtran exactamente ese valor en `turismo.sitio`.
- `excluir` descarta sitios que **tengan** la caracteristica (`campo = TRUE`).
- El alcance limita el universo antes de aplicar los booleanos.

### Response

```json
{
  "ok": true,
  "total": 12,
  "ids_sitios": [1, 5, 17],
  "sitios": [
    {
      "id_sitio": 1,
      "nombre": "Hostal OASIS RIO",
      "tiene_wifi": true,
      "permite_mascotas": false,
      "accesibilidad": null,
      "parqueadero": true,
      "es_gratuito": false
    }
  ],
  "filtros_aplicados": { "tiene_wifi": true },
  "alcance_aplicado": "categoria",
  "categoria_resuelta": "Hospedaje",
  "subcategoria_resuelta": null,
  "ids_sitios_candidatos_aplicados": [],
  "excluir_aplicado": [],
  "tiempo_ms": 8.2,
  "mensaje": "Se encontraron 12 sitio(s) que cumplen los filtros."
}
```

`ids_sitios` es la lista plana para el planificador; `sitios` incluye detalle booleano para depuracion en tests.

---

## H4 · contactos

**Herramienta del planificador:** filtra sitios por canal de contacto o reserva (WhatsApp, email, telefono, etc.).

```http
POST /api/v1/chatboot/contactos
```

### Request

```json
{
  "contacto_sugerido": "whatsapp",
  "excluir_contactos": ["telefono"],
  "categoria": "hospedaje",
  "subcategoria": "hotel",
  "ids_sitios_candidatos": []
}
```

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `contacto_sugerido` | `string` | Canal buscado (`whatsapp`, `email`, `telefono`, `web`, `facebook`, `instagram`, `tiktok`). |
| `excluir_contactos` | `string[]` | Canales que el usuario no quiere; descarta sitios que los tengan registrados. |
| `categoria` | `string \| null` | Alcance por categoria. |
| `subcategoria` | `string \| null` | Alcance por subcategoria. |
| `ids_sitios_candidatos` | `int[]` | Alcance por IDs previos (prioridad maxima). |

Alias aceptados: `whats app`, `wsp`, `correo`, `pagina_web`, `celular`, etc.

### Logica

1. Resuelve `contacto_sugerido` al enum `turismo.tipo_contacto_t`.
2. Aplica alcance (IDs > subcategoria > categoria > todos).
3. Busca sitios activos con contacto activo del tipo sugerido en `turismo.contacto`.
4. Descarta sitios que tengan algun tipo en `excluir_contactos`.
5. Si **encuentra** coincidencias: `ok=true`, `ids_sitios` con los IDs que tienen ese contacto.
6. Si **no encuentra** el contacto sugerido: `ok=false` y devuelve en `sitios` la lista de **todos los contactos disponibles** por cada sitio del alcance (para que el LLM ofrezca alternativas).

### Response — coincidencia encontrada

```json
{
  "ok": true,
  "contacto_sugerido": "whatsapp",
  "contacto_sugerido_resuelto": "whatsapp",
  "ids_sitios": [1, 5],
  "sitios": [
    {
      "id_sitio": 1,
      "nombre": "Hostal OASIS RIO",
      "tiene_contacto_sugerido": true,
      "contactos": [
        { "tipo": "whatsapp", "contenido": "0999999999" },
        { "tipo": "telefono", "contenido": "032961234" }
      ]
    }
  ],
  "alcance_aplicado": "subcategoria",
  "categoria_resuelta": "Hospedaje",
  "subcategoria_resuelta": "Hotel",
  "ids_sitios_candidatos_aplicados": [],
  "excluir_contactos_aplicados": [],
  "tipos_contacto_excluidos": [],
  "tiempo_ms": 12.1,
  "mensaje": "Se encontraron 2 sitio(s) con contacto tipo 'whatsapp'."
}
```

### Response — sin coincidencia (lista alternativas)

```json
{
  "ok": false,
  "contacto_sugerido": "whatsapp",
  "contacto_sugerido_resuelto": "whatsapp",
  "ids_sitios": [],
  "sitios": [
    {
      "id_sitio": 17,
      "nombre": "La Casa del Cura",
      "tiene_contacto_sugerido": false,
      "contactos": [
        { "tipo": "telefono", "contenido": "032000111" },
        { "tipo": "email", "contenido": "info@ejemplo.com" }
      ]
    }
  ],
  "mensaje": "Ningun sitio tiene contacto tipo 'whatsapp'. Se listan los contactos disponibles por sitio."
}
```

---

## H5 · horario

**Herramienta del planificador:** filtra sitios por disponibilidad horaria.

```http
POST /api/v1/chatboot/horario
```

### Request

```json
{
  "tipo": "atiende_dia",
  "dia_semana": "7",
  "hora": null,
  "rango_hora": { "inicio": null, "fin": null },
  "comparador": null,
  "meridiano": null,
  "excluir_dias": [],
  "categoria": "gastronomia",
  "subcategoria": "restaurante",
  "ids_sitios_candidatos": []
}
```

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `tipo` | `string` | `abierto_ahora`, `atiende_dia`, `abierto_en_hora`, `abierto_en_rango`, `abierto_24h`. |
| `dia_semana` | `1-7 \| actual \| null` | Dia ISO (1=lunes, 7=domingo). |
| `hora` | `HH:MM \| actual \| null` | Hora de consulta. |
| `rango_hora` | `object` | Rango `{inicio, fin}` en formato `HH:MM`. |
| `comparador` | `exacto \| antes_de \| despues_de` | Solo para `abierto_en_hora`. |
| `meridiano` | `AM \| PM \| null` | Ajuste 12h cuando el LLM lo envia. |
| `excluir_dias` | `int[] \| string[]` | Descarta sitios que atiendan esos dias. |
| `categoria` / `subcategoria` / `ids_sitios_candidatos` | — | Alcance comun. |

### Logica

1. Resuelve `dia_semana` (`actual` usa America/Guayaquil) y `hora` (con `meridiano` si aplica).
2. Aplica alcance sobre `turismo.sitio`.
3. Consulta `turismo.horario` y `turismo.horario_detalle`.
4. Filtra segun `tipo`:
   - `abierto_24h`: `horario.abierto_24h = true`
   - `atiende_dia`: tiene detalle activo ese dia o es 24h
   - `abierto_ahora`: dia y hora actuales dentro del rango del sitio
   - `abierto_en_hora`: la hora indicada cae en el horario del dia
   - `abierto_en_rango`: el horario del sitio se solapa con el rango pedido
5. Devuelve `ids_sitios`, `sitios` con detalle y `filtros_aplicados` para tarjetas dinamicas.

Tambien disponible dentro de `POST /api/v1/chatboot/ejecutar-plan` como paso secuencial.

---

## H6 · precio

**Herramienta del planificador:** filtra sitios por rango de precio general.

```http
POST /api/v1/chatboot/precio
```

### Request

```json
{
  "precio_numero": null,
  "operador": "min",
  "etiqueta": "economico",
  "excluir_etiquetas": ["alto"],
  "categoria": "gastronomia",
  "subcategoria": "restaurante",
  "ids_sitios_candidatos": []
}
```

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `precio_numero` | `number \| null` | Valor numerico si el usuario lo especifica. |
| `operador` | `min \| max \| exacto` | `min` (hasta ese precio), `max` (desde ese precio), `exacto` (dentro del rango). |
| `etiqueta` | `string \| null` | `economico`, `medio`, `alto`. |
| `excluir_etiquetas` | `string[]` | Descarta sitios con esas etiquetas en `rango_precio`. |
| `categoria` / `subcategoria` / `ids_sitios_candidatos` | — | Alcance comun. |

Debe indicarse `etiqueta` o `precio_numero` (con `operador`).

### Logica

1. Resuelve `etiqueta` contra el enum `turismo.etiqueta_precio_t`.
2. Aplica alcance sobre `turismo.sitio`.
3. Consulta `turismo.rango_precio` activo.
4. Filtra por etiqueta y/o precio:
   - Solo etiqueta: `etiqueta_precio` coincide.
   - `exacto`: `precio_min <= precio_numero <= precio_max`.
   - `min`: `precio_max <= precio_numero`.
   - `max`: `precio_min >= precio_numero`.
5. Excluye sitios que tengan alguna etiqueta en `excluir_etiquetas`.
6. Devuelve `filtros_aplicados`, `precio_min`, `precio_max` y `etiqueta_precio` por sitio para tarjetas dinamicas.

Tambien disponible dentro de `POST /api/v1/chatboot/ejecutar-plan` como paso secuencial.

**Resolucion unificada por sitio:** si el candidato tiene `tarifa_acceso` se usa esa tabla; si no, se usa `rango_precio`.

---

## H7 · tarifa_acceso

**Herramienta del planificador:** filtra por tarifa de entrada (museos, atracciones con condicion de descuento).

```http
POST /api/v1/chatboot/tarifa-acceso
```

### Request

```json
{
  "precio_numero": null,
  "operador": "min",
  "etiqueta": "economico",
  "condicion": "estudiante",
  "excluir_condiciones": [],
  "ids_sitios_candidatos": []
}
```

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `precio_numero` | `number \| null` | Valor numerico indicado por el usuario. |
| `operador` | `min \| max \| exacto` | Comparacion sobre el monto. |
| `etiqueta` | `string \| null` | Clasificacion calculada por monto (ver abajo). |
| `condicion` | `string \| null` | Filtro por condicion (`estudiante`, `ninos`, `adultos`, etc.). |
| `excluir_condiciones` | `string[]` | Descarta sitios con tarifas que coincidan. |
| `categoria` / `subcategoria` / `ids_sitios_candidatos` | — | Alcance comun. |

### Etiquetas calculadas (no vienen de BD)

| Etiqueta | Regla |
|----------|-------|
| `economico` | precio <= $1 |
| `medio` | $1 < precio <= $5 |
| `alto` | precio > $5 |

### Logica

1. Por cada sitio: usa `tarifa_acceso` si existe; si no, `rango_precio` (con `precio_min` como referencia).
2. Filtra por `condicion` con similitud trigramas cuando se indica.
3. Aplica `etiqueta` y/o `precio_numero` con `operador`.
4. Devuelve `fuente_precio`, `precio`, `condicion` y `etiqueta_precio` en tarjetas dinamicas.

Tambien disponible dentro de `POST /api/v1/chatboot/ejecutar-plan`.

---

## H8 · ruta

**Herramienta del planificador:** filtra rutas turisticas por tipo de actividad.

```http
POST /api/v1/chatboot/ruta
```

### Request

```json
{
  "tipo_ruta": "ciclismo",
  "excluir_tipos": ["senderismo"],
  "ids_rutas_candidatos": []
}
```

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `tipo_ruta` | `string` | `senderismo`, `ciclismo`, `caminata_urbana`, `montanismo`, `otro`. |
| `excluir_tipos` | `string[]` | Tipos de ruta a excluir del resultado. |
| `ids_rutas_candidatos` | `int[]` | IDs de rutas previas para acotar el filtro. |

### Mapeo a BD (`gis.tipo_ruta_t`)

| LLM | Enum BD |
|-----|---------|
| `senderismo` | `Senderismo` |
| `ciclismo` | `Ciclismo` |
| `caminata_urbana` | `Caminata Urbana` |
| `montanismo` | `Montañismo` |
| `otro` | `Otras` |

### Response

Devuelve `ids_rutas` y `rutas` con `id_ruta`, `titulo`, `tipo_ruta`.

En `ejecutar-plan` las rutas van en `tarjetas_rutas` (max. 5 aleatorias si hay mas resultados).

---

## H9 · gis

**Herramienta del planificador:** resuelve consultas geoespaciales de cercania.

```http
POST /api/v1/chatboot/gis
```

### Request

```json
{
  "usar_ubicacion_usuario": false,
  "distancia": 500,
  "unidad": "m",
  "punto_referencia": "Parque Maldonado",
  "excluir_zonas": [],
  "categoria": "gastronomia",
  "subcategoria": "restaurante",
  "ids_sitios_candidatos": []
}
```

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `usar_ubicacion_usuario` | `boolean` | Prioriza la ubicacion del usuario si se envia. |
| `distancia` | `number \| null` | Radio de busqueda. Si se omite, la API expande automaticamente 500 m -> 1 km -> 1.5 km. |
| `unidad` | `m \| km \| null` | Unidad de distancia. |
| `punto_referencia` | `string \| null` | Lugar de referencia (ej. "Parque Maldonado"). |
| `excluir_zonas` | `string[]` | Zonas o terminos a excluir de los resultados. |
| `categoria` / `subcategoria` / `ids_sitios_candidatos` | — | Alcance comun. |

### Logica

1. Resuelve el punto de origen en este orden:
   - Si `usar_ubicacion_usuario=true` y se envian coordenadas, usa esas.
   - Si hay `punto_referencia`, busca en `turismo.sitio` por trigramas.
   - Si no esta en la BD, consulta a la API publica de Nominatim (OpenStreetMap).
   - Si nada resuelve, devuelve error.
2. Aplica alcance sobre `turismo.sitio`. **GIS rechaza alcance `todos`**: requiere `ids_sitios_candidatos` o `categoria`/`subcategoria` en el request.
3. Busca con `ST_DWithin` en radios progresivos cuando `distancia` es `null`: 500 m, luego 1 km, maximo 1.5 km. Si el cliente envia `distancia` explicita, usa solo ese radio (tope 1.5 km).
4. Ordena por `ST_Distance` ascendente.
5. Excluye sitios cuyo nombre coincida con `excluir_zonas` (trigramas).
6. Devuelve `ids_sitios` y `sitios` con `distancia_metros`, `latitud` y `longitud`.
7. **Fallback mapa:** si no hay sitios cercanos pero existen `ids_sitios_candidatos` de un paso previo (p. ej. categoria), responde `ok: false`, `gis_fallback_mapa: true`, conserva esos IDs con coordenadas y mensaje: *"No encontré sitios cerca de ti... pero puedes observar estos sitios en el mapa."*
8. En `ejecutar-plan`, `gis_fallback_mapa_aplicado: true` cuando aplica ese fallback; las tarjetas incluyen `campos_dinamicos.gis_fallback_mapa`.

Tambien disponible dentro de `POST /api/v1/chatboot/ejecutar-plan` como paso secuencial. Si se usa en el plan, el payload principal debe incluir el campo `ubicacion_usuario: {"lat": float, "lon": float}` dentro de los parametros de la herramienta.

---

## `POST /api/v1/chatboot/busqueda-semantica` (H12)

Busca sitios turísticos basándose en la similitud semántica de una descripción proporcionada por el usuario contra los embeddings de los documentos de los sitios.
La herramienta combina similitud por embeddings (75%) con coincidencia de palabras clave por texto/trigramas (25%) y solo acepta resultados con score combinado mínimo de 70%.
Solo evalua sitios con documentos y chunks activos; los sitios sin documentos activos no participan en el calculo semantico.

### Request Body

```json
{
  "texto_embeddings": "un lugar tranquilo con mucha historia y arquitectura colonial",
  "posibles_match": ["historia", "arquitectura colonial", "patrimonio"],
  "excluir_terminos": ["ruido", "moderno"],
  "categoria": "atractivo",
  "subcategoria": "iglesia",
  "ids_sitios_candidatos": [1, 2, 3]
}
```

- **`texto_embeddings`**: (Obligatorio) El texto a convertir en embedding para la búsqueda.
- **`posibles_match`**: (Opcional) Palabras clave o frases cortas que deben reforzar la evidencia textual.
- **`excluir_terminos`**: (Opcional) Lista de palabras que, si están presentes en el texto del documento (`contenido`), excluirán ese documento de los resultados.
- **`categoria`**, **`subcategoria`**, **`ids_sitios_candidatos`**: (Opcionales) Filtros de alcance estándar.

### Response Body

```json
{
  "ok": true,
  "total": 5,
  "ids_sitios": [10, 15, 22, 5, 8],
  "sitios": [
    {
      "id_sitio": 10,
      "nombre": "Catedral de Riobamba",
      "score_similitud": 0.8543,
      "score_embedding": 0.86,
      "score_palabras_clave": 0.83,
      "titulo_chunk": "Historia y arquitectura",
      "contenido_chunk": "Texto del chunk coincidente...",
      "palabras_clave_match": ["historia", "arquitectura colonial"]
    }
  ],
  "top_sitios_semantica": [
    {
      "id_sitio": 10,
      "nombre": "Catedral de Riobamba",
      "score_similitud": 0.8543,
      "score_embedding": 0.86,
      "score_palabras_clave": 0.83,
      "titulo_chunk": "Historia y arquitectura",
      "contenido_chunk": "Texto del chunk coincidente...",
      "palabras_clave_match": ["historia", "arquitectura colonial"],
      "supera_umbral": true,
      "similitud_porcentaje": 85.43,
      "motivo": "supera_umbral"
    }
  ],
  "filtros_aplicados": {
    "texto_embeddings": "un lugar tranquilo con mucha historia y arquitectura colonial",
    "posibles_match": ["historia", "arquitectura colonial", "patrimonio"],
    "peso_embedding": 0.75,
    "peso_palabras_clave": 0.25,
    "umbral_minimo": 0.7
  },
  "alcance_aplicado": "categoria",
  "categoria_resuelta": "atractivo",
  "subcategoria_resuelta": "iglesia",
  "ids_sitios_candidatos_aplicados": [],
  "excluir_terminos_aplicados": ["ruido", "moderno"],
  "posibles_match_aplicados": ["historia", "arquitectura colonial", "patrimonio"],
  "umbral_minimo": 0.7,
  "tiempo_ms": 450.2,
  "mensaje": "Se encontraron 5 sitio(s) relevantes por busqueda semantica."
}
```

Tambien disponible dentro de `POST /api/v1/chatboot/ejecutar-plan` como paso secuencial. Puede devolver hasta 25 candidatos validos para alimentar `sitios_relacionados[]`; la respuesta final del plan sigue mostrando maximo 5 tarjetas.
`top_sitios_semantica` incluye candidatos por encima y por debajo del umbral para depuracion; `sitios` conserva solo los que superan el 70%.

---

## Ejecutar plan

Orquesta una o varias herramientas y devuelve tarjetas listas para la app.

```http
POST /api/v1/chatboot/ejecutar-plan
```

### Request

```json
{
  "tipo_ejecucion": "secuencial",
  "client_mensaje_id": "msg-123",
  "herramientas": [
    {
      "herramienta": "categoria_subcategoria",
      "grupo": "museo_arqueologia",
      "orden": 1,
      "parametros": {
        "categoria": "Manifestaciones Culturales",
        "subcategoria": "Museo",
        "excluir_categorias": []
      }
    },
    {
      "herramienta": "busqueda_semantica",
      "grupo": "museo_arqueologia",
      "orden": 2,
      "parametros": {
        "texto_embeddings": "museo con exhibicion de restos arqueologicos y patrimonio historico",
        "posibles_match": ["restos arqueologicos", "arqueologia", "exhibicion arqueologica"],
        "excluir_terminos": []
      }
    }
  ]
}
```

### Semantica de ejecucion

- `secuencial`: ejecuta las herramientas por `orden`; cada paso filtra los IDs del paso anterior. El campo `grupo` se ignora; toda la lista es una sola cadena.
- `paralelo`: agrupa por `grupo`; cada grupo se ejecuta secuencialmente y la API **une** los IDs finales de cada grupo (no interseccion).
- Si una herramienta no trae `grupo` en modo paralelo, se trata como una rama independiente.
- Si `busqueda_semantica` se ejecuta despues de filtros previos **en la misma rama** y no encuentra coincidencias sobre el 70%, no descarta esos filtros previos; conserva los IDs anteriores y marca `semantic_fallback_aplicado: true` para esa rama.
- Si `busqueda_semantica` es el primer paso de una rama y no encuentra coincidencias, esa rama queda sin resultados; en modo paralelo las demas ramas siguen aportando IDs.
- Si un paso H3–H7 (`precio`, `tarifa_acceso`, `horario`, `contactos`, `campos_parametrizados`) llega **sin criterio de filtrado** pero la rama ya tiene `ids_sitios_candidatos` previos, ese paso se omite (no-op), se conservan los IDs y `filtro_passthrough_aplicado: true`. El precio y contacto de los sitios siguen apareciendo en las tarjetas sin necesitar H6/H7.
- **GIS** siempre requiere alcance previo en la misma rama (`ids_sitios_candidatos` o `categoria`/`subcategoria`). Si GIS llega sin alcance, `ejecutar-plan` omite la búsqueda global y marca `gis_alcance_passthrough_aplicado: true`. La API `/gis` devuelve error si el alcance sería `todos`.
- Un filtro H3–H7 **válido** que no encuentra coincidencias deja 0 resultados **solo si nunca hubo candidatos previos** en la rama. Si ya había alcance, aplica **recomendación cálida** (`recomendacion_fallback_aplicado: true`): restaura los IDs anteriores y muestra un mensaje en `recomendacion_turistica`.
- `semantic_fallback_aplicado` en la respuesta es `true` si **alguna** rama aplico fallback semantico.

### Patron de actividades (doble via)

Cuando el planificador detecta una **actividad o experiencia** (acampar, trekking, pesca, etc.) y existe subcategoria de catalogo relacionada, el plan usa `tipo_ejecucion: "paralelo"` con dos grupos:

1. `grupo_catalogo`: filtra por subcategoria inferible (p. ej. `Campamento Turistico`).
2. `grupo_actividad`: `busqueda_semantica` sola en `orden: 1`, sin categoria previa, buscando la actividad en chunks de todos los sitios activos.

Ejemplo: "acampar con mi familia" puede devolver campamentos turisticos (rama catalogo) y atractivos naturales como Volcan El Altar (`Montana`) que mencionan camping en sus documentos (rama actividad).

Si la actividad no tiene subcategoria de catalogo, el plan usa `busqueda_semantica` secuencial sola.

### Response

```json
{
  "ok": true,
  "client_mensaje_id": "msg-123",
  "tarjetas": [],
  "tarjetas_rutas": [],
  "sitios_relacionados": [1, 2, 3],
  "candidatos_semanticos": [],
  "semantic_fallback_aplicado": false,
  "filtro_passthrough_aplicado": false,
  "gis_alcance_passthrough_aplicado": false,
  "retroalimentacion_semantica_gis": null,
  "recomendacion_fallback_aplicado": false,
  "recomendacion_turistica": null,
  "sugerencias_exploracion": [],
  "tiempo_ms": 120.5,
  "mensaje": "Plan ejecutado. Se encontraron 3 sitio(s)."
}
```

- `tarjetas`: maximo 5 tarjetas construidas con campos base.
- `sitios_relacionados`: hasta 25 IDs finales que cumplieron el plan antes de limitar las tarjetas visibles.
- `candidatos_semanticos`: candidatos de H12 con scores y chunk para depuracion, incluidos los descartados por umbral.
- `semantic_fallback_aplicado`: `true` cuando alguna rama tuvo semantica posterior sin coincidencias y se conservaron filtros previos de esa rama.
- `filtro_passthrough_aplicado`: `true` cuando alguna rama omitio un paso H3–H7 sin criterio y conservo los IDs previos. Las tarjetas pueden incluir `campos_dinamicos.filtro_passthrough` con el nombre del paso omitido.
- `gis_alcance_passthrough_aplicado`: `true` cuando alguna rama omitio GIS por falta de alcance previo. Las tarjetas pueden incluir `campos_dinamicos.gis_alcance_passthrough`.
- `retroalimentacion_semantica_gis`: mensaje amigable cuando en una rama coinciden `semantica_sin_coincidencias` y `gis_fallback_mapa` (semántica no refinó y GIS no encontró cercanos, pero se muestran candidatos del catálogo). También va en `campos_dinamicos.retroalimentacion_turistica` por tarjeta y en `mensaje`.
- `recomendacion_fallback_aplicado`: `true` cuando un filtro restrictivo (H3–H7 o `busqueda_aproximada` con criterio) dejó 0 resultados pero había candidatos previos; la API restaura esos IDs y muestra alternativas. Mensaje en `recomendacion_turistica` y `campos_dinamicos.recomendacion_fallback`.
- `recomendacion_turistica`: globo amigable para el turista cuando aplica recomendación cálida (p. ej. precio económico sin coincidencias, pero hay hoteles de otro rango).
- `sugerencias_exploracion`: categorías sugeridas cuando nunca hubo alcance previo en la rama (fallback en frío); el chatboot las envía como `opciones` en un globo, sin tarjetas.
- `tarjetas_rutas`: maximo 5 rutas cuando se usa la herramienta `ruta`.

---

## Archivos del modulo

| Archivo | Rol |
|---------|-----|
| [`apis/esquemas/chatboot.py`](../esquemas/chatboot.py) | Contratos Pydantic |
| [`apis/servicios/chatboot.py`](../servicios/chatboot.py) | Logica de negocio |
| [`apis/rutas/chatboot.py`](../rutas/chatboot.py) | Rutas FastAPI |
