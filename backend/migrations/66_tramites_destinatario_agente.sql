-- Migracion 66: destinatario directo de tramite = agente
--
-- Hasta ahora un tramite se asignaba a una subarea o equipo (colectivo) y un
-- agente lo "tomaba". Esta migracion habilita pasar un tramite DIRECTAMENTE a
-- un agente (persona): aparece en SU bandeja y nadie mas puede tomarlo.
-- Fiel al modelo Mesa Digital (origin/destination con tipo 'user').
--
-- Cambios:
--   1. Nueva columna tramite.id_agente_actual (FK -> agentes, nullable).
--   2. CHECK tramite_destinatario_actual_tipo_check: agrega 'agente'.
--   3. CHECK ck_tramite_destinatario: 4 ramas (NULL | subarea | equipo | agente),
--      exactamente una FK poblada por tipo.
--
-- Idempotente. Aplicar en local Y prod.

BEGIN;

-- 1. Columna nueva
ALTER TABLE tramite
    ADD COLUMN IF NOT EXISTS id_agente_actual INTEGER
        REFERENCES agentes(id_agente) ON DELETE SET NULL;

-- 2. CHECK del tipo: incluir 'agente'
ALTER TABLE tramite DROP CONSTRAINT IF EXISTS tramite_destinatario_actual_tipo_check;
ALTER TABLE tramite ADD CONSTRAINT tramite_destinatario_actual_tipo_check
    CHECK (destinatario_actual_tipo IS NULL
           OR destinatario_actual_tipo::text = ANY (ARRAY['subarea','equipo','agente']::text[]));

-- 3. CHECK de consistencia: exactamente una FK por tipo
ALTER TABLE tramite DROP CONSTRAINT IF EXISTS ck_tramite_destinatario;
ALTER TABLE tramite ADD CONSTRAINT ck_tramite_destinatario CHECK (
       (destinatario_actual_tipo IS NULL
            AND id_subarea_actual IS NULL AND id_equipo_actual IS NULL AND id_agente_actual IS NULL)
    OR (destinatario_actual_tipo::text = 'subarea'
            AND id_subarea_actual IS NOT NULL AND id_equipo_actual IS NULL AND id_agente_actual IS NULL)
    OR (destinatario_actual_tipo::text = 'equipo'
            AND id_equipo_actual IS NOT NULL AND id_subarea_actual IS NULL AND id_agente_actual IS NULL)
    OR (destinatario_actual_tipo::text = 'agente'
            AND id_agente_actual IS NOT NULL AND id_subarea_actual IS NULL AND id_equipo_actual IS NULL)
);

-- Indice para resolver "mi bandeja por agente destinatario"
CREATE INDEX IF NOT EXISTS idx_tramite_agente_actual
    ON tramite (id_agente_actual) WHERE id_agente_actual IS NOT NULL AND activo = TRUE;

COMMIT;
