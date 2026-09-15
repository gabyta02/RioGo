ALTER TABLE trazabilidad.accion
    ADD COLUMN IF NOT EXISTS referencia TEXT;

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
