# Plan de implementación: ejecutor modular de herramientas

## Resumen

Implementar el núcleo de ejecución del chatbot de exploración respetando los contratos actuales de `apis/docs/chatboot_arquitectura_api.md`. El nodo `ejecutar_plan_tools.py` debe quedar como orquestador: ejecuta consultas en paralelo, pasos de cada consulta en secuencia y delega la lógica concreta a un archivo Python por herramienta.

`pregunta_directa` quedó implementada posteriormente como herramienta modular con salida determinística `globo + accion`.

## Estructura propuesta

Crear el paquete:

```text
chatboot/application/nodes/chatboot_exploracion/herramientas/
```

Con estos módulos:

- `base.py`: tipos comunes, estructura estándar de estado, normalización de IDs, extracción de payloads y helpers para `ok` / `sin_resultados` / `error`.
- `cliente_http.py`: cliente HTTP asíncrono, `APIS_BASE_URL`, timeout y manejo uniforme de errores.
- `registry.py`: mapa de nombres del planificador hacia ejecutores de herramientas.
- `busqueda_referencia.py`
- `contacto_busqueda.py`
- `horario_consulta.py`
- `precio_consulta.py`
- `tarifa_acceso_consulta.py`
- `atributos_booleanos_consulta.py`
- `ruta_consulta.py`
- `gis_consulta.py`
- `busqueda_semantica_consulta.py`
- `conversacional.py`
- `fallback.py`

`ejecutar_plan_tools.py` no debe contener reglas específicas de una herramienta; solo normaliza el plan, llama al registry, propaga candidatos y arma el resultado final.

## Orquestación

- Conectar el flujo como `cargar_memoria -> crear_plan -> ejecutar_plan -> guardar_memoria`.
- Si `plan_valido` es falso, no ejecutar herramientas y conservar el fallback generado por `crear_plan`.
- Cada elemento de `plan["consultas"]` se ejecuta en paralelo con `asyncio.gather`.
- Dentro de cada consulta, ordenar `ejecucion_herramienta` por `orden` y ejecutar secuencialmente.
- Cada herramienta ejecutada debe devolver un estado con forma fija:

```python
{
    "herramienta": "nombre_herramienta",
    "orden": 1,
    "status": "ok" | "sin_resultados" | "error",
    "ids": [],
    "payload": {},
    "nota": "",
}
```

- Propagación de IDs:
  - Si una herramienta devuelve IDs, esos IDs pasan como `ids_consulta` a la siguiente.
  - Si falla la primera herramienta de una consulta, detener solo esa consulta y generar fallback para ella.
  - Si falla una herramienta intermedia, registrar `sin_resultados`, conservar los IDs previos y continuar.
  - Si falla la última herramienta, conservar los IDs previos como candidatos finales.
- Mantener en el contexto de ejecución el tipo de IDs actual: `sitio` o `ruta`.
- Nunca dejar el turno sin respuesta: siempre debe existir al menos un globo final.

## Contratos de herramientas

Todas las herramientas HTTP consumen `/api/v1/chatboot/herramientas` y agregan `ids_consulta` al payload.

| Nombre en plan | Módulo | Endpoint | IDs de salida |
|---|---|---|---|
| `busqueda_referencia` | `busqueda_referencia.py` | `/busqueda-referencia` | `ids_sitio` |
| `contactos` | `contacto_busqueda.py` | `/contacto-busqueda` | `ids_sitio` |
| `horario` | `horario_consulta.py` | `/horario-consulta` | `ids_sitio` |
| `precio` | `precio_consulta.py` | `/precio-consulta` | `ids_sitio` |
| `tarifa_acceso` | `tarifa_acceso_consulta.py` | `/tarifa-acceso-consulta` | `ids_sitio` |
| `atributos_booleanos` | `atributos_booleanos_consulta.py` | `/atributos-booleanos-consulta` | `ids_sitio` |
| `ruta` | `ruta_consulta.py` | `/ruta-consulta` | `ids_ruta` |
| `gis` | `gis_consulta.py` | `/gis-consulta` | `ids_sitio` o `ids_ruta` |
| `busqueda_semantica` | `busqueda_semantica_consulta.py` | `/busqueda-semantica-consulta` | `ids_sitio` |

Reglas por contrato:

- Las respuestas `ids_sitio` o `ids_ruta` son `ok`.
- Las respuestas `sin_sitios` o `sin_rutas` son `sin_resultados`.
- Las respuestas con `fallo`, errores HTTP o excepciones son `error`.
- `payload` guarda la respuesta cruda de la API o herramienta interna.
- `nota` debe incluir `retroalimentacion.mensaje` cuando exista.

## Casos especiales

### GIS

- GIS siempre va al final y requiere `ids_consulta` no vacío.
- Si GIS llega sin candidatos previos, no llamar a la API; registrar `sin_resultados` con nota de falta de alcance y generar fallback suave.
- Si el paso anterior produjo rutas, forzar `parametros["entidad"] = "ruta"` antes de llamar a la API.
- Si `usar_ubicacion_usuario` es `true`, inyectar `ubicacion_usuario` desde el estado.
- Normalizar ubicación del cliente:

```python
{"lat": valor, "lng": valor} -> {"lat": valor, "lon": valor}
```

- Usar `retroalimentacion.mensaje` y `candidatos[].distancia_aproximada` como contexto para el redactor.

### Búsqueda semántica

