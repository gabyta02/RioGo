# Modulo GeoNode Gestor

Este modulo prepara una instalacion Docker independiente de GeoNode para gestionar informacion GIS sin afectar los servicios actuales de RiobambaGo. Queda pensado para cargar shapefiles, visualizar capas, editar informacion geografica y publicar capas mediante GeoServer.

No se ha iniciado ningun servicio. Estos archivos solo dejan preparada la configuracion.

## Servicios incluidos

- `geonode_gestor_django`: aplicacion GeoNode/Django.
- `geonode_gestor_geoserver`: GeoServer para publicar capas.
- `geonode_gestor_db`: PostgreSQL/PostGIS propio para GeoNode.
- `geonode_gestor_redis`: Redis para colas y cache operativo.
- `geonode_gestor_celery`: tareas en segundo plano.
- `geonode_gestor_geoserver_data`: inicializa el directorio de datos de GeoServer.

Se usan varios contenedores porque GeoNode no es una sola pieza: Django atiende la aplicacion, GeoServer sirve mapas y servicios OGC, PostGIS persiste datos espaciales, Redis coordina tareas y Celery procesa trabajos pesados como importaciones.

## Archivos creados

- `docker-compose.geonode.yml`: define servicios, red propia y volumenes propios.
- `.env.geonode.example`: plantilla de variables para crear `.env.geonode`.
- `nginx-geonode.conf.example`: ejemplo manual para publicar detras de Nginx.
- `README_INSTALACION.md`: esta guia.

## Variables a revisar antes de levantarlo

Antes de ejecutar cualquier servicio, copiar `.env.geonode.example` a `.env.geonode` y cambiar al menos:

- `PUBLIC_DOMAIN`, `SITEURL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`.
- `GEOSERVER_PUBLIC_LOCATION` y `GEOSERVER_WEB_UI_LOCATION`.
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`.
- `GEOSERVER_ADMIN_USER`, `GEOSERVER_ADMIN_PASSWORD`.
- `POSTGRES_PASSWORD`, `GEONODE_DATABASE_PASSWORD`, `GEONODE_GEODATABASE_PASSWORD`.
- `SECRET_KEY`, `OAUTH2_API_KEY`, `OAUTH2_CLIENT_ID`, `OAUTH2_CLIENT_SECRET`.
- `GEONODE_LOCAL_PORT` y `GEOSERVER_LOCAL_PORT` si `8081` o `8082` ya estan ocupados.
- Variables de correo si se enviaran notificaciones.

## Validar sin levantar contenedores

Comando documentado para validar la configuracion renderizada:

```bash
docker compose -f geonode_gestor/docker-compose.geonode.yml --env-file geonode_gestor/.env.geonode.example config
```

Este comando no debe crear contenedores, redes ni volumenes. Solo muestra la configuracion final que Docker Compose interpretaria.

## Levantar mas adelante

Cuando se haya revisado el archivo `.env.geonode` real:

```bash
docker compose -f geonode_gestor/docker-compose.geonode.yml --env-file geonode_gestor/.env.geonode up -d
```

Este comando no se ejecuto durante la preparacion del modulo.

## Ver logs cuando este levantado

```bash
docker compose -f geonode_gestor/docker-compose.geonode.yml --env-file geonode_gestor/.env.geonode logs -f
```

Para un servicio concreto:

```bash
docker compose -f geonode_gestor/docker-compose.geonode.yml --env-file geonode_gestor/.env.geonode logs -f geonode_gestor_django
```

## Detener solo este modulo

```bash
docker compose -f geonode_gestor/docker-compose.geonode.yml --env-file geonode_gestor/.env.geonode down
```

No agregar `-v` en la detencion normal, porque eso elimina volumenes y puede borrar datos persistentes.

## Eliminar solo los recursos de este modulo

Primero detener:

```bash
docker compose -f geonode_gestor/docker-compose.geonode.yml --env-file geonode_gestor/.env.geonode down
```

Si algun dia se decide borrar datos, hacerlo de forma manual y consciente eliminando solo volumenes con prefijo `geonode_gestor_`. No usar `docker system prune` para este caso.

## Uso manual del ejemplo de Nginx

El archivo `nginx-geonode.conf.example` es solo una referencia. No se aplica automaticamente.

El ejemplo usa:

- GeoNode en `http://127.0.0.1:8081`.
- GeoServer en `http://127.0.0.1:8082/geoserver/`.
- `server_name geo.midominio.com`.
- Redireccion HTTP a HTTPS.
- `client_max_body_size 500M`.

Este ejemplo funciona directamente si Nginx corre en el host. El Nginx actual de RiobambaGo corre dentro del contenedor `riobambago-ngix` y la red `RiobambaGo`; desde ese contenedor, `127.0.0.1` no apunta al host, sino al propio contenedor. Integrar ese Nginx con GeoNode requiere una fase posterior autorizada, posiblemente conectando redes o configurando acceso controlado hacia el host.

## Conexion futura con PostGIS principal

En esta fase GeoNode usa una base PostGIS propia e independiente. No se conecta a la base principal de la app.

Para una segunda fase se podria:

- Crear un usuario de solo lectura o permisos limitados en la base PostGIS principal.
- Exponer la base principal de forma controlada solo a GeoServer o a la red necesaria.
- Registrar en GeoServer un datastore PostGIS hacia las tablas geograficas necesarias.
- Evitar que GeoNode escriba en tablas de negocio de RiobambaGo sin una politica clara de permisos.

Nada de esto esta implementado ahora.

## Recomendaciones de seguridad

- Cambiar todas las contrasenas y secretos antes de levantar.
- Mantener `DEBUG=False`.
- Publicar GeoNode solo mediante HTTPS.
- No exponer PostgreSQL/PostGIS al exterior.
- Mantener los puertos `8081` y `8082` ligados a `127.0.0.1`.
- Revisar memoria disponible para GeoServer antes de importar capas grandes.
- Hacer backups de los volumenes `geonode_gestor_db_data` y `geonode_gestor_geoserver_data`.

## Riesgos y precauciones

- Las importaciones GIS pueden consumir bastante CPU, RAM y disco.
- Shapefiles grandes pueden requerir subir `client_max_body_size` y ajustar memoria JVM.
- La primera ejecucion descargara imagenes si no existen localmente.
- Cambiar dominios o `SITEURL` despues de cargar datos puede requerir ajustes internos.
- No reutilizar redes ni volumenes del proyecto actual sin una fase de integracion revisada.

## Estado actual

- No se ejecuto `docker compose up`.
- No se ejecuto `docker compose down`.
- No se crearon contenedores.
- No se crearon redes Docker.
- No se crearon volumenes Docker.
- No se modifico el `docker-compose.yml` principal.
- No se modifico la carpeta `ngix/`.
- No se modifico la carpeta `apis/`.
- No se modifico la carpeta `base_datos/`.
