-- Migración 25 — Vínculo reclamo ↔ empresa (1:1, opcional)
--
-- Permite registrar que un reclamo se hace "a nombre de" una empresa que el
-- ciudadano representa. La N:M ciudadano↔empresa ya existe en
-- ciudadano_empresa con id_tipo_representacion; esta columna en reclamos es
-- 1:1 (un reclamo es a nombre de máximo una empresa, o ninguna).
--
-- Idempotente: usa IF NOT EXISTS para columna e índice.

ALTER TABLE reclamos
    ADD COLUMN IF NOT EXISTS id_empresa INTEGER NULL
        REFERENCES empresas(id_empresa) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_reclamos_id_empresa
    ON reclamos(id_empresa)
    WHERE id_empresa IS NOT NULL;

COMMENT ON COLUMN reclamos.id_empresa IS
    'Empresa a cuyo nombre se hace el reclamo. NULL = reclamo a título personal del ciudadano. La empresa debe estar entre las que el ciudadano representa (validación en backend al crear).';
