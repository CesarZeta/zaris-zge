-- Migración 78 — Cambio de contraseña forzado en primer ingreso (Fase 3 del roadmap
-- de integridad de cuentas).
--
-- Cuando un usuario interno se da de alta, el sistema genera una contraseña
-- temporal aleatoria, la manda por email, y marca debe_cambiar_password=TRUE.
-- En el primer login el frontend detecta la marca y obliga a elegir una nueva
-- contraseña antes de dejar usar el sistema. El endpoint self-service de cambio
-- limpia la marca.
--
-- También se usará en Fase 4-Camino-B (vecino dado de alta por un agente): la
-- misma mecánica de clave temporal + cambio forzado, sobre ciudadano_credencial
-- (esa columna se agrega en una migración aparte cuando se encare la Fase 4).
--
-- Idempotente. Aplicar en local Y prod.

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS debe_cambiar_password BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN usuarios.debe_cambiar_password IS
    'TRUE = el usuario tiene una contraseña temporal y debe elegir una nueva en su próximo ingreso. Lo setea el alta (clave generada por el sistema) y lo limpia el cambio self-service.';
