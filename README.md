<div align="center">
<img src="panel_admin/public/assets/logo.png" alt="Logo de RioGo" width="150">

# RioGo
**Plataforma turística inteligente para Riobamba**  
Exploración de atractivos, rutas y servicios turísticos mediante una API geoespacial, un panel administrativo y un chatbot conectado en tiempo real.

<br>

<img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
<img src="https://img.shields.io/badge/React-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React">
<img src="https://img.shields.io/badge/PostgreSQL_%2B_PostGIS-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL y PostGIS">
<img src="https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis">
<img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
<img src="https://img.shields.io/badge/Nginx-009639?style=flat-square&logo=nginx&logoColor=white" alt="Nginx">

<br><br>

[Descripción](#-descripción) · [Componentes](#-componentes-principales) · [Arquitectura](#-arquitectura) · [Chatbot](#-flujo-del-chatbot) · [Stack Tecnológico](#-stack-tecnológico) · [Estructura](#-estructura-del-repositorio) · [Instalación](#-puesta-en-marcha) · [API](#-api-y-canales-de-comunicación) · [Pruebas](#-pruebas-y-documentación) · [GeoNode](#-geonode-y-geoserver)

</div>

---

## 🌋 Descripción

RioGo es una plataforma para consultar y administrar información turística de Riobamba. El repositorio reúne los servicios de backend, el orquestador conversacional, el panel web, la base de datos geoespacial y la infraestructura de despliegue.

La solución permite:

* Explorar sitios, noticias, rutas turísticas y recorridos de buses.
* Consultar información mediante un chatbot turístico con memoria de conversación.
* Recomendar lugares usando filtros, ubicación y búsqueda semántica.
* Gestionar atractivos, categorías, rutas, noticias, cuentas y permisos.
* Trabajar con geometrías, distancias y capas geográficas.
* Registrar sesiones, conversaciones y acciones administrativas.

> [!NOTE]
> La aplicación móvil consume estos servicios, pero su código fuente no forma parte de este repositorio.

---

## 🧩 Componentes principales

| Componente | Responsabilidad | Tecnologías |
| :--- | :--- | :--- |
| **`apis/`** | API REST, autenticación, reglas de negocio, GIS y búsqueda semántica | FastAPI, SQLAlchemy, Pydantic, Voyage AI |
| **`chatboot/`** | Planificación, ejecución de herramientas, evaluación y respuesta conversacional | FastAPI, WebSockets, LangGraph, DeepSeek, Redis |
| **`panel_admin/`** | Administración del contenido turístico y visualización de métricas | React, Vite, Tailwind CSS, MapLibre, TanStack Query |
| **`base_datos/`** | Persistencia relacional, geográfica y vectorial | PostgreSQL 16, PostGIS 3.5, pgvector, pg_trgm |
| **`ngix/`** | Terminación TLS y enrutamiento hacia los servicios | Nginx |
| **`geonode_gestor/`** | Gestión y publicación de información GIS en un despliegue independiente | GeoNode, GeoServer |
| **`fuente_datos/`** | Imágenes y documentos utilizados por la plataforma | Markdown, recursos multimedia |

---

## 🏗️ Arquitectura

```mermaid
flowchart TB
    mobile["Aplicación móvil"]
    operator["Administrador"]
    proxy["Nginx<br/>TLS y proxy inverso"]

    mobile --> proxy
    operator --> proxy

    subgraph services["Servicios de aplicación"]
        panel["Panel React"]
        api["API FastAPI"]
        bot["Chatbot FastAPI + LangGraph"]
    end

    proxy -->|"/admin y /account"| panel
    proxy -->|"/api/v1"| api
    proxy -->|"/ws"| bot
    panel --> api
    bot -->|"Herramientas HTTP"| api

    subgraph data["Datos y estado"]
        db["PostgreSQL<br/>PostGIS + pgvector"]
        apiCache["Redis API"]
        botMemory["Redis Chatbot"]
    end

    api <--> db
    api <--> apiCache
    bot <--> botMemory

    geo["GeoNode + GeoServer<br/>módulo independiente"]
    geo -.->|"Integración GIS opcional"| proxy
```

Los servicios principales comparten la red Docker `RiobambaGo`. La base de datos habilita las extensiones `postgis`, `vector`, `pg_trgm` y `pgcrypto`, y organiza la información en cuatro esquemas:

| Esquema | Contenido |
| :--- | :--- |
| **`turismo`** | Sitios, categorías, noticias, contenido, precios y multimedia |
| **`gis`** | Rutas turísticas, geometrías y recorridos de buses |
| **`conversacion`** | Usuarios, sesiones, mensajes, permisos e historial |
| **`trazabilidad`** | Acciones administrativas e inicios de sesión |

---

## 🤖 Flujo del chatbot

El contenedor `chatboot` recibe mensajes de la app mediante WebSocket. No responde únicamente con el modelo de lenguaje: primero construye un plan, consulta herramientas reales de la API y evalúa la evidencia antes de presentar una respuesta.

```mermaid
flowchart TB
    appIn["1. La app envía la consulta<br/>por WebSocket"]
    guard["2. Limpieza, validación<br/>y control de prompt injection"]
    memory["3. Recuperación del contexto<br/>desde Redis"]
    planner["4. El LLM genera<br/>un plan estructurado"]
    validate["5. Validación y sanitización<br/>del plan"]
    executor["6. Ejecución del plan"]
    tools["7. Herramientas consultan<br/>las APIs de RioGo"]
    sources["8. PostgreSQL, PostGIS,<br/>pgvector y contenido"]
    normalize["9. Resultados normalizados<br/>y candidatos consolidados"]
    evaluator["10. Evaluación y ranking<br/>por filtros y evidencias"]
    package["11. Redacción y empaquetado<br/>en globos, cards o multimedia"]
    persist["12. Memoria e historial<br/>actualizados"]
    appOut["13. Respuesta final<br/>enviada a la app"]
    fallback["Respuesta segura<br/>o fallback determinístico"]

    appIn --> guard --> memory --> planner --> validate
    validate -->|"Plan válido"| executor
    validate -->|"Plan inválido"| fallback
    executor --> tools --> sources --> tools
    tools --> normalize --> evaluator --> package --> persist --> appOut
    evaluator -->|"Sin coincidencias confiables"| fallback
    fallback --> persist
```

<details>
<summary><strong>Ver el detalle de cada fase</strong></summary>

1. **Entrada** — el WebSocket valida el cuerpo del mensaje, el usuario, la sesión y, cuando existe, la ubicación.
2. **Protección** — se limpia el texto, se detectan intentos de inyección y se añade contexto como palabras relevantes y fecha.
3. **Memoria** — Redis recupera el contexto reciente de la conversación.
4. **Planificación** — DeepSeek genera un JSON con las consultas y herramientas necesarias.
5. **Validación** — el plan se comprueba y sanitiza antes de permitir su ejecución.
6. **Ejecución** — las consultas independientes se procesan en paralelo; las herramientas de cada consulta se ejecutan en orden y refinan los IDs obtenidos.
7. **Recuperación** — las herramientas llaman por HTTP a `apis`, que consulta datos turísticos, espaciales y vectoriales.
8. **Evaluación** — se consolidan candidatos, distancias, coincidencias semánticas, precios, tarifas, horarios y atributos. El redactor selecciona hasta cinco IDs válidos; si el modelo falla, existe un ranking determinístico de respaldo.
9. **Salida** — se construyen bloques compatibles con la app (globo, card, multimedia o stream), se guarda el historial y se envía el evento final.

</details>

**Ejemplos de herramientas del plan**

| Tipo de consulta | Función |
| :--- | :--- |
| Búsqueda semántica | Encuentra sitios por intención y similitud vectorial |
| Categoría y subcategoría | Reduce candidatos por clasificación turística |
| GIS y ubicación | Calcula cercanía y filtra por radio o referencia espacial |
| Precio y tarifa | Contrasta costos del servicio o acceso |
| Horario | Verifica disponibilidad y condiciones de atención |
| Atributos | Filtra propiedades booleanas del sitio |
| Pregunta directa | Recupera información puntual de un sitio o documento |

---

## 🧰 Stack Tecnológico

<div align="center">

<img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/python/python-original.svg" width="42" height="42" alt="Python" title="Python">
&nbsp;
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/fastapi/fastapi-original.svg" width="42" height="42" alt="FastAPI" title="FastAPI">
&nbsp;
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/react/react-original.svg" width="42" height="42" alt="React" title="React">
&nbsp;
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/postgresql/postgresql-original.svg" width="42" height="42" alt="PostgreSQL y PostGIS" title="PostgreSQL y PostGIS">
&nbsp;
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/redis/redis-original.svg" width="42" height="42" alt="Redis" title="Redis">
&nbsp;
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/docker/docker-original.svg" width="42" height="42" alt="Docker" title="Docker">
&nbsp;
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/nginx/nginx-original.svg" width="42" height="42" alt="Nginx" title="Nginx">

</div>

---

## 📁 Estructura del repositorio

```
RioGo/
├── apis/               # API REST y lógica de negocio
│   ├── core/           # Autenticación, correo, embeddings e infraestructura
│   ├── rutas/          # Endpoints agrupados por dominio
│   ├── servicios/      # Casos de uso y acceso a datos
│   ├── esquemas/       # Contratos Pydantic
│   ├── docs/           # Documentación técnica de la API
│   └── tests/          # Pruebas automatizadas e integración
├── chatboot/            # Orquestador conversacional y WebSockets
│   ├── application/    # Flujos, nodos, planes y herramientas
│   ├── domain/         # Modelos del dominio conversacional
│   └── infrastructure/ # LLM, Redis, configuración y transporte
├── panel_admin/         # Aplicación administrativa React
├── base_datos/          # Imagen PostGIS, inicialización y migraciones
├── geonode_gestor/       # Despliegue GIS independiente
├── fuente_datos/         # Imágenes y documentos del sistema
├── ngix/                 # Proxy inverso y configuración TLS
├── docs/                 # Contratos de pruebas y rutas
└── docker-compose.yml    # Orquestación principal
```

---

## 🚀 Puesta en marcha

### Requisitos

* Docker Engine y Docker Compose v2.
* Puertos 80 y 443 disponibles.
* Credenciales de DeepSeek y Voyage AI.
* Cuenta SMTP si se utilizarán verificación y recuperación por correo.

<details>
<summary><strong>Ver instalación paso a paso</strong></summary>

**1. Clonar el proyecto**

```bash
git clone https://github.com/gabyta02/RioGo.git
cd RioGo
```

**2. Configurar la base de datos**

Crea `base_datos/.env`:

```env
POSTGRES_DB=riobambago
POSTGRES_USER=riobambago
POSTGRES_PASSWORD=cambia_esta_contrasena
```

**3. Configurar la API**

Crea `apis/.env`:

```env
DATABASE_URL=postgresql+psycopg2://riobambago:cambia_esta_contrasena@postgres-apis:5432/riobambago
SECRET_KEY=genera_una_clave_larga_y_aleatoria
ALGORITHM=HS256
VOYAGE_API_KEY=tu_clave_de_voyage
MODELO_VOYAGE=voyage-4-lite

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
GMAIL_USUARIO=tu_correo
GMAIL_CLAVE_APLICATION=tu_clave_de_aplicacion
```

**4. Configurar el chatbot**

Crea `chatboot/.env`:

```env
DEEPSEEK_API_KEY=tu_clave_de_deepseek
CHATBOOT_TIMEZONE=America/Guayaquil
```

El resto de las direcciones internas, límites y tiempos de espera ya se definen en `docker-compose.yml`.

**5. Preparar TLS**

Coloca el certificado y su clave en `ngix/certs/`, usando los nombres esperados por `ngix/nginx.conf`, o adapta esa configuración para tu dominio y entorno local.

> [!IMPORTANT]
> No publiques archivos `.env`, claves privadas, contraseñas ni certificados reales. Si alguna credencial fue incluida anteriormente en el historial de Git, debe revocarse y reemplazarse.

**6. Construir e iniciar**

```bash
docker compose up -d --build
docker compose ps
```

Para consultar los registros:

```bash
docker compose logs -f apis chatboot ngix
```

Para detener los contenedores sin borrar los datos:

```bash
docker compose down
```

</details>

---

## 🔌 API y canales de comunicación

### HTTP

La API se publica bajo `/api/v1`. FastAPI genera documentación interactiva en `/docs` cuando se accede directamente al servicio; para exponerla a través de Nginx se debe añadir una ruta específica en el proxy.

| Dominio | Prefijo principal |
| :--- | :--- |
| Autenticación y recuperación | `/api/v1/auth` |
| Sitios y fichas turísticas | `/api/v1/sitios`, `/api/v1/ficha_sitio` |
| Favoritos, noticias e historial | `/api/v1/favoritos`, `/api/v1/noticias`, `/api/v1/historial` |
| Rutas turísticas y buses | `/api/v1/rutas-movil-turismo`, `/api/v1/rutas-buses` |
| Herramientas del chatbot | `/api/v1/chatboot/herramientas` |
| Pregunta directa | `/api/v1/chatboot/pregunta-directa` |
| Administración | `/api/v1/admin/*` |

Las rutas protegidas utilizan `Authorization: Bearer <token>`. El sistema también implementa refresh mediante cookie, sesiones administrativas, roles, permisos y control de inactividad.

### WebSockets

| Canal | Uso |
| :--- | :--- |
| `/ws/exploracion` | Recomendaciones y consultas turísticas abiertas |
| `/ws/pregunta_directa` | Preguntas específicas sobre un sitio o su contenido |
| `/ws/sitio` | Proxy heredado presente en Nginx; no tiene una ruta registrada en la aplicación actual |

El evento de cierre del procesamiento se envía como `clasificacion_final` e incluye el canal y el contenido listo para representar en la app.

---

## 🧪 Pruebas y documentación

```bash
cd apis
pytest tests/ -q --ignore=tests/probar_apis_chatboot.py
```

Documentos útiles:

* Índice técnico de la API
* Arquitectura de la API
* Autenticación, tokens y permisos
* Arquitectura de herramientas del chatbot
* Contratos HTTP
* Instalación independiente de GeoNode
* Contrato para pruebas JMeter

---

## 🗺️ GeoNode y GeoServer

`geonode_gestor/` contiene una instalación Docker independiente para cargar shapefiles, editar información geográfica, visualizar capas y publicarlas mediante GeoServer. No forma parte del `docker-compose.yml` principal; su preparación y conexión con Nginx deben realizarse siguiendo su propia guía.
