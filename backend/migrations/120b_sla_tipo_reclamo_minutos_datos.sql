-- Migracion 120b — Backfill del SLA en minutos (2026-10-23). Datos de la 120,
-- en archivo aparte (apply_migration es atomico: un fallo de datos no debe
-- revertir el DDL).
--
-- sla_minutos = sla_dias * 1440 en los tipos que todavia no lo tienen. El
-- trigger trg_tipo_reclamo_sla_sync vuelve a derivar sla_dias del valor nuevo
-- (mismo numero). Idempotente.

UPDATE tipo_reclamo
   SET sla_minutos = sla_dias * 1440
 WHERE sla_minutos IS NULL AND sla_dias IS NOT NULL;
