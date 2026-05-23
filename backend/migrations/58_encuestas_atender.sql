-- Mig 58: Agregar tracking de atencion a respuestas insatisfechas.
-- Permite marcar cuando un agente contacto al vecino que solicito contacto
-- (encuesta_respuesta.solicita_contacto = TRUE).
-- Idempotente: ADD COLUMN IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.

BEGIN;

ALTER TABLE encuesta_respuesta
  ADD COLUMN IF NOT EXISTS atendida BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE encuesta_respuesta
  ADD COLUMN IF NOT EXISTS atendida_por INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

ALTER TABLE encuesta_respuesta
  ADD COLUMN IF NOT EXISTS fecha_atendida TIMESTAMPTZ;

-- Indice parcial para la cola de pendientes de contacto (las mas urgentes).
CREATE INDEX IF NOT EXISTS idx_encuesta_respuesta_pendientes
  ON encuesta_respuesta (solicita_contacto, atendida)
  WHERE solicita_contacto = TRUE AND atendida = FALSE;

COMMIT;
