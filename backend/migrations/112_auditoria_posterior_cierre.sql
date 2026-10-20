-- Migracion 112 — Auditoria de reclamos POSTERIOR al cierre (2026-10-20)
--
-- PLAN_AUDITORIA_RECLAMOS.md. Hasta hoy la auditoria estaba ANTES del cierre: al
-- terminar la OT operativa de un tipo con audit=true el reclamo pasaba a
-- 'En auditoria' y recien al aprobarla a 'Resuelto' (ahi se fijaba fecha_cierre).
-- Cesar (2026-10-19): la gestion se mide desde el alta hasta el PRIMER cierre;
-- la auditoria es posterior y voluntaria: un supervisor elige un reclamo
-- 'Resuelto', lo manda a 'En auditoria' (pendiente del auditor) y el auditor lo
-- cierra como 'Auditado' con resultado aprobado u observado. fecha_cierre no se
-- toca nunca; una auditoria observada genera un reclamo NUEVO vinculado para el
-- retrabajo (id_reclamo_origen_auditoria), invisible para el vecino.
--
-- Idempotente. Aplicar en local (asyncpg) y prod (MCP) en la misma sesion (S24).
-- Verificado antes de aplicar (2026-10-20): ninguna de las dos DBs tiene las
-- columnas nuevas; el CHECK se llama ck_reclamo_estado en ambas; el CHECK de
-- ordenes_trabajo.resultado_auditoria se llama ck_ot_resultado en prod y
-- ordenes_trabajo_resultado_auditoria_check en local (se dropean los dos nombres);
-- reclamos 'En auditoria' del modelo viejo: 1 en prod (#36, su subreclamo #37 ya
-- esta Resuelto), 0 en local.

-- 1. Estado nuevo 'Auditado' en el CHECK de reclamos.estado.
ALTER TABLE reclamos DROP CONSTRAINT IF EXISTS ck_reclamo_estado;
ALTER TABLE reclamos ADD CONSTRAINT ck_reclamo_estado CHECK (
    estado IN ('Sin asignar','En gestión','En espera','En auditoría','Resuelto','Cancelado','Auditado')
);

-- 2. Catalogo estado_reclamo: 'Auditado' nuevo (final) + semantica/orden de los demas.
INSERT INTO estado_reclamo (nombre, descripcion, orden, es_final, activo)
SELECT 'Auditado', 'Cierre de la auditoría posterior (aprobada u observada)', 6, TRUE, TRUE
 WHERE NOT EXISTS (SELECT 1 FROM estado_reclamo WHERE nombre = 'Auditado');

UPDATE estado_reclamo
   SET descripcion = 'Reclamo resuelto reabierto para auditoría posterior, pendiente del auditor',
       orden = 5, es_final = FALSE, fecha_modificacion = NOW()
 WHERE nombre = 'En auditoría';
UPDATE estado_reclamo SET orden = 4, fecha_modificacion = NOW() WHERE nombre = 'Resuelto';
UPDATE estado_reclamo SET orden = 7, fecha_modificacion = NOW() WHERE nombre = 'Cancelado';

-- 3. Columnas de auditoria en reclamos (todas NULL para los reclamos sin auditoria).
ALTER TABLE reclamos
    ADD COLUMN IF NOT EXISTS fecha_inicio_auditoria TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS fecha_fin_auditoria    TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS resultado_auditoria    VARCHAR(20) NULL,
    ADD COLUMN IF NOT EXISTS id_reclamo_origen_auditoria INTEGER NULL
        REFERENCES reclamos(id_reclamo) ON DELETE SET NULL;

ALTER TABLE reclamos DROP CONSTRAINT IF EXISTS ck_reclamos_resultado_auditoria;
ALTER TABLE reclamos ADD CONSTRAINT ck_reclamos_resultado_auditoria CHECK (
    resultado_auditoria IS NULL OR resultado_auditoria IN ('aprobado','observado')
);

CREATE INDEX IF NOT EXISTS idx_reclamos_origen_auditoria
    ON reclamos(id_reclamo_origen_auditoria) WHERE id_reclamo_origen_auditoria IS NOT NULL;

COMMENT ON COLUMN reclamos.fecha_inicio_auditoria IS 'Cuando un supervisor mando el reclamo Resuelto a auditoria posterior (mig 112)';
COMMENT ON COLUMN reclamos.fecha_fin_auditoria IS 'Cuando el auditor cerro la auditoria (estado Auditado, mig 112)';
COMMENT ON COLUMN reclamos.resultado_auditoria IS 'aprobado | observado (mig 112). NULL = sin auditoria o pendiente';
COMMENT ON COLUMN reclamos.id_reclamo_origen_auditoria IS 'Reclamo auditado cuya auditoria observada genero este retrabajo (mig 112). Invisible para el vecino';

-- 4. OT de auditoria: resultado 'observada' (el 'rechazada' viejo queda valido para la historia).
ALTER TABLE ordenes_trabajo DROP CONSTRAINT IF EXISTS ck_ot_resultado;
ALTER TABLE ordenes_trabajo DROP CONSTRAINT IF EXISTS ordenes_trabajo_resultado_auditoria_check;
ALTER TABLE ordenes_trabajo ADD CONSTRAINT ck_ot_resultado CHECK (
    resultado_auditoria IS NULL OR resultado_auditoria IN ('aprobada','rechazada','observada')
);

-- 5. Reclamos que quedaron 'En auditoria' con el modelo viejo (auditoria previa al
--    cierre): su gestion termino cuando entraron a auditoria -> 'Resuelto' con esa
--    fecha como fecha_cierre. Primero el historial (lee el estado viejo), despues el UPDATE.
INSERT INTO reclamo_historial (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
SELECT r.id_reclamo, 'Cambio de estado a Resuelto', 'En auditoría', 'Resuelto',
       'Migración 112: la auditoría pasa a ser posterior al cierre. El reclamo queda resuelto con la fecha en que había entrado a auditoría.',
       NOW(), NULL
  FROM reclamos r
 WHERE r.estado = 'En auditoría';

UPDATE reclamos r
   SET estado = 'Resuelto',
       fecha_cierre = COALESCE(
           r.fecha_cierre,
           (SELECT MIN(h.fecha_alta) FROM reclamo_historial h
             WHERE h.id_reclamo = r.id_reclamo AND h.estado_nuevo = 'En auditoría'),
           r.fecha_modificacion),
       fecha_modificacion = NOW()
 WHERE r.estado = 'En auditoría';
