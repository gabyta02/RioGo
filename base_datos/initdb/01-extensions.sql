CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER DATABASE riobambago SET timezone TO 'America/Guayaquil';
SET timezone TO 'America/Guayaquil';


-- ============================================================
-- SCHEMAS
-- ============================================================
CREATE SCHEMA IF NOT EXISTS turismo;
CREATE SCHEMA IF NOT EXISTS conversacion;
CREATE SCHEMA IF NOT EXISTS gis;
CREATE SCHEMA IF NOT EXISTS trazabilidad;


-- ============================================================
-- ENUMS
-- ============================================================
CREATE TYPE turismo.etiqueta_precio_t AS ENUM (
    'economico',
    'medio',
    'alto',
    'desconocido'
);

CREATE TYPE turismo.tipo_sitio_t AS ENUM (
    'servicio_turistico',
    'atractivo_turistico',
    'operadora_turistica',
    'desconocido'
);

CREATE TYPE conversacion.rol_mensaje_t AS ENUM (
    'usuario',
    'conversacion_general',
    'conversacion_sitio_especifico'
);

CREATE TYPE turismo.tipo_documento_t AS ENUM (
    'sitio',
    'ruta'
);

CREATE TYPE turismo.tipo_chunk_t AS ENUM (
    'descripcion',
    'seccion'
);

CREATE TYPE turismo.origen_chunk_t AS ENUM (
    'sitio',
    'ruta'
);

CREATE TYPE gis.tipo_ruta_t AS ENUM (
    'Senderismo',
    'Ciclismo',
    'Caminata Urbana',
    'Montañismo',
    'Otras'
);

CREATE TYPE conversacion.accion_t AS ENUM (
    'ver',
    'crear',
    'actualizar',
    'eliminar',
    'exportar'
);

CREATE TYPE trazabilidad.resultado_t AS ENUM (
    'exitoso',
    'fallido'
);

CREATE TYPE trazabilidad.accion_t AS ENUM (
    'INSERT', 'UPDATE', 'DELETE',
    'creacion_cuenta', 'actualizacion_cuenta',
    'inactivacion_cuenta', 'eliminacion_cuenta',
    'cambio_username', 'cambio_email', 'cambio_password',
    'cambio_2fa', 'cambio_foto_perfil',
    'logout'
);


