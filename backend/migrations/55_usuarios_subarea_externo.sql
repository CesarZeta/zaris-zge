-- Migración 55 — usuarios.id_subarea + usuarios.es_externo
--
-- Contexto: el módulo Usuarios necesita que cada usuario tenga subárea
-- (obligatoria salvo usuarios externos). La regla de cierre directo de
-- reclamos (Sin asignar → Resuelto sin OT, solo supervisor de la misma
-- subárea del tipo de reclamo) depende de esta columna.
--
-- - id_subarea: FK lógica → subarea.id_subarea (sin FK física por
--   consistencia con el resto del proyecto que usa subarea sin FK fuerte).
--   Nullable en DB: los usuarios externos no llevan subárea, y el backfill
--   se hace por separado. La obligatoriedad la enforce el backend/form.
-- - es_externo: usuario que NO pertenece a una subárea del municipio
--   (ej. contratista, consultor externo). Cuando TRUE, subárea no requerida.
--
-- Idempotente.

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS id_subarea INTEGER;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS es_externo BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_usuarios_subarea ON usuarios (id_subarea);
