-- ============================================================================
-- 101b: Seed del ciclo de vida del tramite hacia el vecino (requiere mig 101).
--       Separado del DDL a proposito (apply_migration es atomico, §21).
--
--   1) Plantilla CSAT tipo='tramites' (el CHECK ya la admitia desde mig 57;
--      era andamiaje sin hook). Shape calcado de las plantillas de turnos
--      (mig 72) y entradas (98b): likert5 + texto libre con orden 99.
--   2) Claves de configuracion_general del timer de desistimiento (Config ->
--      Sistema §41). INSERT SIEMPRE con `activo` y `tipo` explicitos: prod las
--      tiene NOT NULL sin default (regla §21, ya mordio en 75b y 96).
--
-- Idempotente: la plantilla se saltea si existe; las claves con ON CONFLICT
-- sobre `clave` (UNIQUE en ambos entornos).
-- ============================================================================

DO $$
DECLARE
  v_pid INTEGER;
BEGIN
  IF EXISTS (SELECT 1 FROM encuesta_plantilla WHERE tipo = 'tramites') THEN
    RAISE NOTICE 'plantilla tramites ya existe, skip';
  ELSE
    INSERT INTO encuesta_plantilla (nombre, descripcion, version, tipo, activo, id_municipio)
    VALUES ('Encuesta de satisfacción de trámites',
            'Encuesta enviada al vecino cuando su trámite termina (aprobado o rechazado).',
            '1.0', 'tramites', TRUE, 1)
    RETURNING id_encuesta_plantilla INTO v_pid;

    INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
    VALUES (v_pid, '¿Cómo calificás la gestión de tu trámite?', 'likert5', 1, 'todos', TRUE, 1);
    INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
    VALUES (v_pid, '¿Querés dejarnos un comentario sobre el trámite?', 'texto_libre', 99, 'todos', FALSE, 1);

    RAISE NOTICE 'plantilla tramites creada id=%', v_pid;
  END IF;
END $$;

INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
VALUES
  ('tramite_desistimiento_activo', 'true', 'boolean',
   'Timer de desistimiento de trámites a la espera del vecino (avisos escalonados + desistido automático). false = solo se archiva por inactividad como antes.', TRUE),
  ('tramite_sla_dias_default', '30', 'integer',
   'SLA (días) por defecto de un trámite cuando el tipo no define sla_dias. Vencido el SLA arranca la cuenta de avisos en los estados que esperan al vecino.', TRUE),
  ('tramite_desistimiento_aviso1_dias', '30', 'integer',
   'Días después de vencido el SLA (o de entrar al estado de espera) para el 1er aviso al vecino de trámite pendiente.', TRUE),
  ('tramite_desistimiento_aviso2_dias', '60', 'integer',
   'Días después de vencido el SLA para el 2do aviso (recordatorio).', TRUE),
  ('tramite_desistimiento_dias', '90', 'integer',
   'Días después de vencido el SLA en que el trámite pendiente del vecino se marca DESISTIDO automáticamente.', TRUE),
  ('tramite_desistimiento_aviso_final_horas', '72', 'integer',
   'Horas antes del desistimiento para el último aviso al vecino.', TRUE)
ON CONFLICT (clave) DO NOTHING;
