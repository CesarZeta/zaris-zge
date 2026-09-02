-- ============================================================================
-- Migracion 103 — Ubicacion de atencion (Fase 1 del plan PLAN_MODULO_ATENCION.md)
--
-- La UBICACION es el lugar fisico (espacios_agenda) donde se gestiona la
-- atencion de un turno. Hoy un turno por AGENTE no sabe donde se atiende
-- (turnos.id_agente XOR id_espacio es el RECURSO, no el lugar). Esta migracion
-- agrega la ubicacion como dato propio:
--
--   - tipo_prestacion.id_espacio_ubicacion: donde se atiende esta prestacion.
--     Para prestaciones cuyo recurso ya es un espacio, es ese mismo espacio.
--   - turnos.id_espacio_ubicacion: COPIA de la ubicacion de la prestacion al
--     reservar (turno autocontenido, mismo criterio que el recurso en mig 70).
--
-- Backfill: solo las filas cuyo recurso es un espacio (la ubicacion es obvia).
-- Los turnos/prestaciones por agente quedan NULL hasta que se cargue la
-- ubicacion en el form de Prestaciones ("Sin ubicacion" en el frontend).
--
-- OJO NOT VALID (feedback_check_not_valid_se_evalua_al_update): los CHECK
-- ck_tipo_prestacion_recurso / ck_tipo_prestacion_reserva_espacio son NOT
-- VALID y se re-evaluan en cada UPDATE. El WHERE del backfill exige
-- id_agente IS NULL para tocar SOLO filas que ya los satisfacen.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS + backfill con guarda IS NULL.
-- Aplicar en LOCAL y PROD en la misma sesion (2026-09-01).
-- ============================================================================

ALTER TABLE tipo_prestacion
    ADD COLUMN IF NOT EXISTS id_espacio_ubicacion INTEGER
    REFERENCES espacios_agenda(id_espacio) ON DELETE SET NULL;

ALTER TABLE turnos
    ADD COLUMN IF NOT EXISTS id_espacio_ubicacion INTEGER
    REFERENCES espacios_agenda(id_espacio) ON DELETE SET NULL;

-- Backfill prestaciones cuyo recurso ya es un espacio (id_agente IS NULL para
-- no despertar los CHECK NOT VALID sobre filas viejas sucias).
UPDATE tipo_prestacion
SET id_espacio_ubicacion = id_espacio
WHERE tipo_recurso = 'espacio'
  AND id_espacio IS NOT NULL
  AND id_agente IS NULL
  AND id_espacio_ubicacion IS NULL;

-- Backfill turnos cuyo recurso ya es un espacio.
UPDATE turnos
SET id_espacio_ubicacion = id_espacio
WHERE id_espacio IS NOT NULL
  AND id_agente IS NULL
  AND id_espacio_ubicacion IS NULL;

-- Listados y colero consultan "turnos de la ubicacion X en la fecha Y".
CREATE INDEX IF NOT EXISTS ix_turnos_ubicacion_fecha
    ON turnos (id_espacio_ubicacion, fecha);
