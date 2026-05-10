-- Migración 29 — agregar agentes.es_auditor (faltaba en prod)
--
-- En local la columna fue agregada manualmente en alguna sesión sin migración
-- formal. Prod nunca la recibió. Esta migración la formaliza:
--   - en local: idempotente (ya existe).
--   - en prod: la crea con default FALSE.
--
-- El backend /ot/auditor/me la consulta para validar que un agente sea
-- auditor antes de mostrar OTs de auditoría (ver memoria
-- feedback_vincular_por_id y CLAUDE.md §18).

BEGIN;

ALTER TABLE agentes
    ADD COLUMN IF NOT EXISTS es_auditor BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_agentes_es_auditor ON agentes(es_auditor)
    WHERE es_auditor = TRUE;

COMMIT;
