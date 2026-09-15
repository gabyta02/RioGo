BEGIN;

CREATE TABLE IF NOT EXISTS conversacion.sesion_usuario (
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

CREATE INDEX IF NOT EXISTS idx_sesion_usuario_usuario
    ON conversacion.sesion_usuario (id_usuario);

CREATE INDEX IF NOT EXISTS idx_sesion_usuario_usuario_activo
    ON conversacion.sesion_usuario (id_usuario, activo);

CREATE INDEX IF NOT EXISTS idx_sesion_usuario_activo
    ON conversacion.sesion_usuario (activo);

DROP TRIGGER IF EXISTS trg_sesion_usuario_actualizado_en ON conversacion.sesion_usuario;

CREATE TRIGGER trg_sesion_usuario_actualizado_en
BEFORE UPDATE OF refresh_token_hash, cliente, ip, user_agent, activo,
    caducado, ultimo_uso_en, revocado_en
ON conversacion.sesion_usuario
FOR EACH ROW
EXECUTE FUNCTION turismo.fn_actualizar_timestamp();

COMMIT;
