-- Migración 70: turnos contra lugar atendido (espacios_agenda)
--
-- Hasta ahora un turno se reservaba SIEMPRE contra un agente (id_agente NOT NULL).
-- Ahora puede reservarse contra un agente O contra un espacio atendido (ventanilla).
-- La capacidad del espacio = su disponibilidad efectiva (unión de los agentes
-- vinculados vía espacio_agentes), que ya resuelve services/agenda.py.
--
-- Polimorfismo: exactamente uno de {id_agente, id_espacio} poblado.
-- La ocupación espejo usa tipo_recurso='agente' o 'espacio' según corresponda.
-- En prod hay 0 turnos al aplicar esto, así que no hay backfill. Idempotente.

ALTER TABLE turnos
  ADD COLUMN IF NOT EXISTS id_espacio INTEGER REFERENCES espacios_agenda(id_espacio) ON DELETE SET NULL;

-- id_agente deja de ser obligatorio (puede ser un turno contra espacio).
ALTER TABLE turnos
  ALTER COLUMN id_agente DROP NOT NULL;

-- Exactamente uno de los dos recursos.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'turnos'::regclass AND conname = 'ck_turnos_recurso'
  ) THEN
    ALTER TABLE turnos
      ADD CONSTRAINT ck_turnos_recurso
      CHECK ((id_agente IS NOT NULL)::int + (id_espacio IS NOT NULL)::int = 1);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_turnos_espacio
  ON turnos (id_espacio, fecha) WHERE activo = TRUE AND id_espacio IS NOT NULL;
