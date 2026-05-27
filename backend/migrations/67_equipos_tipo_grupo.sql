-- Migración 67: tipo_grupo en equipos
--
-- Distingue dos clases de grupo:
--   'mesa_tramites'    → recibe pases de Trámites. Cualquier integrante toma de
--                        su "Mi bandeja". NO se agenda → no lleva horario.
--   'trabajo_reclamos' → atiende reclamos/OT. Su disponibilidad alimenta la
--                        Agenda (vía disponibilidad_recurso, tipo_recurso='equipo').
--                        Lleva días+horarios (cargados como franjas, igual que agentes).
--
-- Default 'mesa_tramites' porque los grupos demo creados en la sesión 2026-05-27
-- son mesas de entrada de trámites. Idempotente.

ALTER TABLE equipos
  ADD COLUMN IF NOT EXISTS tipo_grupo VARCHAR(20) NOT NULL DEFAULT 'mesa_tramites';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'equipos'::regclass AND conname = 'ck_equipo_tipo_grupo'
  ) THEN
    ALTER TABLE equipos
      ADD CONSTRAINT ck_equipo_tipo_grupo
      CHECK (tipo_grupo IN ('mesa_tramites', 'trabajo_reclamos'));
  END IF;
END $$;

-- Subárea obligatoria solo para grupos de trabajo (reclamos/OT): la necesitan
-- para el scope de Agenda/OT. La mesa de trámites puede recibir pases sin subárea.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'equipos'::regclass AND conname = 'ck_equipo_subarea_reclamos'
  ) THEN
    ALTER TABLE equipos
      ADD CONSTRAINT ck_equipo_subarea_reclamos
      CHECK (tipo_grupo <> 'trabajo_reclamos' OR id_subarea IS NOT NULL);
  END IF;
END $$;
