-- ============================================================================
-- 96: Politica de renovacion de credenciales de usuarios internos (~1 año).
--     Idea de Cesar 2026-07-18 (memoria project_politica_renovacion_credenciales).
--     Reusa el gate de cambio forzado existente (usuarios.debe_cambiar_password,
--     mig 78): al loguear, si la clave supera la vigencia configurada, el backend
--     marca debe_cambiar_password=TRUE y el login vanilla fuerza el cambio.
--
-- Idempotente. Sin cambios de RLS (tabla existente).
-- ============================================================================

-- Fecha del ultimo cambio de password. DEFAULT NOW() para que las altas nuevas
-- arranquen el reloj solas; backfill NOW() = el reloj arranca hoy para las
-- cuentas existentes (nadie es forzado de inmediato por la migracion).
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS password_actualizada_en TIMESTAMPTZ DEFAULT NOW();

UPDATE usuarios SET password_actualizada_en = NOW()
 WHERE password_actualizada_en IS NULL;

-- Vigencia configurable en dias (0 = politica desactivada). Editable en
-- Config → Sistema (§41). OJO drift §21: prod tiene configuracion_general.tipo
-- NOT NULL y local no — INSERT condicional por existencia de la columna.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM configuracion_general WHERE clave = 'password_renovacion_dias') THEN
        RETURN;
    END IF;
    -- activo explicito: en prod la columna es NOT NULL SIN default (drift §24
    -- cazado al aplicar 2026-07-18); en local tiene default TRUE.
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'configuracion_general' AND column_name = 'tipo') THEN
        INSERT INTO configuracion_general (clave, valor, descripcion, tipo, activo)
        VALUES ('password_renovacion_dias', '365',
                'Dias de vigencia de la password de usuarios internos antes de forzar la renovacion en el proximo login (0 = desactivado)',
                'integer', TRUE);
    ELSE
        INSERT INTO configuracion_general (clave, valor, descripcion, activo)
        VALUES ('password_renovacion_dias', '365',
                'Dias de vigencia de la password de usuarios internos antes de forzar la renovacion en el proximo login (0 = desactivado)',
                TRUE);
    END IF;
END $$;
