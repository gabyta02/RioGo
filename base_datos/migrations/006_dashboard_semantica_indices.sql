CREATE INDEX IF NOT EXISTS idx_msg_explo_usuario_embedding_hnsw
ON conversacion.mensaje_explorador
USING hnsw (embedding vector_cosine_ops)
WHERE rol = 'usuario' AND embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_msg_detalle_usuario_embedding_hnsw
ON conversacion.mensaje_detalle
USING hnsw (embedding vector_cosine_ops)
WHERE rol = 'usuario' AND embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_msg_explo_usuario_fecha
ON conversacion.mensaje_explorador (creado_en DESC)
WHERE rol = 'usuario';

CREATE INDEX IF NOT EXISTS idx_msg_detalle_usuario_fecha
ON conversacion.mensaje_detalle (creado_en DESC)
WHERE rol = 'usuario';
