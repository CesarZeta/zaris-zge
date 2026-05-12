-- =============================================================================
-- Migracion 35 — Agenda sub-fase 3.B — Tokens para autoservicio publico
-- =============================================================================
-- eventos.token_publico         : UUID compartible que abre el form de reserva publica.
--                                 Se setea cuando admite_autoservicio=TRUE.
-- evento_reservas.token_reserva : UUID individual nominal para "Mi reserva"
--                                 (ver / cancelar sin login).
--
-- La extension pgcrypto provee gen_random_uuid(). Idempotente.
-- =============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE eventos
    ADD COLUMN IF NOT EXISTS token_publico UUID;

CREATE UNIQUE INDEX IF NOT EXISTS uq_eventos_token_publico
    ON eventos (token_publico)
    WHERE token_publico IS NOT NULL;

ALTER TABLE evento_reservas
    ADD COLUMN IF NOT EXISTS token_reserva UUID;

CREATE UNIQUE INDEX IF NOT EXISTS uq_evento_reservas_token_reserva
    ON evento_reservas (token_reserva)
    WHERE token_reserva IS NOT NULL;

-- Backfill: eventos activos con autoservicio que no tienen token todavia.
UPDATE eventos
   SET token_publico = gen_random_uuid()
 WHERE admite_autoservicio = TRUE
   AND token_publico IS NULL;

-- Backfill: reservas activas con origen autoservicio que no tienen token todavia.
UPDATE evento_reservas
   SET token_reserva = gen_random_uuid()
 WHERE origen = 'autoservicio'
   AND token_reserva IS NULL;

COMMIT;
