BEGIN;

INSERT INTO conversacion.usuario_permiso (id_usuario, id_modulo, accion, id_sitio)
SELECT DISTINCT up.id_usuario,
       m_analytics.id_modulo,
       'ver'::conversacion.accion_t,
       up.id_sitio
FROM conversacion.usuario_permiso up
JOIN conversacion.modulo m_origen ON m_origen.id_modulo = up.id_modulo
JOIN conversacion.modulo m_analytics ON m_analytics.codigo = 'analytics'
JOIN conversacion.usuario u ON u.id_usuario = up.id_usuario
JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
WHERE c.nombre = 'Dueño'
  AND m_origen.codigo = 'attractions'
  AND up.accion = 'ver'::conversacion.accion_t
  AND up.id_sitio IS NOT NULL
ON CONFLICT DO NOTHING;

COMMIT;
