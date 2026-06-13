-- Migracion 89: tipo 'bloqueo' en ocupaciones
-- Cierre manual de un recurso sin entidad asociada (espacio en mantenimiento,
-- agente afectado a otra tarea). No requiere FK: las 3 (id_orden_trabajo,
-- id_evento, id_ciudadano) van NULL. El backend exige motivo (schema
-- OcupacionCreate). Idempotente: DROP IF EXISTS + ADD.

ALTER TABLE ocupaciones DROP CONSTRAINT IF EXISTS ck_ocup_tipo;
ALTER TABLE ocupaciones ADD CONSTRAINT ck_ocup_tipo
    CHECK (tipo IN ('ot', 'evento', 'turno', 'bloqueo'));

ALTER TABLE ocupaciones DROP CONSTRAINT IF EXISTS ck_ocupacion_consistencia;
ALTER TABLE ocupaciones ADD CONSTRAINT ck_ocupacion_consistencia CHECK (
       (tipo = 'ot'      AND id_orden_trabajo IS NOT NULL AND id_evento IS NULL     AND id_ciudadano IS NULL)
    OR (tipo = 'evento'  AND id_evento IS NOT NULL        AND id_orden_trabajo IS NULL AND id_ciudadano IS NULL)
    OR (tipo = 'turno'   AND id_ciudadano IS NOT NULL     AND id_evento IS NULL     AND id_orden_trabajo IS NULL)
    OR (tipo = 'bloqueo' AND id_orden_trabajo IS NULL     AND id_evento IS NULL     AND id_ciudadano IS NULL)
);
