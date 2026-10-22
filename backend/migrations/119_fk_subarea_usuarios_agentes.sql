-- Migracion 119 — FK de usuarios.id_subarea y agentes.id_subarea a subarea (2026-10-22)
--
-- Drift (§24): en local las dos FK y el indice idx_agentes_subarea existen desde hace
-- tiempo (cambio manual, sin migracion); en prod no habia ninguna de las tres cosas.
-- Sin la FK, prod aceptaba una gestion inexistente que local rechaza. La gestion de una
-- persona es la del agente (§3, mig 116), asi que la integridad importa en las dos.
--
-- Verificado antes de aplicar: 0 huerfanos en usuarios y 0 en agentes (local y prod).
-- ON DELETE SET NULL igual que local (las subareas no se borran: baja logica).
-- Idempotente: cada FK se crea solo si no existe una con ese nombre.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'usuarios_id_subarea_fkey' AND conrelid = 'usuarios'::regclass) THEN
        ALTER TABLE usuarios
            ADD CONSTRAINT usuarios_id_subarea_fkey
            FOREIGN KEY (id_subarea) REFERENCES subarea(id_subarea) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'agentes_id_subarea_fkey' AND conrelid = 'agentes'::regclass) THEN
        ALTER TABLE agentes
            ADD CONSTRAINT agentes_id_subarea_fkey
            FOREIGN KEY (id_subarea) REFERENCES subarea(id_subarea) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_agentes_subarea ON agentes (id_subarea);
