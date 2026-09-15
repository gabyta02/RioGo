-- Alcance por sitio en permisos de usuario (sin tablas nuevas).
-- Ejecutar en BD existente: psql -U ... -d ... -f 003_usuario_permiso_alcance.sql

BEGIN;

ALTER TABLE conversacion.usuario_permiso
    ADD COLUMN IF NOT EXISTS id_sitio BIGINT NULL
        REFERENCES turismo.sitio(id_sitio) ON DELETE CASCADE;

ALTER TABLE conversacion.usuario_permiso
    DROP CONSTRAINT IF EXISTS usuario_permiso_pkey;

CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_permiso_global
    ON conversacion.usuario_permiso (id_usuario, id_modulo, accion)
    WHERE id_sitio IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_permiso_sitio
    ON conversacion.usuario_permiso (id_usuario, id_modulo, accion, id_sitio)
    WHERE id_sitio IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_usuario_permiso_sitio
    ON conversacion.usuario_permiso (id_usuario, id_sitio)
    WHERE id_sitio IS NOT NULL;

INSERT INTO conversacion.cargo (nombre)
VALUES ('Dueño')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO conversacion.cargo_permiso (id_cargo, id_modulo, accion)
SELECT c.id_cargo, m.id_modulo, 'ver'::conversacion.accion_t
FROM conversacion.cargo c
CROSS JOIN conversacion.modulo m
WHERE c.nombre = 'Dueño'
  AND m.codigo = 'dashboard'
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION conversacion.fn_copiar_permisos_cargo()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.id_cargo IS NOT NULL THEN
        INSERT INTO conversacion.usuario_permiso (id_usuario, id_modulo, accion, id_sitio)
        SELECT NEW.id_usuario, cp.id_modulo, cp.accion, NULL
        FROM conversacion.cargo_permiso cp
        WHERE cp.id_cargo = NEW.id_cargo
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
