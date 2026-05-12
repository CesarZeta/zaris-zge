-- =============================================================================
-- Migracion 36 — Fix schema drift: defaults de `activo` en tablas Agenda (prod)
-- =============================================================================
-- Prod tenia las tablas Agenda con `activo NOT NULL` SIN default, mientras que
-- local + las migraciones originales (30-34) las creaban con `DEFAULT TRUE`.
-- El backend hace INSERTs que confian en el default; sin el, fallaba en prod
-- con "null value in column activo violates not-null constraint" (HTTP 500).
--
-- Aplicada en prod el 2026-05-12 via MCP. Local NO necesita correrla porque
-- ya tenia los defaults desde el dia 1.
--
-- Idempotente: ALTER ... SET DEFAULT no falla si el default ya existe.
-- =============================================================================

BEGIN;

ALTER TABLE municipios          ALTER COLUMN activo SET DEFAULT TRUE;
ALTER TABLE estado_evento       ALTER COLUMN activo SET DEFAULT TRUE;
ALTER TABLE estado_reserva      ALTER COLUMN activo SET DEFAULT TRUE;
ALTER TABLE eventos             ALTER COLUMN activo SET DEFAULT TRUE;
ALTER TABLE evento_encargados   ALTER COLUMN activo SET DEFAULT TRUE;
ALTER TABLE evento_reservas     ALTER COLUMN activo SET DEFAULT TRUE;
ALTER TABLE ocupaciones         ALTER COLUMN activo SET DEFAULT TRUE;

COMMIT;
