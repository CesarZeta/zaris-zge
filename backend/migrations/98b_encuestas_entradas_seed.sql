-- ============================================================================
-- 98b: Seed de la plantilla CSAT de Entradas (tipo='entradas').
--      Separado del DDL de la mig 98 a proposito: apply_migration es atomico
--      y un seed que falla revertiria tambien el DDL (§21,
--      feedback_apply_migration_parcial_aborta_todo). Requiere mig 98 aplicada
--      (ck_encuesta_plantilla_tipo debe admitir 'entradas').
--
--      Shape calcado del seed de la plantilla de turnos (mig 72): mismas
--      columnas de encuesta_plantilla / encuesta_pregunta, comentario de
--      texto libre con orden 99 (siempre ultimo en el form, que ordena por
--      rama, orden).
--
-- Idempotente: skip si ya existe una plantilla tipo='entradas'.
-- ============================================================================

DO $$
DECLARE
  v_pid INTEGER;
BEGIN
  IF EXISTS (SELECT 1 FROM encuesta_plantilla WHERE tipo = 'entradas') THEN
    RAISE NOTICE 'plantilla entradas ya existe, skip';
    RETURN;
  END IF;

  INSERT INTO encuesta_plantilla (nombre, descripcion, version, tipo, activo, id_municipio)
  VALUES ('Encuesta de asistencia a eventos',
          'Encuesta de satisfacción enviada al acreditar la asistencia a un evento con entrada.',
          '1.0', 'entradas', TRUE, 1)
  RETURNING id_encuesta_plantilla INTO v_pid;

  INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
  VALUES (v_pid, '¿Cómo calificás el evento al que asististe?', 'likert5', 1, 'todos', TRUE, 1);
  INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
  VALUES (v_pid, '¿Querés dejarnos un comentario?', 'texto_libre', 99, 'todos', FALSE, 1);

  RAISE NOTICE 'plantilla entradas creada id=%', v_pid;
END $$;
