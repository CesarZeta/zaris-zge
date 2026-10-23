-- Migracion 122 — Limpieza de dos columnas sin uso (2026-10-23, OK de Cesar)
--
-- 1. subarea.asignacion_automatica: el tilde por gestion de la mig 114. Desde la
--    121 la asignacion automatica es general (clave reclamos_asignacion_automatica)
--    con la excepcion subarea.asignacion_manual; prod corre el codigo nuevo desde
--    4c9f5ee (verificado por el marcador de OpenAPI) y nadie la lee.
-- 2. tipo_reclamo.duracion_estimada_min: lo que se reservaba en la agenda al
--    asignar la OT; sin uso desde que los reclamos no se agendan (2026-10-21) y
--    fuera del formulario de Maestros desde el 2026-10-23.
--
-- Verificado antes de aplicar (2026-10-23): ninguna vista, funcion ni constraint
-- depende de las dos columnas (solo sus DEFAULT) y ningun codigo de los tres repos
-- las lee. Respaldo de los valores en prod: _backup_subarea_asignacion_2026_10_23 y
-- _backup_tipo_reclamo_sla_2026_10_23. Idempotente.

ALTER TABLE subarea DROP COLUMN IF EXISTS asignacion_automatica;

ALTER TABLE tipo_reclamo DROP COLUMN IF EXISTS duracion_estimada_min;
