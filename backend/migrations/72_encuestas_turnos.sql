-- =============================================================================
-- Migracion 72 - Encuestas: soporte para turnos en encuesta_envio
--
-- La encuesta de satisfaccion (mig 57) se disparaba SOLO al cerrar reclamos. Se
-- agrega una encuesta diferenciada para turnos de atencion (§33). El CHECK de
-- encuesta_plantilla.tipo ya admite 'turnos'; lo que faltaba en encuesta_envio:
--   1. id_reclamo deja de ser NOT NULL (un envio puede ser de turno, no reclamo).
--   2. nueva FK id_turno -> turnos(id_turno).
--   3. CHECK exactamente-uno de {id_reclamo, id_turno}. NOT VALID: las filas
--      viejas son todas reclamos y ya lo cumplen; no se valida retroactivo.
--   4. indice parcial sobre id_turno.
--
-- El seed de la plantilla tipo='turnos' va aparte (DO block / seed_turnos_demo)
-- para no abortar este DDL si el seed falla (apply_migration es atomico, §21).
-- Idempotente.
-- =============================================================================

ALTER TABLE encuesta_envio ALTER COLUMN id_reclamo DROP NOT NULL;

ALTER TABLE encuesta_envio
  ADD COLUMN IF NOT EXISTS id_turno INTEGER
  REFERENCES turnos(id_turno) ON DELETE RESTRICT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conrelid = 'encuesta_envio'::regclass
       AND conname = 'ck_encuesta_envio_origen'
  ) THEN
    ALTER TABLE encuesta_envio
      ADD CONSTRAINT ck_encuesta_envio_origen
      CHECK ( (id_reclamo IS NOT NULL)::int + (id_turno IS NOT NULL)::int = 1 )
      NOT VALID;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_encuesta_envio_turno
  ON encuesta_envio (id_turno) WHERE id_turno IS NOT NULL;

-- -----------------------------------------------------------------------------
-- Seed de la plantilla CSAT de turnos (idempotente: skip si ya existe una
-- plantilla tipo='turnos'). Espeja la estructura ramificada de la de reclamos.
-- -----------------------------------------------------------------------------
DO $$
DECLARE
  v_pid INTEGER;
BEGIN
  IF EXISTS (SELECT 1 FROM encuesta_plantilla WHERE tipo='turnos') THEN
    RAISE NOTICE 'plantilla turnos ya existe, skip';
    RETURN;
  END IF;

  INSERT INTO encuesta_plantilla (nombre, descripcion, version, tipo, activo, id_municipio)
  VALUES ('Satisfacción de atención (turnos)',
          'Encuesta de satisfacción enviada al cumplir un turno de atención.',
          '1.0', 'turnos', TRUE, 1)
  RETURNING id_encuesta_plantilla INTO v_pid;

  INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
  VALUES (v_pid, '¿Qué tan satisfecho estás con la atención que recibiste?', 'likert5', 1, 'todos', TRUE, 1);
  INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
  VALUES (v_pid, '¿El tiempo de espera te pareció razonable?', 'likert5', 2, 'todos', TRUE, 1);
  INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
  VALUES (v_pid, '¿Recomendarías este punto de atención a otros vecinos?', 'si_no', 3, 'satisfechos', TRUE, 1);
  INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
  VALUES (v_pid, '¿Querés que un responsable del municipio te contacte?', 'si_no', 3, 'insatisfechos', TRUE, 1);
  INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
  VALUES (v_pid, '¿Querés dejar algún comentario sobre la atención?', 'texto_libre', 99, 'todos', FALSE, 1);

  RAISE NOTICE 'plantilla turnos creada id=%', v_pid;
END $$;
