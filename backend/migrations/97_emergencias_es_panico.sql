-- ============================================================================
-- 97: Alerta de panico prioritaria en Emergencias (COM).
--     Plan aprobado 2026-07-16.
--
-- La PWA de vecinos (boton "Seguridad") crea eventos via
-- POST /api/v1/publico/emergencias/eventos cuya descripcion arranca con
-- "ALERTA DE PANICO" (con o sin tilde, casing variable). Hoy entran como
-- PENDIENTE comun y el backoffice no los distingue. Esta migracion agrega el
-- flag es_panico a emergencia_evento; el backend lo setea server-side al
-- detectar el prefijo (el body NO puede setearlo) y el tablero del dispatcher
-- lo usa para destacar, ordenar primero, banner y sonido.
--
-- Nota de columnas (verificado contra mig 83 y el codigo el 2026-07-18):
-- emergencia_evento NO tiene columna `descripcion`; el texto del vecino
-- (campo `descripcion` del body publico) se persiste en
-- `observaciones_recepcion`. El backfill matchea contra esa columna.
--
-- NO toca emergencia_log ni sus triggers (append-only, mig 83).
-- Idempotente (IF NOT EXISTS + es_panico = FALSE en el backfill).
-- Tabla ya existente: sin cambios de RLS.
-- ============================================================================

-- 1) Flag del evento. Server-side only: lo setea publico_emergencias.py al
--    detectar el prefijo normalizado; nunca viene del body.
ALTER TABLE emergencia_evento
    ADD COLUMN IF NOT EXISTS es_panico BOOLEAN NOT NULL DEFAULT FALSE;

-- 2) Indice parcial para las alertas abiertas (las consultas del tablero
--    filtran es_panico = TRUE sobre eventos activos; el set es minusculo).
CREATE INDEX IF NOT EXISTS idx_emergencia_panico_abierta
    ON emergencia_evento (id_emergencia_evento)
    WHERE es_panico = TRUE AND activo = TRUE;

-- 3) Backfill de eventos ya creados por el boton de la PWA: prefijo
--    "ALERTA DE PANICO" normalizado (upper + sin tildes) sobre los primeros
--    20 caracteres de observaciones_recepcion (donde quedo la descripcion
--    del vecino — ver nota de columnas arriba).
UPDATE emergencia_evento
   SET es_panico = TRUE
 WHERE activo = TRUE
   AND translate(upper(left(observaciones_recepcion, 20)), 'ÁÉÍÓÚ', 'AEIOU') LIKE 'ALERTA DE PANICO%'
   AND es_panico = FALSE;
