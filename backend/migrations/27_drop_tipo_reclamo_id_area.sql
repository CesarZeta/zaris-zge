-- Migración 27 — Drop columna redundante tipo_reclamo.id_area
--
-- Contexto: desde la migración 24 (re-seed total) la fuente de verdad del
-- área de un tipo de reclamo es subarea.id_area (vía tr.id_subarea → s.id_area).
-- La columna tipo_reclamo.id_area quedó como espejo histórico y al cierre
-- de mig 26 ya está sincronizada en prod (0 nulls). Mantenerla obliga a
-- doble escritura y abre la puerta a inconsistencias.
--
-- Backend ya consulta exclusivamente subarea.id_area (reclamos.py: catalogo_tipos,
-- crear_reclamo; ordenes_trabajo.py: JOINs vía r.id_area que vive en reclamos,
-- no en tipo_reclamo). El frontend admin_tablas solo expone id_subarea en el
-- form de tipo_reclamo — id_area ya no es editable visualmente.
--
-- Sin vistas ni triggers dependientes (verificado pg_views + pg_trigger).
-- FK tipo_reclamo_id_area_fkey se elimina automáticamente al dropear la columna.
--
-- Snapshot: no es necesario, los valores son derivables 100% desde subarea.id_area
-- (los pocos huérfanos con tr.id_subarea NULL nunca podrán recuperarse a un id_area
-- válido por definición; pierden la info "fantasma" sin impacto en consultas).
--
-- Aplicada en: local + prod 2026-05-10.

BEGIN;

DROP INDEX IF EXISTS idx_tipo_reclamo_area;
ALTER TABLE tipo_reclamo DROP COLUMN IF EXISTS id_area;

COMMIT;
