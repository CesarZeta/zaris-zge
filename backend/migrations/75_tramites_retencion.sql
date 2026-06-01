-- Migracion 75: politica de retencion y depuracion de documentos de Tramites.
--
-- Fase 1 (mig 74) ya agrego tramite.resultado. Esta migracion habilita las
-- Fases 2-5 de la politica de retencion descripta en docs/manual_tramites.html
-- (seccion 10) y CLAUDE.md S35:
--
--   Fase 2  Excepcion por tipo de tramite: tipo_tramite.retencion_nunca_depurar.
--           Si TRUE, los binarios de ese tipo NUNCA se purgan (ej. Habilitaciones).
--   Fase 3  Auto-archivado por inactividad: tramite.fecha_archivado +
--           tramite.archivado_motivo. Un tramite sin movimiento durante N dias
--           (configuracion_general.tramite_inactividad_dias) se archiva y se
--           marca resultado='rechazado' por el cron.
--   Fase 4  Purga FISICA del binario: tramite_documento.binario_purgado +
--           fecha_purga_binario. El REGISTRO (metadatos + hash) NUNCA se borra;
--           solo se marca que el archivo del bucket fue depurado por antiguedad
--           (aprobado -> N anios; rechazado/descarte -> M anios). Plazos en
--           configuracion_general.
--   Fase 5  Cron (GitHub Actions) que dispara el motor de mantenimiento.
--
-- El registro de cada documento es inmutable; lo unico que se depura es el
-- archivo fisico. binario_purgado=TRUE significa "el binario ya no esta en el
-- bucket, pero el registro y su hash siguen aca".
--
-- Idempotente. SOLO DDL (los seeds de configuracion_general van aparte, ver
-- 75b mas abajo / el script de seed) para que un INSERT que choque no aborte
-- el ALTER (apply_migration es atomico).

-- ---------------------------------------------------------------------------
-- Fase 2: excepcion de depuracion por tipo de tramite
-- ---------------------------------------------------------------------------
ALTER TABLE tipo_tramite
    ADD COLUMN IF NOT EXISTS retencion_nunca_depurar BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN tipo_tramite.retencion_nunca_depurar IS
    'Si TRUE, los binarios de los documentos de este tipo de tramite nunca se purgan (override de la politica de retencion). Ej: Habilitaciones.';

-- ---------------------------------------------------------------------------
-- Fase 3: auto-archivado por inactividad
-- ---------------------------------------------------------------------------
ALTER TABLE tramite
    ADD COLUMN IF NOT EXISTS fecha_archivado TIMESTAMPTZ;

ALTER TABLE tramite
    ADD COLUMN IF NOT EXISTS archivado_motivo VARCHAR(30);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_tramite_archivado_motivo'
          AND conrelid = 'tramite'::regclass
    ) THEN
        ALTER TABLE tramite
            ADD CONSTRAINT ck_tramite_archivado_motivo
            CHECK (archivado_motivo IS NULL OR archivado_motivo IN ('inactividad', 'manual'));
    END IF;
END $$;

COMMENT ON COLUMN tramite.fecha_archivado IS
    'Fecha en que el tramite fue archivado (manual o por inactividad). NULL = no archivado. No confundir con un estado final del FSM: es una marca de mantenimiento que arranca el reloj de retencion del binario.';
COMMENT ON COLUMN tramite.archivado_motivo IS
    'Motivo del archivado: inactividad (cron, sin movimiento N dias) o manual.';

-- Indice para que el cron encuentre rapido los tramites a archivar/purgar.
CREATE INDEX IF NOT EXISTS idx_tramite_fecha_archivado
    ON tramite (fecha_archivado) WHERE fecha_archivado IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Fase 4: purga fisica del binario (el registro nunca se borra)
-- ---------------------------------------------------------------------------
ALTER TABLE tramite_documento
    ADD COLUMN IF NOT EXISTS binario_purgado BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE tramite_documento
    ADD COLUMN IF NOT EXISTS fecha_purga_binario TIMESTAMPTZ;

COMMENT ON COLUMN tramite_documento.binario_purgado IS
    'TRUE = el archivo fisico fue depurado del bucket por antiguedad. El registro (nombre, hash_sha256, fecha) permanece para siempre; solo se libero el almacenamiento.';
COMMENT ON COLUMN tramite_documento.fecha_purga_binario IS
    'Fecha en que se purgo el binario del bucket. NULL = binario aun presente.';

-- Indice para que el motor de purga liste rapido los binarios aun presentes.
CREATE INDEX IF NOT EXISTS idx_tramite_documento_no_purgado
    ON tramite_documento (id_tramite) WHERE binario_purgado = FALSE AND activo = TRUE;

-- ---------------------------------------------------------------------------
-- Ledger: nuevos tipos de movimiento para el mantenimiento automatico
-- ---------------------------------------------------------------------------
ALTER TABLE tramite_movimiento DROP CONSTRAINT IF EXISTS tramite_movimiento_tipo_check;
ALTER TABLE tramite_movimiento ADD CONSTRAINT tramite_movimiento_tipo_check
    CHECK (tipo IN (
        'creacion', 'numeracion', 'pase', 'toma', 'liberacion',
        'cambio_estado', 'transicion', 'adjunto',
        'firma_solicitada', 'firma_realizada', 'firma_rechazada',
        'comentario', 'relacion', 'desistido', 'reapertura',
        'aprobacion', 'resultado',
        'archivado_inactividad', 'purga_binario'
    ));
