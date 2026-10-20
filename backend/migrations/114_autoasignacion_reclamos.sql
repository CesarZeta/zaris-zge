-- Migracion 114 — Autoasignacion de reclamos por gestion (2026-10-20)
--
-- Decision de Cesar (cuestionario 2026-10-20): una gestion (subarea) puede
-- asignar sola los reclamos que entran, sin mesa ni supervisor. Candidatos:
-- agentes de nivel Gestion y cuadrillas con integrantes de esa gestion (segun
-- tipo_reclamo.asignacion_a); por disponibilidad (si un dia esta completo pasa
-- al siguiente), despues menor carga, despues rotacion. Motor en
-- services/autoasignacion.py.
--
-- 1. subarea.asignacion_automatica: el tilde (solo admin, Maestros → Subareas).
-- 2. ordenes_trabajo.id_supervisor_asigna admite NULL: una OT autoasignada no
--    tiene supervisor que la asigno (la FK a usuarios sigue igual).
-- 3. ordenes_trabajo.asignacion_automatica: marca la OT creada por el motor
--    (historial, mesa y BI la distinguen de una asignacion manual).
--
-- Idempotente. Verificado antes de aplicar (2026-10-20): ninguna de las dos
-- DBs tiene las columnas nuevas e id_supervisor_asigna es NOT NULL en ambas.

ALTER TABLE subarea ADD COLUMN IF NOT EXISTS asignacion_automatica BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE ordenes_trabajo ALTER COLUMN id_supervisor_asigna DROP NOT NULL;

ALTER TABLE ordenes_trabajo ADD COLUMN IF NOT EXISTS asignacion_automatica BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN subarea.asignacion_automatica IS
  'TRUE = los reclamos nuevos de esta gestion se asignan solos (services/autoasignacion.py, mig 114).';
COMMENT ON COLUMN ordenes_trabajo.asignacion_automatica IS
  'TRUE = OT creada por la autoasignacion (sin supervisor: id_supervisor_asigna NULL).';
