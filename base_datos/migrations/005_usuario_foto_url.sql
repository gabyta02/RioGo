ALTER TABLE conversacion.usuario
    ADD COLUMN IF NOT EXISTS foto_url TEXT;

DROP TRIGGER IF EXISTS trg_usuario_actualizado_en ON conversacion.usuario;

CREATE TRIGGER trg_usuario_actualizado_en
BEFORE UPDATE OF username, email, password, activo, id_cargo,
    nombre_completo, autentificacion_doble, foto_url
ON conversacion.usuario
FOR EACH ROW
EXECUTE FUNCTION turismo.fn_actualizar_timestamp();
