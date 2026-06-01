-- Migracion 74: marca de resultado del tramite (paralela al estado)
--
-- El ESTADO del tramite es del flujo (en_proceso / subsanacion / archivado).
-- El RESULTADO es una marca aparte que indica como concluyo el tramite,
-- igual que un documento se marca aprobado/firmado. Se consulta junto al
-- estado: un tramite concluido se ve "archivado, aprobado" o "archivado,
-- rechazado". Esta marca (no el estado) decide la politica de retencion de
-- los binarios adjuntos (aprobado -> 10 anios, rechazado/descarte -> 1 anio).
--
-- Valores:
--   pendiente  -> default; el tramite todavia no concluyo con resultado.
--   aprobado   -> concluyo favorablemente (supervisor/admin lo marca).
--   rechazado  -> concluyo desfavorablemente (manual, o automatico por
--                 inactividad de 180 dias en la fase del cron de archivado).
--
-- Idempotente.

ALTER TABLE tramite
    ADD COLUMN IF NOT EXISTS resultado VARCHAR(15) NOT NULL DEFAULT 'pendiente';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_tramite_resultado'
          AND conrelid = 'tramite'::regclass
    ) THEN
        ALTER TABLE tramite
            ADD CONSTRAINT ck_tramite_resultado
            CHECK (resultado IN ('pendiente', 'aprobado', 'rechazado'));
    END IF;
END $$;

-- Tipo de movimiento 'resultado' en el ledger append-only: registra cuando
-- un supervisor/admin marca el resultado del tramite (o el cron lo marca
-- 'rechazado' por inactividad). Se agrega al CHECK existente recreandolo.
ALTER TABLE tramite_movimiento DROP CONSTRAINT IF EXISTS tramite_movimiento_tipo_check;
ALTER TABLE tramite_movimiento ADD CONSTRAINT tramite_movimiento_tipo_check
    CHECK (tipo IN (
        'creacion', 'numeracion', 'pase', 'toma', 'liberacion',
        'cambio_estado', 'transicion', 'adjunto',
        'firma_solicitada', 'firma_realizada', 'firma_rechazada',
        'comentario', 'relacion', 'desistido', 'reapertura',
        'aprobacion', 'resultado'
    ));
