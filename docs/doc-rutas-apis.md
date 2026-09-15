# Documentación de APIs de Rutas

Este documento describe cómo consumir los endpoints de **Rutas de Buses** y **Rutas Turísticas** expuestos por el backend FastAPI del proyecto RiobambaGo. Incluye URL base, métodos, parámetros, cuerpo de petición, respuestas y ejemplos de impresión en consola (cURL y Python).

> **Base URL local por defecto:** `http://localhost:8000/api/v1`
> Los prefijos mostrados parten de esa base. Ajustar según despliegue.

---

## Índice

1. [Rutas de Buses (`/rutas-buses`)](#1-rutas-de-buses-rutas-buses)
2. [Rutas Turísticas (`/admin/rutas-turisticas`)](#2-rutas-turísticas-adminrutas-turisticas)
3. [Ejemplos de impresión / consumo](#3-ejemplos-de-impresión--consumo)

---

## 1. Rutas de Buses (`/rutas-buses`)

Prefijo: `/rutas-buses` — Tag OpenAPI: `Rutas de Buses`.

Estos endpoints son **públicos** (no requieren autenticación) y exponen la cartografía de líneas de buses municipales a partir de la tabla `gis.ruta_bus`.

### 1.1 `GET /rutas-buses/`

Lista rutas de buses con filtros opcionales.

- **Query params (todos opcionales):**
  - `estado` *(str)*: filtro parcial (`ILIKE %valor%`) por la columna `estado`.
  - `linea_bus` *(str)*: filtro parcial (`ILIKE %valor%`) por la columna `linea_bus`.
- **Respuesta `200`:** `list[RutaBusSalida]`

#### Modelo `RutaBusSalida`

| Campo | Tipo | Descripción |
|---|---|---|
| `id_ruta` | int | Identificador de la ruta. |
| `nombre` | str \| null | Nombre descriptivo. |
| `estado` | str \| null | Estado de la ruta (texto libre en BD). |
| `distancia_recorrido` | str \| null | Distancia (almacenada como texto). |
| `linea_bus` | str \| null | Línea a la que pertenece la ruta. |
| `color` | str | Color HEX generado determinísticamente a partir de `linea_bus` o `nombre` (paleta de 18 colores, hash djb2). |
| `geometry` | object \| null | GeoJSON (`type` + `coordinates`) producido por `ST_AsGeoJSON(geom)`. El `type` esperado es `MultiLineString`. |

#### Ejemplo de cuerpo de respuesta

```json
[
  {
    "id_ruta": 1,
    "nombre": "Ruta Norte Centro",
    "estado": "Activo",
    "distancia_recorrido": "12.4 km",
    "linea_bus": "L1",
    "color": "#1E88E5",
    "geometry": {
      "type": "MultiLineString",
      "coordinates": [
        [[-78.6345, -1.6635], [-78.6320, -1.6610]],
        [[-78.6320, -1.6610], [-78.6290, -1.6580]]
      ]
    }
  }
]
```

---

### 1.2 `GET /rutas-buses/{id_ruta}`

Obtiene una ruta específica por ID.

- **Path param:** `id_ruta` *(int, requerido)*.
- **Respuestas:**
  - `200` → `RutaBusSalida`
  - `404` → `{"detail": "Ruta de bus no encontrada"}`

---

### 1.3 `GET /rutas-buses/leyenda`

Devuelve la leyenda agrupada por `linea_bus` y `nombre`, con el color asociado y la cantidad de rutas por combinación.

- **Respuesta `200`:** `list[LeyendaRutaBusSalida]`

#### Modelo `LeyendaRutaBusSalida`

| Campo | Tipo | Descripción |
|---|---|---|
| `linea_bus` | str | Línea de bus. |
| `color` | str | Color HEX (mismo algoritmo que en la lista). |
| `cantidad_rutas` | int | Rutas agrupadas bajo ese `linea_bus` + `nombre`. |

> **Nota:** el agrupamiento es por `(linea_bus, nombre)`, por lo que una misma línea puede aparecer varias veces si tiene varios nombres registrados.

#### Ejemplo

```json
[
  { "linea_bus": "L1", "color": "#1E88E5", "cantidad_rutas": 1 },
  { "linea_bus": "L2", "color": "#43A047", "cantidad_rutas": 1 }
]
```

---

## 2. Rutas Turísticas (`/admin/rutas-turisticas`)

Prefijo: `/admin/rutas-turisticas` — Tag OpenAPI: `Rutas turisticas admin`.

Estos endpoints están **protegidos** por:

- `Depends(requerir_usuario_panel)`
- `Depends(requerir_permiso("routes"))`

Es decir, requieren un usuario autenticado del panel administrativo con el permiso `routes`. Los detalles de autenticación dependen del módulo `core.dependencias` y de `main.py` (no se modifican en este documento).

### 2.1 `GET /admin/rutas-turisticas`

Lista paginada de rutas turísticas con filtros.

- **Query params:**
  - `q` *(str, opcional)*: búsqueda parcial (`ILIKE`) por `titulo`.
  - `tipo_ruta` *(Literal, opcional)*: `Senderismo | Ciclismo | Caminata Urbana | Montañismo | Otras`.
  - `estado` *(Literal, default `"all"`)*: `activo | inactivo | all`.
  - `page` *(int, default `1`, `>= 1`)*.
  - `page_size` *(int, default `10`, `1..100`)*.
- **Respuesta `200`:** `RutasListResponse`.

#### Modelo `RutasListResponse`

```json
{
  "page": 1,
  "page_size": 10,
  "total": 42,
  "items": [
    {
      "id_ruta": 7,
      "tipo_ruta": "Senderismo",
      "titulo": "Ruta del Volcán",
      "url_imagen": "/api/v1/imagenes/rutas/ruta-del-volcan/abc123.jpg",
      "descripcion": "Recorrido de 8 km por...",
      "activo": true,
      "total_puntos": 5,
      "tiene_linea": true
    }
  ]
}
```

---

### 2.2 `POST /admin/rutas-turisticas`

Crea una nueva ruta turística.

- **Body (`RutaCreate`):**

| Campo | Tipo | Requerido | Notas |
|---|---|---|---|
| `tipo_ruta` | Literal | sí | Valores: `Senderismo`, `Ciclismo`, `Caminata Urbana`, `Montañismo`, `Otras`. |
| `titulo` | str | sí | 2..150 caracteres. |
| `url_imagen` | str \| null | no | URL previamente subida vía `POST /imagen`. |
| `descripcion` | str \| null | no | |
| `activo` | bool | no, default `true` | |
| `linea` | list[Coordenada] \| null | no | Cada `Coordenada` = `{latitud, longitud}`. Se convierte a `LINESTRING` WKT (SRID 4326). |
| `puntos` | list[RutaPuntoCreate] | no, default `[]` | Ver modelo abajo. |
| `documentos` | list[str] | no, default `[]` | Rutas/URLs de documentos asociados. |

#### Modelo `RutaPuntoCreate`

```json
{
  "orden": 1,
  "id_sitio": 12,                 // opcional (>=1)
  "punto_inicio": { "latitud": -1.66, "longitud": -78.63 }, // opcional
  "punto_fin":    { "latitud": -1.66, "longitud": -78.63 }  // opcional
}
```

> **Validación:** cada punto debe contener al menos `id_sitio`, `punto_inicio` o `punto_fin`.

- **Respuesta `201`:** `RutaResponse` (mismo modelo que los `items` del listado).
- **Efectos colaterales:** registra evento en `core.trazabilidad` y regenera el chunk de descripción para el chatbot (`servicios.chunks_descripcion`).

#### Ejemplo de petición

```json
POST /api/v1/admin/rutas-turisticas
Content-Type: application/json

{
  "tipo_ruta": "Senderismo",
  "titulo": "Ruta del Volcán",
  "descripcion": "Recorrido circular de 8 km",
  "activo": true,
  "linea": [
    { "latitud": -1.6635, "longitud": -78.6345 },
    { "latitud": -1.6610, "longitud": -78.6320 }
  ],
  "puntos": [
    { "orden": 1, "id_sitio": 12 },
    { "orden": 2, "punto_fin": { "latitud": -1.6580, "longitud": -78.6290 } }
  ],
  "documentos": []
}
```

---

### 2.3 `POST /admin/rutas-turisticas/imagen`

Sube una imagen para una ruta y devuelve su URL pública.

- **Content-Type:** `multipart/form-data`
- **Campos:**
  - `titulo_ruta` *(str, requerido)*: se usa para generar un slug de carpeta.
  - `archivo` *(file, requerido)*: imagen (`image/*`). Extensiones permitidas: `.jpg`, `.jpeg`, `.png`, `.webp`; si no tiene extensión válida, se guarda como `.jpg`.
- **Respuesta `201`:** `ImagenRutaResponse`

```json
{
  "url": "/api/v1/imagenes/rutas/ruta-del-volcan/65f3a1b2c8d4e0f1a2b3c4d5.jpg",
  "nombre_archivo": "65f3a1b2c8d4e0f1a2b3c4d5.jpg"
}
```

> La URL devuelta se almacena luego en el campo `url_imagen` al crear/actualizar la ruta.

---

### 2.4 `GET /admin/rutas-turisticas/sitios`

Busca sitios turísticos disponibles para asociar a una ruta.

- **Query params:**
  - `q` *(str, opcional)*: filtro por nombre (`ILIKE`).
  - `limit` *(int, default `20`, `1..50`)*.
- **Respuesta `200`:** `list[SitioRutaResponse]`

#### Modelo `SitioRutaResponse`

| Campo | Tipo | Descripción |
|---|---|---|
| `id_sitio` | int | |
| `nombre` | str | |
| `categoria` | str \| null | |
| `subcategoria` | str \| null | |
| `latitud` | float | Extraída con `ST_Y`. |
| `longitud` | float | Extraída con `ST_X`. |

---

### 2.5 `GET /admin/rutas-turisticas/{id_ruta}/geometria`

Devuelve la geometría completa (línea + puntos) de una ruta.

- **Path param:** `id_ruta` *(int)*.
- **Respuesta `200`:** `RutaGeometriaResponse`
- **Errores:** `404` si la ruta no existe.

```json
{
  "id_ruta": 7,
  "titulo": "Ruta del Volcán",
  "linea": [
    { "longitud": -78.6345, "latitud": -1.6635 },
    { "longitud": -78.6320, "latitud": -1.6610 }
  ],
  "puntos": [
    {
      "orden": 1,
      "id_sitio": 12,
      "nombre_sitio": "Mirador Norte",
      "tipo": "sitio",
      "latitud": -1.6635,
      "longitud": -78.6345
    }
  ]
}
```

> El campo `tipo` se calcula en backend: `fin`, `inicio` (si `orden=1` y tiene `punto_inicio`), `sitio` (si tiene `id_sitio`), o `libre`.

> **Persistencia de vértices:** los vértices no tienen una tabla propia ni un
> identificador persistido. Son las coordenadas ordenadas del campo `linea`,
> reconstruidas desde `gis.rutas_turistica.geom_linea` (`LINESTRING`, SRID
> 4326). El panel crea IDs temporales en memoria para editar sin perder la
> relación entre marcadores y vértices, pero esos IDs no viajan a la API.

---

### 2.6 `PUT /admin/rutas-turisticas/{id_ruta}/geometria`

Reemplaza la línea y los puntos de una ruta (borrado + reinserción de `gis.ruta_puntos`).

`linea` es la fuente persistente de los vértices de forma de la ruta: cada
coordenada enviada pasa a formar parte del `LINESTRING` guardado en
`gis.rutas_turistica.geom_linea`. `puntos` no guarda todos los vértices; solo
guarda los puntos de control ordenados sobre esa línea: origen, destino, puntos
libres conectados y sitios intermedios.

- **Body (`RutaGeometriaUpdate`):**

```json
{
  "linea": [
    { "latitud": -1.6635, "longitud": -78.6345 },
    { "latitud": -1.6610, "longitud": -78.6320 }
  ],
  "puntos": [
    { "orden": 1, "tipo": "inicio", "latitud": -1.6635, "longitud": -78.6345 },
    { "orden": 2, "tipo": "fin",    "latitud": -1.6580, "longitud": -78.6290 },
    { "orden": 3, "tipo": "sitio",  "id_sitio": 12 }
  ]
}
```

- **Validaciones:**
  - `linea` representa una sola polilínea continua, con al menos dos vértices
    distintos y sin vértices consecutivos repetidos.
  - Debe existir exactamente un `inicio` como primer punto y un `fin` como
    último punto; sus órdenes deben ser consecutivos.
  - Los puntos `sitio` requieren `id_sitio`, deben ser paradas intermedias y
    usan la ubicación oficial del sitio activo.
  - Tipos `inicio`, `fin` y `libre` requieren `latitud` + `longitud`; cada
    punto de control debe coincidir con un vértice de `linea`.
  - El backend valida todo antes de borrar/reinsertar puntos, y realiza rollback
    si falla el guardado de la línea o de algún punto.
- **Respuesta `200`:** `RutaGeometriaResponse` (geometría actualizada).
- **Efectos colaterales:** registra evento `UPDATE` con actor (`obtener_actor`).

---

### 2.7 `PATCH /admin/rutas-turisticas/{id_ruta}`

Actualización parcial de los campos escalares y/o de las relaciones (`linea`, `puntos`, `documentos`) de una ruta.

- **Body (`RutaUpdate`):** todos los campos opcionales. Si se envía `puntos` o `documentos`, se reemplazan.

| Campo | Tipo |
|---|---|
| `tipo_ruta` | Literal \| null |
| `titulo` | str \| null (2..150) |
| `url_imagen` | str \| null |
| `descripcion` | str \| null |
| `activo` | bool \| null |
| `linea` | list[Coordenada] \| null |
| `puntos` | list[RutaPuntoCreate] \| null |
| `documentos` | list[str] \| null |

- **Respuesta `200`:** `RutaResponse`.
- **Errores:** `404` si la ruta no existe.
- **Efectos colaterales:** si se actualiza `descripcion`, regenera el chunk del chatbot; si se reemplaza `url_imagen` y la anterior era local, elimina el archivo del disco.

---

### 2.8 `PATCH /admin/rutas-turisticas/{id_ruta}/estado`

Cambia únicamente el estado activo/inactivo de la ruta.

- **Body (`EstadoRutaUpdate`):**

```json
{ "activo": false }
```

- **Respuesta `200`:** `RutaResponse`.
- **Errores:** `404` si la ruta no existe.

---

### 2.9 `DELETE /admin/rutas-turisticas/{id_ruta}`

Elimina la ruta y sus dependencias.

- **Respuesta `200`:** `RutaResponse` con `activo=false`, `total_puntos=0`, `tiene_linea=false` y `url_imagen=null` (representa el snapshot tras borrado).
- **Errores:** `404` si la ruta no existe.
- **Efectos colaterales:**
  - Borra la fila en `gis.rutas_turistica` (cascade manual sobre `gis.ruta_puntos`).
  - Elimina repositorios asociados vía `eliminar_repositorios_de_vinculo`.
  - Borra el archivo de imagen local si existía.
  - Registra evento `DELETE` con snapshot anterior.

---

## 3. Ejemplos de impresión / consumo

A continuación se muestran ejemplos de cómo **realizar la petición** y **cómo imprimir la respuesta** por consola, tanto con `cURL` como con Python (`requests`).

### 3.1 Rutas de Buses

#### Listar todas las rutas de buses — `cURL`

```bash
curl -X GET "http://localhost:8000/api/v1/rutas-buses/" \
  -H "Accept: application/json"
```

Salida formateada (ejemplo, los IDs y geometrías pueden variar):

```text
[
  {
    "id_ruta": 1,
    "nombre": "Ruta Norte Centro",
    "estado": "Activo",
    "distancia_recorrido": "12.4 km",
    "linea_bus": "L1",
    "color": "#1E88E5",
    "geometry": {
      "type": "MultiLineString",
      "coordinates": [
        [[-78.6345, -1.6635], [-78.6320, -1.6610]]
      ]
    }
  }
]
```

#### Listar con filtro por línea — `cURL`

```bash
curl -X GET "http://localhost:8000/api/v1/rutas-buses/?linea_bus=L1" \
  -H "Accept: application/json"
```

#### Imprimir en consola con Python (`requests`)

```python
import json
import requests

BASE = "http://localhost:8000/api/v1"

# 1) Listar rutas de buses
resp = requests.get(f"{BASE}/rutas-buses/", timeout=10)
resp.raise_for_status()
rutas = resp.json()

print(f"Total de rutas: {len(rutas)}")
for ruta in rutas:
    coords_count = sum(len(line) for line in (ruta.get("geometry") or {}).get("coordinates", []))
    print(
        f"  - id={ruta['id_ruta']:<4} "
        f"linea={ruta.get('linea_bus')!s:<5} "
        f"estado={ruta.get('estado')!s:<10} "
        f"color={ruta.get('color')} "
        f"tramos={coords_count}"
    )

# 2) Obtener una ruta por ID
ruta_id = rutas[0]["id_ruta"] if rutas else 1
detalle = requests.get(f"{BASE}/rutas-buses/{ruta_id}", timeout=10).json()
print("\nDetalle de la ruta:")
print(json.dumps(detalle, indent=2, ensure_ascii=False))

# 3) Leyenda
leyenda = requests.get(f"{BASE}/rutas-buses/leyenda", timeout=10).json()
print("\nLeyenda:")
for item in leyenda:
    print(f"  {item['linea_bus']:<5}  {item['color']}  ({item['cantidad_rutas']} ruta/s)")
```

Salida esperada (ejemplo):

```text
Total de rutas: 3
  - id=1    linea=L1    estado=Activo     color=#1E88E5 tramos=2
  - id=2    linea=L1    estado=Activo     color=#1E88E5 tramos=1
  - id=3    linea=L2    estado=Inactivo   color=#43A047 tramos=3

Detalle de la ruta:
{
  "id_ruta": 1,
  "nombre": "Ruta Norte Centro",
  "estado": "Activo",
  "distancia_recorrido": "12.4 km",
  "linea_bus": "L1",
  "color": "#1E88E5",
  "geometry": { "type": "MultiLineString", "coordinates": [...] }
}

Leyenda:
  L1    #1E88E5  (1 ruta/s)
  L2    #43A047  (1 ruta/s)
```

---

### 3.2 Rutas Turísticas (requieren autenticación del panel)

> Los siguientes ejemplos asumen un endpoint de login que devuelve un token JWT. Ajustar el header `Authorization` al esquema real (`Bearer ...`).

#### Listar paginado — `cURL`

```bash
curl -X GET "http://localhost:8000/api/v1/admin/rutas-turisticas?page=1&page_size=10&estado=activo" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer <TOKEN>"
```

#### Crear una ruta — `cURL`

```bash
curl -X POST "http://localhost:8000/api/v1/admin/rutas-turisticas" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "tipo_ruta": "Senderismo",
    "titulo": "Ruta del Volcán",
    "descripcion": "Recorrido circular de 8 km",
    "activo": true,
    "linea": [
      { "latitud": -1.6635, "longitud": -78.6345 },
      { "latitud": -1.6610, "longitud": -78.6320 }
    ],
    "puntos": [
      { "orden": 1, "id_sitio": 12 }
    ]
  }'
```

#### Subir imagen — `cURL`

```bash
curl -X POST "http://localhost:8000/api/v1/admin/rutas-turisticas/imagen" \
  -H "Authorization: Bearer <TOKEN>" \
  -F "titulo_ruta=Ruta del Volcán" \
  -F "archivo=@/ruta/local/imagen.jpg"
```

Respuesta:

```json
{
  "url": "/api/v1/imagenes/rutas/ruta-del-volcan/65f3a1b2c8d4e0f1a2b3c4d5.jpg",
  "nombre_archivo": "65f3a1b2c8d4e0f1a2b3c4d5.jpg"
}
```

Luego, esa URL se usa en `POST` o `PATCH` de la ruta en el campo `url_imagen`.

#### Actualizar geometría — `cURL`

```bash
curl -X PUT "http://localhost:8000/api/v1/admin/rutas-turisticas/7/geometria" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "linea": [
      { "latitud": -1.6635, "longitud": -78.6345 },
      { "latitud": -1.6610, "longitud": -78.6320 }
    ],
    "puntos": [
      { "orden": 1, "tipo": "inicio", "latitud": -1.6635, "longitud": -78.6345 },
      { "orden": 2, "tipo": "fin",    "latitud": -1.6580, "longitud": -78.6290 }
    ]
  }'
```

#### Cambiar estado — `cURL`

```bash
curl -X PATCH "http://localhost:8000/api/v1/admin/rutas-turisticas/7/estado" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{ "activo": false }'
```

#### Eliminar — `cURL`

```bash
curl -X DELETE "http://localhost:8000/api/v1/admin/rutas-turisticas/7" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer <TOKEN>"
```

#### Imprimir en consola con Python (`requests`)

```python
import json
import requests

BASE = "http://localhost:8000/api/v1"
TOKEN = "<TOKEN_JWT>"

session = requests.Session()
session.headers.update({
    "Accept": "application/json",
    "Authorization": f"Bearer {TOKEN}",
})

# 1) Listar rutas turísticas paginadas
params = {"page": 1, "page_size": 10, "estado": "activo"}
lista = session.get(f"{BASE}/admin/rutas-turisticas", params=params, timeout=10).json()
print(f"Total rutas activas: {lista['total']} | Página {lista['page']} de tamaño {lista['page_size']}")
for r in lista["items"]:
    print(
        f"  - [{r['id_ruta']}] {r['titulo']:<30} "
        f"tipo={r['tipo_ruta']:<15} "
        f"activo={r['activo']} "
        f"puntos={r['total_puntos']} "
        f"linea={r['tiene_linea']}"
    )

# 2) Obtener geometría completa
if lista["items"]:
    id_ruta = lista["items"][0]["id_ruta"]
    geom = session.get(f"{BASE}/admin/rutas-turisticas/{id_ruta}/geometria", timeout=10).json()
    print(f"\nGeometría de la ruta {geom['id_ruta']} - {geom['titulo']}:")
    print(json.dumps(geom, indent=2, ensure_ascii=False))

# 3) Crear una nueva ruta
nueva = {
    "tipo_ruta": "Senderismo",
    "titulo": "Ruta Demo",
    "descripcion": "Ruta creada desde la documentación",
    "activo": True,
    "linea": [
        {"latitud": -1.6635, "longitud": -78.6345},
        {"latitud": -1.6610, "longitud": -78.6320},
    ],
    "puntos": [{"orden": 1, "id_sitio": 12}],
    "documentos": [],
}
creada = session.post(f"{BASE}/admin/rutas-turisticas", json=nueva, timeout=10)
creada.raise_for_status()
print("\nRuta creada:")
print(json.dumps(creada.json(), indent=2, ensure_ascii=False))

# 4) Cambiar estado
id_nueva = creada.json()["id_ruta"]
cambio = session.patch(
    f"{BASE}/admin/rutas-turisticas/{id_nueva}/estado",
    json={"activo": False},
    timeout=10,
).json()
print(f"\nEstado actualizado: activo={cambio['activo']}")

# 5) Eliminar
elim = session.delete(f"{BASE}/admin/rutas-turisticas/{id_nueva}", timeout=10)
print(f"\nEliminación status code: {elim.status_code}")
print(json.dumps(elim.json(), indent=2, ensure_ascii=False))
```

---

## Resumen rápido de endpoints

### Rutas de Buses (públicas)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/rutas-buses/` | Lista rutas con filtros opcionales `estado`, `linea_bus`. |
| GET | `/rutas-buses/leyenda` | Leyenda agrupada por línea y nombre. |
| GET | `/rutas-buses/{id_ruta}` | Detalle de una ruta. |

### Rutas Turísticas (admin)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/admin/rutas-turisticas` | Listado paginado con filtros. |
| POST | `/admin/rutas-turisticas` | Crea una ruta. |
| POST | `/admin/rutas-turisticas/imagen` | Sube imagen asociada. |
| GET | `/admin/rutas-turisticas/sitios` | Busca sitios para asociar. |
| GET | `/admin/rutas-turisticas/{id_ruta}/geometria` | Devuelve línea + puntos. |
| PUT | `/admin/rutas-turisticas/{id_ruta}/geometria` | Reemplaza línea + puntos. |
| PATCH | `/admin/rutas-turisticas/{id_ruta}` | Actualización parcial. |
| PATCH | `/admin/rutas-turisticas/{id_ruta}/estado` | Cambia activo/inactivo. |
| DELETE | `/admin/rutas-turisticas/{id_ruta}` | Elimina la ruta y limpia dependencias. |
