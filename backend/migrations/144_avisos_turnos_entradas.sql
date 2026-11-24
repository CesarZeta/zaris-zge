-- Migración 144 — Avisos de turnos y entradas al vecino (PLAN_AVISOS_TURNOS_ENTRADAS.md, aprobado por
-- César el 2026-11-24).
--
-- Qué hace:
--   1. ck_ciudadano_aviso_tipo admite 'turno' y 'entrada' (los demás valores no cambian).
--   2. turnos.recordado_en y evento_reservas.recordado_en: momento en que se mandó el recordatorio del
--      día anterior. Vacío = todavía no; garantiza uno solo aunque la tarea corra varias veces.
--   3. Índices parciales para la tarea del recordatorio (los pendientes por fecha).
--
-- Lleva DROP CONSTRAINT: en prod la corre César en el SQL Editor de Supabase; en local, psql.
-- Re-aplicable. Va ANTES del código: sin las columnas, reprogramar un turno y editar un evento fallan.

ALTER TABLE ciudadano_aviso DROP CONSTRAINT IF EXISTS ck_ciudadano_aviso_tipo;
ALTER TABLE ciudadano_aviso ADD CONSTRAINT ck_ciudadano_aviso_tipo CHECK (tipo IN (
    'reclamo_estado', 'emergencia_estado', 'municipio', 'tramite_estado', 'tramite_pendiente',
    'tramite_pedido', 'turno', 'entrada'));

ALTER TABLE turnos          ADD COLUMN IF NOT EXISTS recordado_en TIMESTAMPTZ;
ALTER TABLE evento_reservas ADD COLUMN IF NOT EXISTS recordado_en TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_turnos_recordatorio ON turnos (id_municipio, fecha)
    WHERE activo AND estado = 'reservado' AND recordado_en IS NULL;
CREATE INDEX IF NOT EXISTS ix_evento_reservas_recordatorio ON evento_reservas (id_evento)
    WHERE activo AND recordado_en IS NULL;
