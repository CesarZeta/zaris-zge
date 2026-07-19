-- ============================================================================
-- 98: Encuestas CSAT para Entradas (reservas de eventos).
--     Tercera rama del polimorfismo de encuesta_envio (patron mig 72, que sumo
--     id_turno): nueva FK id_evento_reserva -> evento_reservas. El disparo lo
--     hace el backend al acreditar la entrada (la reserva pasa a 'asistio' en
--     agenda_v2._patch_reserva_estado), best-effort tras el commit — cubre
--     tanto el PATCH /reservas/{id}/asistio como el POST /reservas/acreditar-qr.
--
--     1. ADD COLUMN id_evento_reserva. ON DELETE RESTRICT: copia el criterio
--        de la FK id_turno de mig 72 (verificado en prod 2026-07-18: la FK
--        encuesta_envio_id_turno_fkey es RESTRICT, igual que id_reclamo).
--     2. ck_encuesta_envio_origen pasa de XOR de 2 a exactamente-uno de 3.
--        Se re-crea NOT VALID como el original (las filas viejas ya cumplen:
--        todas tienen exactamente un origen y la columna nueva nace NULL).
--     3. ck_encuesta_plantilla_tipo (mig 57) no admitia 'entradas'; se amplia
--        o el seed de 98b violaria el CHECK.
--     4. Indice parcial sobre id_evento_reserva (espejo de idx_encuesta_envio_turno).
--
--     El seed de la plantilla tipo='entradas' va SEPARADO en
--     98b_encuestas_entradas_seed.sql (apply_migration es atomico, §21:
--     un seed que falla revertiria tambien este DDL).
--
-- Idempotente. Sin cambios de RLS (tablas existentes).
-- ============================================================================

ALTER TABLE encuesta_envio
  ADD COLUMN IF NOT EXISTS id_evento_reserva INTEGER
  REFERENCES evento_reservas(id_evento_reserva) ON DELETE RESTRICT;

-- XOR de 3: exactamente uno de {id_reclamo, id_turno, id_evento_reserva}.
-- No hay ALTER de CHECK en Postgres: DROP IF EXISTS + ADD. El par es
-- idempotente al re-correr el archivo completo. OJO: aunque sea NOT VALID,
-- el CHECK se evalua en INSERT/UPDATE de cualquier fila, tambien las viejas
-- (feedback_check_not_valid_se_evalua_al_update) — las filas existentes ya
-- lo cumplen, no hace falta backfill.
ALTER TABLE encuesta_envio DROP CONSTRAINT IF EXISTS ck_encuesta_envio_origen;
ALTER TABLE encuesta_envio
  ADD CONSTRAINT ck_encuesta_envio_origen
  CHECK ( (id_reclamo IS NOT NULL)::int
        + (id_turno IS NOT NULL)::int
        + (id_evento_reserva IS NOT NULL)::int = 1 )
  NOT VALID;

-- Ampliar el catalogo de tipos de plantilla con 'entradas'. Los valores
-- existentes en prod/local estan todos dentro del set (verificado 2026-07-18),
-- por eso este ADD puede validar sin NOT VALID.
ALTER TABLE encuesta_plantilla DROP CONSTRAINT IF EXISTS ck_encuesta_plantilla_tipo;
ALTER TABLE encuesta_plantilla
  ADD CONSTRAINT ck_encuesta_plantilla_tipo
  CHECK (tipo IN ('reclamos', 'tramites', 'turnos', 'entradas'));

CREATE INDEX IF NOT EXISTS idx_encuesta_envio_evento_reserva
  ON encuesta_envio (id_evento_reserva) WHERE id_evento_reserva IS NOT NULL;
