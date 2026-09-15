BEGIN;

UPDATE conversacion.cargo
SET nombre = 'Super admin'
WHERE LOWER(nombre) = 'super administrador';

INSERT INTO conversacion.cargo (nombre, activo)
VALUES ('Admin', TRUE)
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO conversacion.cargo (nombre, activo)
VALUES ('Dueño', TRUE)
ON CONFLICT (nombre) DO NOTHING;

DELETE FROM conversacion.cargo_permiso cp
USING conversacion.cargo c, conversacion.modulo m
WHERE cp.id_cargo = c.id_cargo
  AND cp.id_modulo = m.id_modulo
  AND LOWER(c.nombre) IN ('admin', 'dueño', 'dueno')
  AND m.codigo = 'admin_accounts';

INSERT INTO conversacion.cargo_permiso (id_cargo, id_modulo, accion)
SELECT c.id_cargo, m.id_modulo, 'ver'::conversacion.accion_t
FROM conversacion.cargo c
CROSS JOIN conversacion.modulo m
WHERE LOWER(c.nombre) IN ('dueño', 'dueno')
  AND m.codigo IN ('dashboard', 'analytics')
ON CONFLICT DO NOTHING;

COMMIT;
