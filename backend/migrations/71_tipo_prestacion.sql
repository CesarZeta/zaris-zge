-- =============================================================================
-- Migracion 71 - Turnos: tipo_servicio_turno -> tipo_prestacion (recurso embebido)
--
-- Replanteo del modulo Turnos (decidido con el usuario 2026-05-28):
--   Antes: el "tipo de servicio" definia solo la duracion; el recurso (agente o
--   espacio) se elegia suelto en cada reserva.
--   Ahora: una PRESTACION define de una vez el recurso fijo (un agente O un
--   lugar de atencion), su duracion y su CLASE (atencion de personas vs.
--   reserva de un espacio). El turno se reserva eligiendo prestacion + slot;
--   la disponibilidad efectiva del recurso (horario - feriados - novedades, §27)
--   define los slots. El recurso de la prestacion se COPIA al turno al reservar.
--
-- Esta migracion solo hace DDL (rename + columnas + CHECKs). Los seeds de
-- prestaciones de ejemplo van en seed_turnos_demo.py (apply_migration es
-- atomico: un INSERT que falle abortaria el rename — ver memoria
-- feedback_apply_migration_parcial_aborta_todo).
--
-- Las filas viejas de tipo_servicio_turno quedan SIN recurso (NULL). Por eso el
-- CHECK de "exactamente un recurso" se agrega NOT VALID: aplica a filas nuevas
-- pero no valida las existentes. El seed las soft-deletea (activo=FALSE).
--
-- Idempotente: cada paso chequea su precondicion antes de actuar.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Rename tabla + PK + FK en turnos (solo si todavia no se hizo)
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.tipo_servicio_turno') IS NOT NULL
     AND to_regclass('public.tipo_prestacion') IS NULL THEN
    ALTER TABLE tipo_servicio_turno RENAME TO tipo_prestacion;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='tipo_prestacion' AND column_name='id_tipo_servicio_turno') THEN
    ALTER TABLE tipo_prestacion RENAME COLUMN id_tipo_servicio_turno TO id_tipo_prestacion;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='turnos' AND column_name='id_tipo_servicio_turno') THEN
    ALTER TABLE turnos RENAME COLUMN id_tipo_servicio_turno TO id_tipo_prestacion;
  END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 2. Columnas nuevas en tipo_prestacion: clase + recurso polimorfico
-- -----------------------------------------------------------------------------
ALTER TABLE tipo_prestacion
  ADD COLUMN IF NOT EXISTS clase        VARCHAR(20) NOT NULL DEFAULT 'atencion',
  ADD COLUMN IF NOT EXISTS tipo_recurso VARCHAR(10),
  ADD COLUMN IF NOT EXISTS id_agente    INTEGER REFERENCES agentes(id_agente)       ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS id_espacio   INTEGER REFERENCES espacios_agenda(id_espacio) ON DELETE RESTRICT;

-- clase valida
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid='tipo_prestacion'::regclass AND conname='ck_tipo_prestacion_clase') THEN
    ALTER TABLE tipo_prestacion
      ADD CONSTRAINT ck_tipo_prestacion_clase
      CHECK (clase IN ('atencion','reserva_espacio'));
  END IF;
END $$;

-- tipo_recurso valido (permite NULL en filas viejas)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid='tipo_prestacion'::regclass AND conname='ck_tipo_prestacion_tipo_recurso') THEN
    ALTER TABLE tipo_prestacion
      ADD CONSTRAINT ck_tipo_prestacion_tipo_recurso
      CHECK (tipo_recurso IS NULL OR tipo_recurso IN ('agente','espacio'));
  END IF;
END $$;

-- Exactamente un recurso, coherente con tipo_recurso. NOT VALID: aplica a filas
-- nuevas; las viejas (sin recurso) las soft-deletea el seed.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid='tipo_prestacion'::regclass AND conname='ck_tipo_prestacion_recurso') THEN
    ALTER TABLE tipo_prestacion
      ADD CONSTRAINT ck_tipo_prestacion_recurso
      CHECK (
        (id_agente IS NOT NULL)::int + (id_espacio IS NOT NULL)::int = 1
        AND (
          (tipo_recurso = 'agente'  AND id_agente  IS NOT NULL) OR
          (tipo_recurso = 'espacio' AND id_espacio IS NOT NULL)
        )
      ) NOT VALID;
  END IF;
END $$;

-- reserva_espacio solo apunta a un espacio. NOT VALID por las filas viejas.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid='tipo_prestacion'::regclass AND conname='ck_tipo_prestacion_reserva_espacio') THEN
    ALTER TABLE tipo_prestacion
      ADD CONSTRAINT ck_tipo_prestacion_reserva_espacio
      CHECK (clase <> 'reserva_espacio' OR tipo_recurso = 'espacio') NOT VALID;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_tipo_prestacion_clase
  ON tipo_prestacion (clase) WHERE activo = TRUE;
