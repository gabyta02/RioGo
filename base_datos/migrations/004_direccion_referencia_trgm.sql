-- Índice trigram para referencia_adicional en búsqueda por referencia
CREATE INDEX IF NOT EXISTS idx_direccion_referencia_trgm
    ON turismo.direccion
    USING gin (
        translate(
            lower(COALESCE(referencia_adicional, '')),
            'áéíóúüñàèìòùâêîôûãõç',
            'aeiouunaeiouaeiouaoc'
        ) gin_trgm_ops
    );
