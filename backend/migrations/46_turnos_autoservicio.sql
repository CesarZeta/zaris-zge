-- =============================================================================
-- Migracion 46 - Turnos autoservicio: token publico + origen
--
-- Habilita que un ciudadano reserve un turno sin login (autoservicio publico).
-- A diferencia de los eventos (fecha/hora fija), un turno requiere elegir un
-- slot libre cruzando disponibilidad_recurso con ocupaciones. El backend
-- publico (/api/v1/turnos/publico/*) hace ese calculo.
--
-- Cambios:
--   - turnos.token_turno  : UUID no enumerable para que el ciudadano consulte
--                           o cancele su turno sin JWT (espejo de
--                           evento_reservas.token_reserva).
--   - turnos.origen       : 'backoffice' (default, alta por operador) o
--                           'autoservicio' (alta por el ciudadano).
--   - Backfill: token_turno = gen_random_uuid() para las filas existentes.
--
-- Requiere pgcrypto (ya creada en mig 35). Idempotente.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE turnos
  ADD COLUMN IF NOT EXISTS token_turno UUID,
  ADD COLUMN IF NOT EXISTS origen VARCHAR(15) NOT NULL DEFAULT 'backoffice';

-- Backfill de filas existentes sin token.
UPDATE turnos SET token_turno = gen_random_uuid() WHERE token_turno IS NULL;

-- Una vez backfilleado, el token es obligatorio y unico.
ALTER TABLE turnos ALTER COLUMN token_turno SET NOT NULL;
ALTER TABLE turnos ALTER COLUMN token_turno SET DEFAULT gen_random_uuid();

CREATE UNIQUE INDEX IF NOT EXISTS idx_turnos_token ON turnos (token_turno);

ALTER TABLE turnos DROP CONSTRAINT IF EXISTS ck_turnos_origen;
ALTER TABLE turnos ADD CONSTRAINT ck_turnos_origen
  CHECK (origen IN ('backoffice', 'autoservicio'));
