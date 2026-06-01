-- Migracion 75b: claves de configuracion para la politica de retencion (mig 75).
--
-- Va SEPARADA del DDL (75) por atomicidad: apply_migration es atomico, asi que
-- un INSERT que choque no debe poder revertir el ALTER TABLE. Los plazos son
-- configurables desde Config -> Sistema (S41).
--
-- Claves:
--   retencion_dias_aprobado     dias que se conserva el binario de un tramite
--                               cuyo resultado es 'aprobado' (default 10 anios).
--   retencion_dias_rechazado    dias que se conserva el binario de un tramite
--                               rechazado / desistido (default 1 anio).
--   tramite_inactividad_dias    dias sin movimiento tras los cuales el cron
--                               archiva el tramite y lo marca rechazado (180).
--   tramite_purga_binarios_real switch del motor de purga: 'false' = dry-run
--                               (solo loguea / reporta que purgaria, NO borra
--                               del bucket); 'true' = purga real. Arranca en
--                               dry-run como red de seguridad.
--
-- Idempotente (ON CONFLICT DO NOTHING — no pisa un valor ya ajustado a mano).
--
-- DRIFT prod vs local (cazado 2026-06-01, regla S24): prod tiene una columna
-- `configuracion_general.tipo` NOT NULL (valores 'string'|'boolean'|'integer',
-- la usa la pantalla Config->Sistema S41 para tipar el input); local NO la
-- tiene. El DO block de abajo arma el INSERT con o sin la columna `tipo` segun
-- exista, para que el seed corra en ambos entornos sin tocar el otro.

DO $$
DECLARE
    tiene_tipo BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'configuracion_general' AND column_name = 'tipo'
    ) INTO tiene_tipo;

    IF tiene_tipo THEN
        INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
        VALUES
            ('retencion_dias_aprobado',     '3650',  'integer', 'Dias que se conserva el archivo fisico de un documento de un tramite APROBADO antes de depurarlo (10 anios). El registro y su hash nunca se borran.', TRUE),
            ('retencion_dias_rechazado',    '365',   'integer', 'Dias que se conserva el archivo fisico de un documento de un tramite RECHAZADO o desistido antes de depurarlo (1 anio). El registro y su hash nunca se borran.', TRUE),
            ('tramite_inactividad_dias',    '180',   'integer', 'Dias sin movimiento tras los cuales un tramite se archiva automaticamente y se marca resultado=rechazado por inactividad.', TRUE),
            ('tramite_purga_binarios_real', 'false', 'boolean', 'Switch del motor de purga de binarios de Tramites. false = dry-run (reporta que purgaria, NO borra del bucket). true = purga real. Activar solo tras validar el dry-run.', TRUE)
        ON CONFLICT (clave) DO NOTHING;
    ELSE
        INSERT INTO configuracion_general (clave, valor, descripcion, activo)
        VALUES
            ('retencion_dias_aprobado',     '3650',  'Dias que se conserva el archivo fisico de un documento de un tramite APROBADO antes de depurarlo (10 anios). El registro y su hash nunca se borran.', TRUE),
            ('retencion_dias_rechazado',    '365',   'Dias que se conserva el archivo fisico de un documento de un tramite RECHAZADO o desistido antes de depurarlo (1 anio). El registro y su hash nunca se borran.', TRUE),
            ('tramite_inactividad_dias',    '180',   'Dias sin movimiento tras los cuales un tramite se archiva automaticamente y se marca resultado=rechazado por inactividad.', TRUE),
            ('tramite_purga_binarios_real', 'false', 'Switch del motor de purga de binarios de Tramites. false = dry-run (reporta que purgaria, NO borra del bucket). true = purga real. Activar solo tras validar el dry-run.', TRUE)
        ON CONFLICT (clave) DO NOTHING;
    END IF;
END $$;
