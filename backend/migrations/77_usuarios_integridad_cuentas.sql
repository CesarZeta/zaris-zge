-- Migración 77 — Integridad de cuentas (Fase 2 del roadmap usuario↔agente/ciudadano)
--
-- Marca de suspensión automática para usuarios sin vínculo a agente ni ciudadano.
-- La aplica el cron de integridad (services/integridad_cuentas.py vía
-- routes/usuarios_mantenimiento.py). El usuario suspendido queda activo=FALSE
-- (baja lógica) y se puede reactivar manualmente desde Maestros → Usuarios una
-- vez que se le crea el agente o ciudadano faltante.
--
-- Idempotente. Aplicada en local Y prod.

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS suspendido_motivo VARCHAR(30),
    ADD COLUMN IF NOT EXISTS fecha_suspension  TIMESTAMPTZ;

-- CHECK: motivo acotado. 'sin_vinculo' = sin agente ni ciudadano asociado.
-- NOT VALID para no fallar contra filas viejas (todas tienen el motivo en NULL).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_usuarios_suspendido_motivo'
    ) THEN
        ALTER TABLE usuarios
            ADD CONSTRAINT ck_usuarios_suspendido_motivo
            CHECK (suspendido_motivo IS NULL OR suspendido_motivo IN ('sin_vinculo'))
            NOT VALID;
    END IF;
END $$;

COMMENT ON COLUMN usuarios.suspendido_motivo IS
    'Motivo de suspensión automática por el cron de integridad. sin_vinculo = usuario sin agente ni ciudadano asociado.';
COMMENT ON COLUMN usuarios.fecha_suspension IS
    'Momento en que el cron de integridad suspendió la cuenta (baja lógica). NULL si nunca fue suspendida automáticamente.';