-- ============================================================
-- FUNCIÓN: timestamp (usada por triggers en otras tablas)
-- Se define primero porque los triggers la referencian
-- ============================================================
CREATE OR REPLACE FUNCTION turismo.fn_actualizar_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.actualizado_en := NOW();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION trazabilidad.fn_registrar_accion(
    p_id_usuario         INT,
    p_username           VARCHAR,
    p_ip                 INET,
    p_accion             trazabilidad.accion_t,
    p_esquema_modificado VARCHAR,
    p_tabla_modificada   VARCHAR,
    p_id_registro        TEXT,
    p_datos_anteriores   JSONB DEFAULT NULL,
    p_datos_nuevos       JSONB DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM trazabilidad.fn_registrar_accion(
        p_id_usuario,
        p_username,
        p_ip,
        p_accion,
        p_esquema_modificado,
        p_tabla_modificada,
        p_id_registro,
        NULL,
        p_datos_anteriores,
        p_datos_nuevos
    );
END;
$$;


-- ============================================================
-- TURISMO
-- ============================================================

CREATE TABLE turismo.parroquia (
    id_parroquia SERIAL PRIMARY KEY,
    nombre       VARCHAR(100) NOT NULL,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_parroquia_nombre_trgm
    ON turismo.parroquia
    USING gin (translate(lower(nombre), 'áéíóúüñàèìòùâêîôûãõç', 'aeiouunaeiouaeiouaoc') gin_trgm_ops)
    WHERE activo = TRUE;


CREATE TABLE turismo.plataforma (
    id_plataforma SERIAL PRIMARY KEY,
    id_parroquia  INT     NOT NULL REFERENCES turismo.parroquia(id_parroquia),
    nombre        VARCHAR(100) NOT NULL,
    activo        BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_plataforma_nombre_trgm
    ON turismo.plataforma
    USING gin (translate(lower(nombre), 'áéíóúüñàèìòùâêîôûãõç', 'aeiouunaeiouaeiouaoc') gin_trgm_ops)
    WHERE activo = TRUE;


CREATE TABLE turismo.categoria (
    id_categoria SERIAL PRIMARY KEY,
    nombre       VARCHAR(100) NOT NULL,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_categoria_nombre_trgm
    ON turismo.categoria
    USING gin (translate(lower(nombre), 'áéíóúüñàèìòùâêîôûãõç', 'aeiouunaeiouaeiouaoc') gin_trgm_ops)
    WHERE activo = TRUE;


CREATE TABLE turismo.subcategoria (
    id_subcategoria SERIAL PRIMARY KEY,
    id_categoria    INT     NOT NULL REFERENCES turismo.categoria(id_categoria),
    nombre          VARCHAR(100) NOT NULL,
    activo          BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_subcategoria_nombre_trgm
    ON turismo.subcategoria
    USING gin (translate(lower(nombre), 'áéíóúüñàèìòùâêîôûãõç', 'aeiouunaeiouaeiouaoc') gin_trgm_ops)
    WHERE activo = TRUE;


CREATE TABLE turismo.sitio (
    id_sitio        BIGSERIAL PRIMARY KEY,
    id_parroquia    BIGINT REFERENCES turismo.parroquia(id_parroquia),
    id_plataforma   BIGINT REFERENCES turismo.plataforma(id_plataforma),
    id_categoria    BIGINT NOT NULL REFERENCES turismo.categoria(id_categoria),
    id_subcategoria BIGINT REFERENCES turismo.subcategoria(id_subcategoria),
    tipo            turismo.tipo_sitio_t NOT NULL,
    nombre          VARCHAR(180) NOT NULL,
    descripcion_corta VARCHAR(350),
    ubicacion       GEOGRAPHY(POINT, 4326),
    es_gratuito     BOOLEAN,
    permite_mascotas BOOLEAN,
    parqueadero     BOOLEAN,
    tiene_wifi      BOOLEAN,
    accesibilidad   BOOLEAN,
    activo          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_sitio_ubicacion_activo_gist
    ON turismo.sitio USING GIST (ubicacion)
    WHERE activo = TRUE AND ubicacion IS NOT NULL;

CREATE INDEX idx_sitio_activo_categoria_sub
    ON turismo.sitio (id_categoria, id_subcategoria)
    WHERE activo = TRUE;

CREATE INDEX idx_sitio_activo_subcategoria
    ON turismo.sitio (id_subcategoria)
    WHERE activo = TRUE;

CREATE INDEX idx_sitio_activo_parroquia
    ON turismo.sitio (id_parroquia)
    WHERE activo = TRUE;

CREATE INDEX idx_sitio_nombre_trgm
    ON turismo.sitio
    USING gin (translate(lower(nombre), 'áéíóúüñàèìòùâêîôûãõç', 'aeiouunaeiouaeiouaoc') gin_trgm_ops)
    WHERE activo = TRUE;


CREATE TABLE turismo.direccion (
    id_direccion         BIGSERIAL PRIMARY KEY,
    id_sitio             BIGINT NOT NULL UNIQUE REFERENCES turismo.sitio(id_sitio) ON DELETE CASCADE,
    direccion_texto      VARCHAR(200) NOT NULL,
    referencia_adicional VARCHAR(200)
);

CREATE INDEX idx_direccion_texto_trgm
    ON turismo.direccion
    USING gin (translate(lower(direccion_texto), 'áéíóúüñàèìòùâêîôûãõç', 'aeiouunaeiouaeiouaoc') gin_trgm_ops);

CREATE INDEX idx_direccion_referencia_trgm
    ON turismo.direccion
    USING gin (
        translate(
            lower(COALESCE(referencia_adicional, '')),
            'áéíóúüñàèìòùâêîôûãõç',
            'aeiouunaeiouaeiouaoc'
        ) gin_trgm_ops
    );


CREATE TABLE turismo.multimedia (
    id_multimedia SERIAL PRIMARY KEY,
    id_sitio      INT     NOT NULL REFERENCES turismo.sitio(id_sitio) ON DELETE CASCADE,
    url           TEXT    NOT NULL,
    es_principal  BOOLEAN NOT NULL DEFAULT FALSE,
    activo        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_multimedia_sitio
    ON turismo.multimedia (id_sitio);

CREATE INDEX idx_sitio_multimedia_principal
    ON turismo.multimedia (id_sitio, es_principal)
    WHERE es_principal = TRUE;

CREATE UNIQUE INDEX uq_multimedia_principal_por_sitio
    ON turismo.multimedia (id_sitio)
    WHERE es_principal = TRUE;

CREATE OR REPLACE FUNCTION turismo.fn_un_solo_principal_media()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.es_principal = TRUE THEN
        UPDATE turismo.multimedia
        SET es_principal = FALSE
        WHERE id_sitio      = NEW.id_sitio
          AND id_multimedia <> COALESCE(NEW.id_multimedia, -1)
          AND es_principal  = TRUE;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_un_solo_principal_media
BEFORE INSERT OR UPDATE OF es_principal, id_sitio
ON turismo.multimedia
FOR EACH ROW
WHEN (NEW.es_principal = TRUE)
EXECUTE FUNCTION turismo.fn_un_solo_principal_media();


-- Permite N contactos por sitio (teléfono, email, web, etc.)
CREATE TABLE turismo.contacto (
    id_contacto SERIAL PRIMARY KEY,
    id_sitio    BIGINT       NOT NULL REFERENCES turismo.sitio(id_sitio) ON DELETE CASCADE,
    nombre      VARCHAR(100) NOT NULL,
    contenido   VARCHAR(300) NOT NULL,
    activo      BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_contacto_sitio_activo
    ON turismo.contacto (id_sitio)
    WHERE activo = TRUE;

CREATE INDEX idx_contacto_texto_trgm
    ON turismo.contacto
    USING gin (translate(lower(nombre), 'áéíóúüñàèìòùâêîôûãõç', 'aeiouunaeiouaeiouaoc') gin_trgm_ops);


CREATE TABLE turismo.horario (
    id_horario  SERIAL  PRIMARY KEY,
    id_sitio    INT     NOT NULL REFERENCES turismo.sitio(id_sitio) ON DELETE CASCADE,
    abierto_24h BOOLEAN NOT NULL DEFAULT FALSE,
    comentario  VARCHAR(200),
    activo      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_horario_sitio_activo
    ON turismo.horario (id_sitio)
    WHERE activo = TRUE;


CREATE TABLE turismo.horario_detalle (
    id_horario_detalle SERIAL PRIMARY KEY,
    id_horario         INT      NOT NULL REFERENCES turismo.horario(id_horario) ON DELETE CASCADE,
    dia_semana         SMALLINT NOT NULL,
    hora_inicio        TIME     NOT NULL,
    hora_fin           TIME     NOT NULL,
    activo             BOOLEAN  NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_dia_semana CHECK (dia_semana BETWEEN 1 AND 7),
    CONSTRAINT chk_horas      CHECK (hora_inicio < hora_fin)
);

CREATE INDEX idx_horario_detalle_dia
    ON turismo.horario_detalle (dia_semana);

CREATE INDEX idx_horario_detalle_horario
    ON turismo.horario_detalle (id_horario)
    WHERE activo = TRUE;

CREATE INDEX idx_horario_detalle_horario_dia
    ON turismo.horario_detalle (id_horario, dia_semana)
    WHERE activo = TRUE;


CREATE TABLE turismo.rango_precio (
    id_rango_precio SERIAL PRIMARY KEY,
    id_sitio        INT            NOT NULL REFERENCES turismo.sitio(id_sitio) ON DELETE CASCADE,
    precio_min      DECIMAL(8,2)   NOT NULL CHECK (precio_min >= 0),
    precio_max      DECIMAL(8,2)   NOT NULL CHECK (precio_max >= 0),
    etiqueta_precio turismo.etiqueta_precio_t,
    activo          BOOLEAN        NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_rango_precio CHECK (precio_min <= precio_max)
);

CREATE INDEX idx_rango_precio_sitio_activo
    ON turismo.rango_precio (id_sitio)
    WHERE activo = TRUE;


CREATE TABLE turismo.tarifa_acceso (
    id_tarifa_acceso SERIAL PRIMARY KEY,
    id_sitio         INT          NOT NULL REFERENCES turismo.sitio(id_sitio) ON DELETE CASCADE,
    precio           DECIMAL(8,2) NOT NULL CHECK (precio >= 0),
    condicion        VARCHAR(150),
    activo           BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_tarifa_acceso_sitio_activo
    ON turismo.tarifa_acceso (id_sitio)
    WHERE activo = TRUE;

CREATE INDEX idx_tarifa_condicion_trgm
    ON turismo.tarifa_acceso
    USING gin (translate(lower(COALESCE(condicion, '')), 'áéíóúüñàèìòùâêîôûãõç', 'aeiouunaeiouaeiouaoc') gin_trgm_ops)
    WHERE activo = TRUE;


CREATE TABLE turismo.noticia (
    id_noticia   SERIAL       PRIMARY KEY,
    titulo       VARCHAR(200) NOT NULL,
    imagen_url   TEXT,
    fecha_inicio DATE         NOT NULL,
    fecha_fin    DATE,
    activa       BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_fechas_noticia CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);


-- ============================================================
-- RAG: documentos y chunks
-- ============================================================

CREATE TABLE turismo.sitio_documento (
    id_documento       BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    origen             turismo.tipo_documento_t NOT NULL,
    titulo             VARCHAR(200) NOT NULL,
    id_vinculo         BIGINT       NOT NULL,
    repositorio_nombre VARCHAR(180),
    descripcion        VARCHAR(800) NOT NULL,
    ruta_archivo       TEXT,
    activo             BOOLEAN      NOT NULL DEFAULT FALSE,
    creado_en          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sitio_documento_vinculo
    ON turismo.sitio_documento (origen, id_vinculo);


CREATE TABLE turismo.chunk_fuente (
    id_fuente    BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    tipo_chunk   turismo.tipo_chunk_t  NOT NULL,
    origen       turismo.origen_chunk_t NOT NULL,
    id_vinculo   BIGINT       NOT NULL,
    id_documento BIGINT,
    creado_en    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Un documento solo genera una fuente
    CONSTRAINT uq_fuente_documento UNIQUE (id_documento),

    -- Si es seccion debe tener documento, si es descripcion no debe tenerlo
    CONSTRAINT chk_tipo_documento CHECK (
        (tipo_chunk = 'seccion'     AND id_documento IS NOT NULL) OR
        (tipo_chunk = 'descripcion' AND id_documento IS NULL)
    ),

    -- Solo una descripcion por sitio o ruta; las secciones se distinguen por id_documento
    CONSTRAINT uq_fuente_descripcion UNIQUE NULLS NOT DISTINCT (origen, id_vinculo, tipo_chunk, id_documento)
);

-- Corregido: la restricción de unicidad en descripcion se maneja con el UNIQUE anterior.
-- Este índice parcial refuerza que solo haya una descripcion por origen+vinculo
CREATE UNIQUE INDEX uq_descripcion_por_vinculo
    ON turismo.chunk_fuente (origen, id_vinculo)
    WHERE tipo_chunk = 'descripcion';

CREATE INDEX idx_chunk_fuente_vinculo
    ON turismo.chunk_fuente (origen, id_vinculo);

CREATE INDEX idx_chunk_fuente_documento
    ON turismo.chunk_fuente (id_documento)
    WHERE id_documento IS NOT NULL;


CREATE TABLE turismo.chunk (
    id_chunk  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    id_fuente BIGINT      NOT NULL REFERENCES turismo.chunk_fuente (id_fuente) ON DELETE CASCADE,
    contenido TEXT         NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    creado_en TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chunk_embedding
    ON turismo.chunk
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_chunk_fts
    ON turismo.chunk
    USING gin (to_tsvector('spanish', contenido));

CREATE INDEX idx_chunk_trgm
    ON turismo.chunk
    USING gin (lower(contenido) gin_trgm_ops);

CREATE INDEX idx_chunk_id_fuente
    ON turismo.chunk (id_fuente);


-- ============================================================
-- FUNCIONES Y TRIGGERS DE ELIMINACIÓN RAG
-- ============================================================

-- Al eliminar un sitio: borra sus documentos y fuentes
-- (chunks se eliminan por CASCADE desde chunk_fuente)
CREATE OR REPLACE FUNCTION turismo.fn_eliminar_chunks_sitio()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM turismo.sitio_documento
    WHERE origen     = 'sitio'
      AND id_vinculo = OLD.id_sitio;

    DELETE FROM turismo.chunk_fuente
    WHERE origen     = 'sitio'
      AND id_vinculo = OLD.id_sitio;

    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_eliminar_chunks_sitio
BEFORE DELETE ON turismo.sitio
FOR EACH ROW
EXECUTE FUNCTION turismo.fn_eliminar_chunks_sitio();


-- Al eliminar una ruta: borra sus documentos y fuentes
CREATE OR REPLACE FUNCTION turismo.fn_eliminar_chunks_ruta()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM turismo.sitio_documento
    WHERE origen     = 'ruta'
      AND id_vinculo = OLD.id_ruta;

    DELETE FROM turismo.chunk_fuente
    WHERE origen     = 'ruta'
      AND id_vinculo = OLD.id_ruta;

    RETURN OLD;
END;
$$;

-- Al eliminar un documento: borra su fuente (chunks por CASCADE)
CREATE OR REPLACE FUNCTION turismo.fn_eliminar_chunks_documento()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM turismo.chunk_fuente
    WHERE id_documento = OLD.id_documento;

    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_eliminar_chunks_documento
BEFORE DELETE ON turismo.sitio_documento
FOR EACH ROW
EXECUTE FUNCTION turismo.fn_eliminar_chunks_documento();


-- ============================================================
-- USUARIOS Y PERMISOS
-- ============================================================

CREATE TABLE conversacion.cargo (
    id_cargo SERIAL PRIMARY KEY,
    nombre   VARCHAR(100) NOT NULL UNIQUE,
    activo   BOOLEAN      NOT NULL DEFAULT TRUE
);

INSERT INTO conversacion.cargo (nombre) VALUES
    ('Super admin'),
    ('Admin'),
    ('Dueño');


CREATE TABLE conversacion.modulo (
    id_modulo SERIAL PRIMARY KEY,
    codigo    VARCHAR(50)  NOT NULL UNIQUE,
    nombre    VARCHAR(100) NOT NULL,
    activo    BOOLEAN      NOT NULL DEFAULT TRUE
);

INSERT INTO conversacion.modulo (codigo, nombre) VALUES
    ('dashboard',       'Dashboard'),
    ('analytics',       'Análisis de consultas'),
    ('attractions',     'Atractivos turísticos'),
    ('categories',      'Categorías'),
    ('routes',          'Rutas turísticas'),
    ('chatbot_content', 'Contenido chatbot'),
    ('noticias',        'Noticias'),
    ('action_log',      'Registro de acciones'),
    ('admin_accounts',  'Cuentas administrativas');


CREATE TABLE conversacion.cargo_permiso (
    id_cargo  INT              NOT NULL REFERENCES conversacion.cargo(id_cargo)   ON DELETE CASCADE,
    id_modulo INT              NOT NULL REFERENCES conversacion.modulo(id_modulo) ON DELETE CASCADE,
    accion    conversacion.accion_t NOT NULL,
    PRIMARY KEY (id_cargo, id_modulo, accion)
);

INSERT INTO conversacion.cargo_permiso (id_cargo, id_modulo, accion)
SELECT c.id_cargo, m.id_modulo, a.accion
FROM conversacion.cargo c
CROSS JOIN conversacion.modulo m
CROSS JOIN (VALUES
    ('ver'::conversacion.accion_t),
    ('crear'::conversacion.accion_t),
    ('actualizar'::conversacion.accion_t),
    ('eliminar'::conversacion.accion_t),
    ('exportar'::conversacion.accion_t)
) AS a(accion)
WHERE c.nombre = 'Super admin';


CREATE TABLE conversacion.usuario (
    id_usuario            SERIAL       PRIMARY KEY,
    id_cargo              INT          REFERENCES conversacion.cargo(id_cargo),
    nombre_completo       VARCHAR(150),
    username              VARCHAR(80)  NOT NULL UNIQUE,
    password              TEXT         NOT NULL,
    email                 VARCHAR(150) NOT NULL UNIQUE,
    token                 TEXT,
    activo                BOOLEAN      NOT NULL DEFAULT TRUE,
    autentificacion_doble BOOLEAN      NOT NULL DEFAULT FALSE,
    foto_url              TEXT,
    ultimo_acceso_en      TIMESTAMPTZ,
    actualizado_en        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE conversacion.sesion_usuario (
    id_sesion          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    id_usuario         INT          NOT NULL REFERENCES conversacion.usuario(id_usuario) ON DELETE CASCADE,
    refresh_token_hash TEXT         NOT NULL UNIQUE,
    cliente            VARCHAR(30)  NOT NULL DEFAULT 'unknown',
    ip                 INET,
    user_agent         TEXT,
    activo             BOOLEAN      NOT NULL DEFAULT TRUE,
    caducado           BOOLEAN      NOT NULL DEFAULT FALSE,
    creado_en          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ultimo_uso_en      TIMESTAMPTZ,
    revocado_en        TIMESTAMPTZ,
    actualizado_en     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sesion_usuario_usuario
    ON conversacion.sesion_usuario (id_usuario);

CREATE INDEX idx_sesion_usuario_usuario_activo
    ON conversacion.sesion_usuario (id_usuario, activo);

CREATE INDEX idx_sesion_usuario_activo
    ON conversacion.sesion_usuario (activo);

CREATE TRIGGER trg_sesion_usuario_actualizado_en
BEFORE UPDATE OF refresh_token_hash, cliente, ip, user_agent, activo,
    caducado, ultimo_uso_en, revocado_en
ON conversacion.sesion_usuario
FOR EACH ROW
EXECUTE FUNCTION turismo.fn_actualizar_timestamp();

CREATE TRIGGER trg_usuario_actualizado_en
BEFORE UPDATE OF username, email, password, activo, id_cargo,
    nombre_completo, autentificacion_doble, foto_url
ON conversacion.usuario
FOR EACH ROW
EXECUTE FUNCTION turismo.fn_actualizar_timestamp();


CREATE TABLE conversacion.usuario_permiso (
    id_usuario INT              NOT NULL REFERENCES conversacion.usuario(id_usuario) ON DELETE CASCADE,
    id_modulo  INT              NOT NULL REFERENCES conversacion.modulo(id_modulo)   ON DELETE CASCADE,
    accion     conversacion.accion_t NOT NULL,
    PRIMARY KEY (id_usuario, id_modulo, accion)
);

CREATE INDEX idx_usuario_permiso_usuario
    ON conversacion.usuario_permiso (id_usuario);

CREATE INDEX idx_usuario_permiso_modulo
    ON conversacion.usuario_permiso (id_modulo, accion);


CREATE OR REPLACE FUNCTION conversacion.fn_copiar_permisos_cargo()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.id_cargo IS NOT NULL THEN
        INSERT INTO conversacion.usuario_permiso (id_usuario, id_modulo, accion)
        SELECT NEW.id_usuario, cp.id_modulo, cp.accion
        FROM conversacion.cargo_permiso cp
        WHERE cp.id_cargo = NEW.id_cargo
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_copiar_permisos_cargo
AFTER INSERT ON conversacion.usuario
FOR EACH ROW
EXECUTE FUNCTION conversacion.fn_copiar_permisos_cargo();


-- ============================================================
-- CONVERSACION
-- ============================================================

CREATE TABLE conversacion.favorito (
    id_favorito SERIAL      PRIMARY KEY,
    id_usuario  INT         NOT NULL REFERENCES conversacion.usuario(id_usuario) ON DELETE CASCADE,
    id_sitio    INT         NOT NULL REFERENCES turismo.sitio(id_sitio)     ON DELETE CASCADE,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_usuario, id_sitio)
);


CREATE TABLE conversacion.conversacion (
    id_conversacion SERIAL       PRIMARY KEY,
    id_usuario      INT          NOT NULL REFERENCES conversacion.usuario(id_usuario) ON DELETE CASCADE,
    sesion_id       VARCHAR(100) NOT NULL,
    titulo          VARCHAR(200)
);

CREATE INDEX idx_conversacion_usuario
    ON conversacion.conversacion (id_usuario);


CREATE TABLE conversacion.mensaje_explorador (
    id_mensaje_ex     BIGSERIAL    PRIMARY KEY,
    id_conversacion   INT          NOT NULL REFERENCES conversacion.conversacion(id_conversacion) ON DELETE CASCADE,
    client_mensaje_id VARCHAR(100),

    categoria         VARCHAR(100)[],
    subcategoria      VARCHAR(100)[],

    contenido         TEXT         NOT NULL,
    embedding         VECTOR(1024),
    rol               conversacion.rol_mensaje_t NOT NULL,
    creado_en         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_msg_explo_conversacion
    ON conversacion.mensaje_explorador (id_conversacion);

CREATE INDEX idx_msg_explo_usuario_fecha
    ON conversacion.mensaje_explorador (creado_en DESC)
    WHERE rol = 'usuario';

CREATE INDEX idx_msg_explo_usuario_embedding_hnsw
    ON conversacion.mensaje_explorador
    USING hnsw (embedding vector_cosine_ops)
    WHERE rol = 'usuario' AND embedding IS NOT NULL;

CREATE TABLE conversacion.mensaje_detalle (
    id_mensaje_pd     BIGSERIAL    PRIMARY KEY,
    id_conversacion   INT          NOT NULL REFERENCES conversacion.conversacion(id_conversacion) ON DELETE CASCADE,
    client_mensaje_id VARCHAR(100),
    entidad_asociada  VARCHAR(100),
    contenido         TEXT         NOT NULL,
    embedding         VECTOR(1024),
    rol               conversacion.rol_mensaje_t NOT NULL,
    creado_en         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_msg_detalle_conversacion
    ON conversacion.mensaje_detalle (id_conversacion);

CREATE INDEX idx_msg_detalle_usuario_fecha
    ON conversacion.mensaje_detalle (creado_en DESC)
    WHERE rol = 'usuario';

CREATE INDEX idx_msg_detalle_usuario_embedding_hnsw
    ON conversacion.mensaje_detalle
    USING hnsw (embedding vector_cosine_ops)
    WHERE rol = 'usuario' AND embedding IS NOT NULL;


-- ============================================================
-- TRAZABILIDAD
-- ============================================================

CREATE OR REPLACE FUNCTION trazabilidad.fn_enmascarar_sensibles(datos JSONB)
RETURNS JSONB
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    campos_sensibles TEXT[] := ARRAY[
        'password',
        'token',
        'access_token',
        'refresh_token',
        'codigo_hash',
        'codigo_verificacion',
        'token_verificacion',
        'email',
        'email_nuevo'
    ];
    campo            TEXT;
BEGIN
    IF datos IS NULL THEN
        RETURN NULL;
    END IF;

    FOREACH campo IN ARRAY campos_sensibles LOOP
        IF datos ? campo THEN
            datos := jsonb_set(datos, ARRAY[campo], '"*****"');
        END IF;
    END LOOP;

    RETURN datos;
END;
$$;


CREATE TABLE trazabilidad.inicio_sesion (
    id_evento  BIGSERIAL   PRIMARY KEY,
    id_usuario INT         REFERENCES conversacion.usuario(id_usuario) ON DELETE SET NULL,
    username   VARCHAR(80) NOT NULL,
    ip         INET        NOT NULL,
    user_agent TEXT,
    resultado  trazabilidad.resultado_t NOT NULL,
    detalle    TEXT,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inicio_sesion_usuario
    ON trazabilidad.inicio_sesion (id_usuario);

CREATE INDEX idx_inicio_sesion_ip
    ON trazabilidad.inicio_sesion (ip);

CREATE INDEX idx_inicio_sesion_resultado
    ON trazabilidad.inicio_sesion (resultado);

CREATE INDEX idx_inicio_sesion_fecha
    ON trazabilidad.inicio_sesion (creado_en);


CREATE TABLE trazabilidad.accion (
    id_evento          BIGSERIAL    PRIMARY KEY,
    id_usuario         INT          REFERENCES conversacion.usuario(id_usuario) ON DELETE SET NULL,
    username           VARCHAR(80)  NOT NULL,
    ip                 INET         NOT NULL,
    accion             trazabilidad.accion_t NOT NULL,
    esquema_modificado VARCHAR(100) NOT NULL,
    tabla_modificada   VARCHAR(100) NOT NULL,
    id_registro        TEXT,
    referencia         TEXT,
    datos_anteriores   JSONB,
    datos_nuevos       JSONB,
    creado_en          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_accion_usuario
    ON trazabilidad.accion (id_usuario);

CREATE INDEX idx_accion_tabla
    ON trazabilidad.accion (esquema_modificado, tabla_modificada);

CREATE INDEX idx_accion_fecha
    ON trazabilidad.accion (creado_en);

CREATE INDEX idx_accion_registro
    ON trazabilidad.accion (id_registro);


CREATE OR REPLACE FUNCTION trazabilidad.fn_registrar_inicio_sesion(
    p_id_usuario INT,
    p_username   VARCHAR,
    p_ip         INET,
    p_user_agent TEXT,
    p_resultado  trazabilidad.resultado_t,
    p_detalle    TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO trazabilidad.inicio_sesion (
        id_usuario, username, ip, user_agent, resultado, detalle
    ) VALUES (
        p_id_usuario, p_username, p_ip, p_user_agent, p_resultado, p_detalle
    );
END;
$$;


CREATE OR REPLACE FUNCTION trazabilidad.fn_registrar_accion(
    p_id_usuario         INT,
    p_username           VARCHAR,
    p_ip                 INET,
    p_accion             trazabilidad.accion_t,
    p_esquema_modificado VARCHAR,
    p_tabla_modificada   VARCHAR,
    p_id_registro        TEXT,
    p_referencia         TEXT DEFAULT NULL,
    p_datos_anteriores   JSONB DEFAULT NULL,
    p_datos_nuevos       JSONB DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO trazabilidad.accion (
        id_usuario, username, ip, accion,
        esquema_modificado, tabla_modificada, id_registro,
        referencia, datos_anteriores, datos_nuevos
    ) VALUES (
        p_id_usuario, p_username, p_ip, p_accion,
        p_esquema_modificado, p_tabla_modificada, p_id_registro,
        NULLIF(BTRIM(p_referencia), ''),
        trazabilidad.fn_enmascarar_sensibles(p_datos_anteriores),
        trazabilidad.fn_enmascarar_sensibles(p_datos_nuevos)
    );
END;
$$;


-- ============================================================
-- GIS
-- ============================================================

CREATE TABLE gis.rutas_turistica (
    id_ruta    BIGSERIAL PRIMARY KEY,
    tipo_ruta  gis.tipo_ruta_t NOT NULL,
    titulo     VARCHAR(150)    NOT NULL,
    url_imagen TEXT,
    descripcion TEXT,
    geom_linea geometry(LineString, 4326),
    activo     BOOLEAN         NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_rutas_turistica_geom
    ON gis.rutas_turistica USING GIST (geom_linea);

CREATE INDEX idx_rutas_activo_tipo
    ON gis.rutas_turistica (tipo_ruta)
    WHERE activo = TRUE;

CREATE TRIGGER trg_eliminar_chunks_ruta
BEFORE DELETE ON gis.rutas_turistica
FOR EACH ROW
EXECUTE FUNCTION turismo.fn_eliminar_chunks_ruta();


CREATE TABLE gis.ruta_puntos (
    id_ruta_punto SERIAL  PRIMARY KEY,
    id_ruta       INT     NOT NULL REFERENCES gis.rutas_turistica(id_ruta) ON DELETE CASCADE,
    id_sitio      INT     REFERENCES turismo.sitio(id_sitio) ON DELETE SET NULL,
    punto_inicio  geometry(Point, 4326),
    punto_fin     geometry(Point, 4326),
    orden         INT     NOT NULL DEFAULT 1,
    activo        BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_ruta_punto_valido CHECK (
        id_sitio     IS NOT NULL OR
        punto_inicio IS NOT NULL OR
        punto_fin    IS NOT NULL
    )
);

CREATE INDEX idx_ruta_puntos_id_ruta
    ON gis.ruta_puntos (id_ruta);

CREATE INDEX idx_ruta_puntos_id_sitio
    ON gis.ruta_puntos (id_sitio);

CREATE INDEX idx_ruta_puntos_inicio_geom
    ON gis.ruta_puntos USING GIST (punto_inicio);

CREATE INDEX idx_ruta_puntos_fin_geom
    ON gis.ruta_puntos USING GIST (punto_fin);
