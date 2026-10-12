-- Migracion 110 — Circuito de alta de cuentas ZARIS desde la ficha del ciudadano (2026-10-12)
--
-- PLAN_CUENTAS_FUNCIONARIO.md. Un funcionario municipal existe PRIMERO como persona en la
-- BUC; desde esa ficha un administrador le crea la cuenta ZARIS (usuarios + agente 1:1).
-- Hasta hoy el unico vinculo usuario<->ciudadano era "mismo email" (cron de integridad,
-- mig 77). Esta mig lo hace explicito y persiste la marca de funcionario en la ficha.
--
-- Idempotente. Aplicar en local (asyncpg) y prod (MCP) en la misma sesion (§24).
-- Verificado antes de aplicar (2026-10-12): ninguna de las dos DBs tiene estas columnas;
-- el backfill por email toca 1 usuario en prod (ciudadanovl <-> ciudadano 1612) y 0 en local.

-- 1. La ficha de la BUC persiste el tilde "Este ciudadano es funcionario del municipio".
ALTER TABLE ciudadanos
    ADD COLUMN IF NOT EXISTS es_funcionario BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Vinculo explicito usuario -> persona de la BUC. Un ciudadano tiene como maximo UN
--    usuario (indice unico parcial, mismo patron que agentes.id_usuario en mig 64).
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS id_ciudadano INTEGER NULL
        REFERENCES ciudadanos(id_ciudadano) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_id_ciudadano
    ON usuarios(id_ciudadano) WHERE id_ciudadano IS NOT NULL;

-- 3. Backfill deterministico: usuarios activos sin vinculo cuyo email coincide con
--    EXACTAMENTE UN ciudadano activo (mismo criterio que el cron de integridad). Si hay
--    ambiguedad (dos ciudadanos con ese email) no se vincula nada.
UPDATE usuarios u
   SET id_ciudadano = m.id_ciudadano
  FROM (
        SELECT u2.id_usuario, MIN(c.id_ciudadano) AS id_ciudadano
          FROM usuarios u2
          JOIN ciudadanos c ON LOWER(c.email) = LOWER(u2.email) AND c.activo = TRUE
         WHERE u2.activo = TRUE AND u2.id_ciudadano IS NULL AND u2.email IS NOT NULL
         GROUP BY u2.id_usuario
        HAVING COUNT(*) = 1
       ) m
 WHERE u.id_usuario = m.id_usuario
   AND NOT EXISTS (SELECT 1 FROM usuarios x WHERE x.id_ciudadano = m.id_ciudadano);

-- 4. Todo ciudadano vinculado a un usuario queda marcado como funcionario.
UPDATE ciudadanos c
   SET es_funcionario = TRUE
  FROM usuarios u
 WHERE u.id_ciudadano = c.id_ciudadano
   AND c.es_funcionario = FALSE;
