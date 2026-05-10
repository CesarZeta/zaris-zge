-- ════════════════════════════════════════════════════════════════════════════
-- ZARIS — Migración 23: Reasignar subáreas a sus áreas correctas
-- ════════════════════════════════════════════════════════════════════════════
-- Contexto:
--   El sistema heredó subáreas mal ubicadas bajo el área "Gobierno" cuando
--   conceptualmente pertenecen a otras áreas (principalmente Servicios
--   Públicos). Esto rompía la cadena área → subárea → tipo de reclamo.
--
-- Estrategia:
--   Para cada subárea con tipos asociados, calcular la moda de
--   tipo_reclamo.id_area entre esos tipos y reasignar subarea.id_area al
--   resultado. Idempotente — si ya está alineado, no hace nada.
--
-- Backup:
--   Ya existe la tabla _backup_subarea_2026_05_09 con el snapshot pre-update
--   en prod. Para revertir un id_subarea específico:
--     UPDATE subarea s SET id_area = b.id_area
--     FROM _backup_subarea_2026_05_09 b
--     WHERE s.id_subarea = b.id_subarea AND s.id_subarea = <id>;
-- ════════════════════════════════════════════════════════════════════════════

-- Snapshot defensivo (idempotente) por si falta en algún entorno
CREATE TABLE IF NOT EXISTS _backup_subarea_2026_05_09 AS
SELECT id_subarea, id_area, nombre, NOW() AS snapshot_at
FROM subarea WHERE FALSE;  -- shape only, sin filas todavía

INSERT INTO _backup_subarea_2026_05_09 (id_subarea, id_area, nombre, snapshot_at)
SELECT s.id_subarea, s.id_area, s.nombre, NOW()
FROM subarea s
WHERE s.activo
  AND NOT EXISTS (
    SELECT 1 FROM _backup_subarea_2026_05_09 b WHERE b.id_subarea = s.id_subarea
  );

-- UPDATE basado en moda
WITH moda AS (
  SELECT tr.id_subarea, tr.id_area AS id_area_moda,
         ROW_NUMBER() OVER (PARTITION BY tr.id_subarea
                            ORDER BY COUNT(*) DESC, tr.id_area) AS rn
  FROM tipo_reclamo tr
  WHERE tr.activo AND tr.id_area IS NOT NULL
  GROUP BY tr.id_subarea, tr.id_area
)
UPDATE subarea s
SET id_area = m.id_area_moda,
    fecha_modificacion = NOW()
FROM moda m
WHERE m.rn = 1
  AND s.id_subarea = m.id_subarea
  AND s.activo
  AND s.id_area <> m.id_area_moda;
