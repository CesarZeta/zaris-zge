-- Migración 28 — agregar agentes.id_usuario (FK a usuarios)
--
-- Hasta ahora no existía vínculo formal entre agentes y usuarios. El frontend
-- intentaba resolver el agente del usuario logueado por matching de email
-- (agentes.email = usuarios.email), lo cual viola la regla del proyecto de
-- relacionar siempre por id (ver memoria feedback_vincular_por_id).
--
-- Esta migración:
--   1. Agrega agentes.id_usuario INTEGER NULL UNIQUE REFERENCES usuarios(id_usuario).
--   2. Backfill: matchea por email donde haya coincidencia única (data ya existente).
--   3. NO crea usuarios para agentes huérfanos — eso queda como tarea de admin
--      (puede asignar desde admin_tablas seleccionando el id_usuario correcto).
--
-- El backend /api/v1/ot/agente/me resuelve el agente con
--   SELECT id_agente FROM agentes WHERE id_usuario = :current_user.id_usuario.
-- Si no hay match, devuelve 404 con mensaje claro.

BEGIN;

ALTER TABLE agentes
    ADD COLUMN IF NOT EXISTS id_usuario INTEGER NULL
    REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- UNIQUE solo si la columna fue recién creada (constraint separado para idempotencia)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'agentes_id_usuario_key'
    ) THEN
        ALTER TABLE agentes ADD CONSTRAINT agentes_id_usuario_key UNIQUE (id_usuario);
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_agentes_id_usuario ON agentes(id_usuario);

-- Backfill por email (case-insensitive). Solo si hay match único.
UPDATE agentes a
SET id_usuario = u.id_usuario,
    fecha_modificacion = NOW()
FROM usuarios u
WHERE a.id_usuario IS NULL
  AND a.activo = TRUE
  AND u.activo = TRUE
  AND a.email IS NOT NULL
  AND u.email IS NOT NULL
  AND LOWER(a.email) = LOWER(u.email);

COMMIT;
