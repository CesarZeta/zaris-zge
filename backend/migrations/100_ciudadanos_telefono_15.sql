-- ============================================================================
-- 100: ciudadanos.telefono VARCHAR(10) -> VARCHAR(15) en prod (drift §24).
--
-- Cazado 2026-08-30 al smokear PUT /api/v1/publico/perfil contra prod: local
-- tiene telefono VARCHAR(15) (y los schemas Pydantic del BUC validan hasta 15),
-- pero prod quedo en VARCHAR(10) -> cualquier telefono de 11+ digitos (con
-- codigo de pais, "549..." por ejemplo) rompe con StringDataRightTruncation
-- (500) tanto en el perfil del vecino como en el backoffice.
--
-- Solo ensancha (no destructivo; los 610 activos de prod tienen <= 10 chars).
-- En local es no-op (ya esta en 15). Sin cambios de RLS/indices.
-- ============================================================================

ALTER TABLE ciudadanos
    ALTER COLUMN telefono TYPE VARCHAR(15);
