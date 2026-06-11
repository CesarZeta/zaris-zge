-- =============================================================================
-- Migracion 86 - Turnos: historia de atencion por turno cumplido
--
-- Decidido con el usuario 2026-06-11:
--   - tipo_prestacion.registra_atencion (BOOL): marca a NIVEL PRESTACION (no del
--     espacio) que al cumplir un turno de esa prestacion se registra una
--     atencion (intervencion + recomendaciones). Cubre prestaciones por agente
--     ("Odontologia por Dr. X") y por espacio ("Sala de Odontologia").
--   - turno_atencion: registro GENERICO de atencion (sirve para atencion medica
--     o regular), 1:1 con el turno, append-only de hecho (se crea al cumplir y
--     no hay endpoint de edicion). La "historia clinica" es el timeline de
--     estas filas por ciudadano, visible al cumplir (scope de turnos §33).
--
-- Solo DDL (los UPDATE que marcan las prestaciones de Odontologia van aparte,
-- ver feedback_apply_migration_parcial_aborta_todo). Idempotente.
-- =============================================================================

ALTER TABLE tipo_prestacion
  ADD COLUMN IF NOT EXISTS registra_atencion BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS turno_atencion (
    id_turno_atencion        SERIAL PRIMARY KEY,
    id_turno                 INTEGER NOT NULL UNIQUE REFERENCES turnos(id_turno),
    id_ciudadano             INTEGER NOT NULL REFERENCES ciudadanos(id_ciudadano),
    intervencion             TEXT NOT NULL,
    recomendaciones          TEXT,
    -- Estandar §10
    activo                   BOOLEAN DEFAULT TRUE,
    id_municipio             INTEGER,
    id_subarea               INTEGER,
    fecha_alta               TIMESTAMPTZ DEFAULT NOW(),
    fecha_modificacion       TIMESTAMPTZ DEFAULT NOW(),
    id_usuario_alta          INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion  INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

-- Lookup principal: historia de atenciones de un ciudadano.
CREATE INDEX IF NOT EXISTS idx_turno_atencion_ciudadano
  ON turno_atencion (id_ciudadano) WHERE activo = TRUE;

-- RLS sin politicas = deny-all para clientes anon; el backend (postgres dueno)
-- la bypassea (§21/§26). Dato de salud sensible (Ley 25.326).
ALTER TABLE turno_atencion ENABLE ROW LEVEL SECURITY;
