-- Migracion 121 — Asignacion automatica de reclamos GENERAL del municipio (2026-10-23)
--
-- Decision de Cesar (2026-10-23): la asignacion automatica se prende para todo
-- el municipio en Configuracion -> Sistema (clave reclamos_asignacion_automatica)
-- y cada gestion puede ser la EXCEPCION que asigna a mano (Maestros -> Subareas).
-- Regla: una gestion asigna sola = general prendida Y la gestion sin la excepcion.
-- Reemplaza al tilde por gestion de la mig 114 (subarea.asignacion_automatica).
--
-- Este archivo es solo DDL; la clave y la traduccion del estado anterior van en
-- la 121b. subarea.asignacion_automatica queda sin uso y se borra en una mig
-- posterior, cuando prod corra el codigo nuevo (el backend viejo todavia la lee).
--
-- Idempotente. Verificado antes de aplicar (2026-10-23): ninguna DB tiene la
-- columna ni la clave; en prod solo Alumbrado Publico tiene el tilde viejo.

ALTER TABLE subarea ADD COLUMN IF NOT EXISTS asignacion_manual BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN subarea.asignacion_manual IS
  'TRUE = esta gestion asigna sus reclamos a mano aunque la asignacion automatica general este prendida (mig 121).';
COMMENT ON COLUMN subarea.asignacion_automatica IS
  'SIN USO desde la mig 121 (la reemplaza asignacion_manual + la clave reclamos_asignacion_automatica). Se borra en una mig posterior.';