- La API ya resuelve el fallback global cuando no hay coincidencias en el filtro previo.
- El ejecutor debe propagar los `ids_sitio` finales que devuelva la API, aunque provengan del fallback global.
- Si `retroalimentacion.fallback_global_aplicado` es `true`, marcar el estado como `ok` con nota de fallback suave, no como error.
- Si la respuesta es `sin_sitios`, registrar `sin_resultados` y conservar candidatos previos si la herramienta no es la primera.

### Rutas

- `ruta_consulta` produce `ids_ruta`.
- El único siguiente paso válido con rutas en esta fase es GIS con `entidad="ruta"`.
- No construir cards de sitio para IDs de ruta hasta que exista contrato de salida visual para rutas.

### Conversacional

- Leer `chatboot/data/conversacional.json`.
- Usar el bloque `chatboot_exploracion`.
- Elegir aleatoriamente un mensaje según `parametros["tipo"]`.
- Empaquetar como globo y no llamar APIs.

### Fallback

- Empaquetar como globo.
- Si el payload incluye `subcategorias_sugeridas`, `opciones` o `pregunta_sugerida`, incluirlas en `mensajes_app` como:

```json
{ "opciones": [] }
```

### Pregunta directa

- Implementada posteriormente como herramienta HTTP `/api/v1/chatboot/herramientas/pregunta-directa`.
- Si resuelve un sitio, genera globo de delegación y acción `abrir_chatbot_sitio`; no construye cards ni usa redactor exploratorio.
- Si no resuelve con confianza suficiente, genera fallback suave solicitando el nombre exacto.

## Salida al chatbot

Extender `ExploracionState` con:

- `estados_herramientas: list[dict]`
- `ids_asociados: list[int]`
- `mensajes_app: list[MensajeApp]`
- `entidades_resueltas: list[str]`

`resultado_exploracion` debe incluir:

- `plan_valido`
- `plan`
- `errores_formato`
- `estados_herramientas`
- `ids_asociados`
- `mensajes_app`

Empaquetado final:

- Siempre generar un globo final redactado por LLM con los estados acumulados.
- Agregar hasta 5 cards solo para IDs de sitio.
- Si hay más de 5 sitios, seleccionar 5 aleatoriamente.
- Siempre incluir todos los IDs válidos de sitio en:

```json
{ "ids_asociados": [] }
```

Para cards, obtener datos desde `/api/v1/sitios/` y filtrar localmente por `id_sitio`.

Campos de card:

- `nombre_sitio`: `nombre`
- `categoria`: `categoria`
- `direccion`: si no viene en `/sitios/`, usar `""`

## LLM redactor

- Recibe todos los `estados_herramientas`, IDs finales, candidatos y notas.
- Produce un globo personalizado.
- Tono esperado:
  - Todo exitoso: mensaje directo con resultados.
  - Fallback semántico global o suave: indicar que no encontró algo tan específico, pero recomienda alternativas.
  - Sin resultados: mensaje empático con sugerencias si existen.
- Si el redactor falla, usar un globo determinístico de fallback construido desde los estados.

## Memoria

Actualizar `guardar_memoria.py` después de ejecutar el plan:

- Preservar el contrato actual de `MemoriaPlanificador`.
- Mantener turnos existentes.
- Actualizar `entidades` con nombres resueltos exitosamente.
- Guardar solo entidades de herramientas con `status == "ok"`.
- Evitar duplicados y conservar orden.
- Fuentes válidas:
  - Nombres de cards (`nombre_sitio`).
  - `candidatos[].nombre` cuando existan en respuestas de GIS o semántica.
  - Categorías/subcategorías resueltas desde parámetros solo si la herramienta devolvió resultados.

## Configuración HTTP

- `APIS_BASE_URL`: default `http://localhost`.
- `APIS_TIMEOUT_SECONDS`: default `15`.

## Pruebas

Unitarias:

- Registry resuelve todos los nombres del plan.
- Cada módulo de herramienta transforma respuesta `ids_*`, `sin_*` y `fallo` al estado estándar.
- `ejecutar_plan_tools.py` ejecuta consultas en paralelo y pasos en orden.
- Propagación de `ids_consulta` entre herramientas.
- Fallo en primera herramienta detiene solo esa consulta.
- Fallo intermedio conserva IDs previos y continúa.
- Fallo final conserva candidatos previos.
- GIS sin candidatos no llama API.
- `ruta -> gis` fuerza `entidad="ruta"` y propaga `ids_ruta`.
- GIS inyecta ubicación y normaliza `lng` a `lon`.
- Semántica con `fallback_global_aplicado=true` conserva `ids_sitio` y agrega nota.
- Conversacional y fallback no llaman HTTP.
- `guardar_memoria.py` conserva turnos y actualiza `entidades`.

Integración con `httpx.MockTransport`:

- `busqueda_semantica -> horario -> gis`
- `ruta -> gis`
- `busqueda_semantica -> gis`
- `busqueda_semantica` con fallback global.

Verificación manual:

- Ejecutar los checks existentes de `apis/tests/probar_apis_chatboot.py`:

```bash
cd apis
.venv/bin/python tests/probar_apis_chatboot.py --verificar-pipeline
.venv/bin/python tests/probar_apis_chatboot.py --verificar-pipeline-gis
.venv/bin/python tests/probar_apis_chatboot.py --verificar-pipeline-ruta-gis
.venv/bin/python tests/probar_apis_chatboot.py --verificar-pipeline-semantica
.venv/bin/python tests/probar_apis_chatboot.py --verificar-fallback-semantica
```

## Fuera de alcance

- No modificar la lógica de clasificación.
- No construir cards visuales para rutas hasta que exista contrato específico.
