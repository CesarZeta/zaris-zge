-- =============================================================================
-- Migracion 30 — Agenda sub-fase 1.A — Municipios + ALTER tipo_reclamo
-- =============================================================================
-- Contexto: primer paso del modulo Agenda. Crea la tabla municipios (faltaba en
-- prod y local) y agrega a tipo_reclamo dos columnas que la agenda necesita:
--   * duracion_estimada_min : cuanto bloquea el calendario del agente/equipo
--   * asignacion_a          : 'agente' o 'equipo' (default 'agente')
-- Es idempotente — se puede correr multiples veces sin romper.
-- =============================================================================

BEGIN;

-- 1) municipios -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS municipios (
    id_municipio        SERIAL PRIMARY KEY,
    nombre              VARCHAR(120) NOT NULL,
    provincia           VARCHAR(80),
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

-- Seed minimo
INSERT INTO municipios (id_municipio, nombre, provincia)
VALUES (1, 'Municipio Demo', 'Buenos Aires')
ON CONFLICT (id_municipio) DO NOTHING;

-- Reajustar secuencia si quedo desfasada (idempotencia)
SELECT setval('municipios_id_municipio_seq',
              GREATEST(COALESCE((SELECT MAX(id_municipio) FROM municipios), 1), 1),
              true);

-- 2) ALTER tipo_reclamo ----------------------------------------------------
ALTER TABLE tipo_reclamo
    ADD COLUMN IF NOT EXISTS duracion_estimada_min INTEGER NOT NULL DEFAULT 60;

ALTER TABLE tipo_reclamo
    ADD COLUMN IF NOT EXISTS asignacion_a VARCHAR(10) NOT NULL DEFAULT 'agente';

-- CHECK constraint de asignacion_a (drop+add para idempotencia)
ALTER TABLE tipo_reclamo DROP CONSTRAINT IF EXISTS ck_tipo_reclamo_asignacion_a;
ALTER TABLE tipo_reclamo
    ADD CONSTRAINT ck_tipo_reclamo_asignacion_a
    CHECK (asignacion_a IN ('agente','equipo'));

COMMIT;
