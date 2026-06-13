-- Migracion 90: Recuperacion de credenciales para usuarios INTERNOS + DNI en agentes.
--
-- Contexto (pedido del usuario, sesion 2026-06-12):
--   El login interno (frontend/login.html) NO tenia recuperacion de contrasena.
--   El portal de vecinos (publico_auth.py) ya la tenia por DNI->email. Replicamos
--   el mecanismo para el interno:
--     - "Olvide mi contrasena": ingresa email -> link de reseteo por mail.
--     - "Olvide mi usuario": ingresa numero de documento (DNI) -> el sistema busca
--       el agente con ese DNI, resuelve su usuario y le manda un mail recordandole
--       con que direccion entra. Anti-enumeracion: siempre responde OK.
--
--   La relacion usuario<->documento vive en `agentes` (regla 1:1 SS39), pero la tabla
--   NO tenia columna de DNI (solo cuil, que ademas estaba vacio en los 90 agentes).
--   Por eso agregamos `agentes.dni` para que el recovery de usuario tenga sustento real.
--
-- Convenciones del proyecto:
--   - usuarios usa la columna de auditoria legacy `fecha_modif` (SS5), no fecha_modificacion.
--   - NO agregamos lockout al interno (el login actual no lo tiene; fuera de alcance).
--   - Indices parciales sobre el token solo cuando NOT NULL (espejo de ciudadano_credencial).
--
-- Idempotente: ADD COLUMN IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.

BEGIN;

-- =============================================================================
-- 1. usuarios: tokens de recuperacion de contrasena
-- =============================================================================
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS token_recovery               UUID;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS token_recovery_expira        TIMESTAMPTZ;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_ultimo_email_recovery  TIMESTAMPTZ;

-- Indice parcial: solo filas con token activo (la inmensa mayoria son NULL).
CREATE INDEX IF NOT EXISTS idx_usuarios_token_recovery
    ON usuarios (token_recovery)
    WHERE token_recovery IS NOT NULL;

-- =============================================================================
-- 2. agentes: DNI (documento que relaciona al usuario con la persona)
-- =============================================================================
-- VARCHAR(15) nullable: el dato puede no estar cargado en agentes viejos. El
-- backend lo normaliza a digits-only antes de comparar/guardar (acepta que el
-- operador tipee "12.345.678" o "12345678"). NO ponemos UNIQUE: en datos legacy
-- podria haber duplicados o NULLs masivos; el recovery toma el primer match.
ALTER TABLE agentes ADD COLUMN IF NOT EXISTS dni VARCHAR(15);

-- Indice parcial para la busqueda del recovery (solo agentes con DNI cargado).
CREATE INDEX IF NOT EXISTS idx_agentes_dni
    ON agentes (dni)
    WHERE dni IS NOT NULL;

COMMIT;
