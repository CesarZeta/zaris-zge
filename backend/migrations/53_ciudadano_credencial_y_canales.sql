-- Migracion 53: Auth publico de ciudadanos (App Vecinos).
-- Agrega ciudadanos.estado_validacion + tablas ciudadano_credencial,
-- ciudadano_canal_preferido y ciudadano_push_subscription.
-- Idempotente: ADD COLUMN IF NOT EXISTS + CREATE TABLE IF NOT EXISTS.
-- Requiere extension pgcrypto (ya creada en mig 35).

BEGIN;

-- ---------------------------------------------------------------------------
-- 2.1 Columna estado_validacion en ciudadanos
-- ---------------------------------------------------------------------------
ALTER TABLE ciudadanos
    ADD COLUMN IF NOT EXISTS estado_validacion VARCHAR(25) NOT NULL DEFAULT 'auto_registrado';

-- Re-aplicar CHECK de forma idempotente (DROP IF EXISTS + ADD)
ALTER TABLE ciudadanos
    DROP CONSTRAINT IF EXISTS ciudadanos_estado_validacion_check;
ALTER TABLE ciudadanos
    ADD CONSTRAINT ciudadanos_estado_validacion_check
    CHECK (estado_validacion IN ('auto_registrado', 'vinculado_pendiente', 'verificado'));

-- ---------------------------------------------------------------------------
-- 2.2 Tabla ciudadano_credencial
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ciudadano_credencial (
    id_ciudadano_credencial SERIAL PRIMARY KEY,
    id_ciudadano INTEGER NOT NULL UNIQUE REFERENCES ciudadanos(id_ciudadano) ON DELETE CASCADE,

    -- Credenciales
    password_hash VARCHAR(255) NULL,

    -- Activacion inicial
    token_activacion UUID NULL,
    token_activacion_expira TIMESTAMPTZ NULL,
    activado BOOLEAN NOT NULL DEFAULT FALSE,
    activado_en TIMESTAMPTZ NULL,

    -- Recovery
    token_recovery UUID NULL,
    token_recovery_expira TIMESTAMPTZ NULL,

    -- Anti-abuso de reenvios de mail
    fecha_ultimo_email_activacion TIMESTAMPTZ NULL,
    fecha_ultimo_email_recovery TIMESTAMPTZ NULL,

    -- Lockout por intentos fallidos
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    bloqueada_hasta TIMESTAMPTZ NULL,
    fecha_ultimo_login TIMESTAMPTZ NULL,
    fecha_ultimo_cambio_password TIMESTAMPTZ NULL,

    -- Estandar §10
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio INTEGER NULL,
    id_subarea INTEGER NULL,
    fecha_alta TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta INTEGER NULL REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER NULL REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ciudadano_credencial_token_activacion
    ON ciudadano_credencial(token_activacion) WHERE token_activacion IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ciudadano_credencial_token_recovery
    ON ciudadano_credencial(token_recovery) WHERE token_recovery IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2.3 Tabla ciudadano_canal_preferido
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ciudadano_canal_preferido (
    id_ciudadano_canal_preferido SERIAL PRIMARY KEY,
    id_ciudadano INTEGER NOT NULL UNIQUE REFERENCES ciudadanos(id_ciudadano) ON DELETE CASCADE,

    -- Canales (todos preparados, solo email se usa en MVP)
    canal_email BOOLEAN NOT NULL DEFAULT TRUE,
    canal_push BOOLEAN NOT NULL DEFAULT TRUE,
    canal_whatsapp BOOLEAN NOT NULL DEFAULT FALSE,
    canal_sms BOOLEAN NOT NULL DEFAULT FALSE,

    -- Estandar §10
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio INTEGER NULL,
    id_subarea INTEGER NULL,
    fecha_alta TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta INTEGER NULL REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER NULL REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------------
-- 2.4 Tabla ciudadano_push_subscription (placeholder, no se consume en esta etapa)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ciudadano_push_subscription (
    id_ciudadano_push_subscription SERIAL PRIMARY KEY,
    id_ciudadano INTEGER NOT NULL REFERENCES ciudadanos(id_ciudadano) ON DELETE CASCADE,

    endpoint TEXT NOT NULL,
    p256dh TEXT NOT NULL,
    auth_secret TEXT NOT NULL,
    user_agent TEXT NULL,

    -- Estandar §10
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio INTEGER NULL,
    id_subarea INTEGER NULL,
    fecha_alta TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta INTEGER NULL REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER NULL REFERENCES usuarios(id_usuario) ON DELETE SET NULL,

    UNIQUE(id_ciudadano, endpoint)
);

COMMIT;
