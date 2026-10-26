-- Migración 128b — IT-01 F3b: segundo factor de los niveles 0 y 1.
-- Plan: PLAN_MULTI_MUNICIPIO_F3B.md, Tarea 1. Spec: PLAN_MULTI_MUNICIPIO_F3B_DISENO.md §4-§5.
--
-- Sin DROP (va por MCP). Re-aplicable. Compatible con el código viejo: nadie usa todavía las
-- tablas nuevas ni la columna de usuarios.

-- 1. Revocación de sesiones: un token de una cuenta con segundo factor cuyo `iat` sea anterior
--    a esta marca da 401. La fijan la habilitación y cada vinculación confirmada.
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS sesiones_validas_desde TIMESTAMPTZ;

-- 2. Secreto de la app de autenticación, por cuenta. Fuera de `usuarios` a propósito: ningún
--    SELECT de usuarios lo arrastra. Los secretos van cifrados (Fernet, SEGUNDO_FACTOR_CLAVE).
CREATE TABLE IF NOT EXISTS usuario_segundo_factor (
    id_usuario                 INTEGER      PRIMARY KEY REFERENCES usuarios (id_usuario) ON DELETE CASCADE,
    id_municipio               INTEGER      REFERENCES municipios (id_municipio),
    secreto_cifrado            TEXT,
    secreto_pendiente_cifrado  TEXT,
    confirmado_en              TIMESTAMPTZ,
    ultimo_paso                BIGINT,
    intentos_fallidos          SMALLINT     NOT NULL DEFAULT 0,
    bloqueado_hasta            TIMESTAMPTZ,
    habilitado_hasta           TIMESTAMPTZ,
    activo                     BOOLEAN      DEFAULT TRUE,
    fecha_alta                 TIMESTAMPTZ  DEFAULT NOW(),
    fecha_modificacion         TIMESTAMPTZ  DEFAULT NOW(),
    id_usuario_alta            INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion    INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL
);
COMMENT ON TABLE usuario_segundo_factor IS
    'Segundo factor (TOTP) de las cuentas de nivel 0 y 1 (IT-01 F3b). id_municipio NULL = super administrador.';
ALTER TABLE usuario_segundo_factor ENABLE ROW LEVEL SECURITY;

-- 3. Códigos de emergencia (bcrypt), de un solo uso.
CREATE TABLE IF NOT EXISTS usuario_codigo_emergencia (
    id_codigo_emergencia  BIGSERIAL    PRIMARY KEY,
    id_usuario            INTEGER      NOT NULL REFERENCES usuarios (id_usuario),
    id_municipio          INTEGER      REFERENCES municipios (id_municipio),
    codigo_hash           TEXT         NOT NULL,
    usado_en              TIMESTAMPTZ,
    activo                BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_alta            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE usuario_codigo_emergencia IS
    'Códigos de emergencia del segundo factor (IT-01 F3b), bcrypt, un solo uso. id_municipio NULL = super administrador.';
CREATE INDEX IF NOT EXISTS ix_usuario_codigo_emergencia_vigentes
    ON usuario_codigo_emergencia (id_usuario) WHERE activo AND usado_en IS NULL;
ALTER TABLE usuario_codigo_emergencia ENABLE ROW LEVEL SECURITY;

-- 4. Eventos del segundo factor (append-only). Un registro: sin los campos estándar de §10.
CREATE TABLE IF NOT EXISTS usuario_segundo_factor_evento (
    id_evento         BIGSERIAL     PRIMARY KEY,
    id_usuario        INTEGER       NOT NULL REFERENCES usuarios (id_usuario),
    id_municipio      INTEGER       REFERENCES municipios (id_municipio),
    evento            VARCHAR(20)   NOT NULL,
    id_usuario_actor  INTEGER       REFERENCES usuarios (id_usuario),
    ip                VARCHAR(64),
    user_agent        VARCHAR(1000),
    fecha_hora        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_usuario_segundo_factor_evento_evento CHECK (evento IN
        ('vinculado', 'ingreso', 'fallido', 'emergencia', 'bloqueo', 'habilitado'))
);
COMMENT ON TABLE usuario_segundo_factor_evento IS
    'Eventos del segundo factor (IT-01 F3b). id_municipio NULL = super administrador. Append-only.';
CREATE INDEX IF NOT EXISTS ix_usuario_segundo_factor_evento_usuario
    ON usuario_segundo_factor_evento (id_usuario, fecha_hora DESC);
ALTER TABLE usuario_segundo_factor_evento ENABLE ROW LEVEL SECURITY;

-- Por sentencia (no por fila): frena también un DELETE o un TRUNCATE sobre la tabla vacía.
CREATE OR REPLACE FUNCTION usuario_segundo_factor_evento_no_mutate()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'usuario_segundo_factor_evento es append-only';
END;
$$;
CREATE OR REPLACE TRIGGER usuario_segundo_factor_evento_no_update BEFORE UPDATE ON usuario_segundo_factor_evento
    FOR EACH STATEMENT EXECUTE FUNCTION usuario_segundo_factor_evento_no_mutate();
CREATE OR REPLACE TRIGGER usuario_segundo_factor_evento_no_delete BEFORE DELETE ON usuario_segundo_factor_evento
    FOR EACH STATEMENT EXECUTE FUNCTION usuario_segundo_factor_evento_no_mutate();
CREATE OR REPLACE TRIGGER usuario_segundo_factor_evento_no_truncate BEFORE TRUNCATE ON usuario_segundo_factor_evento
    FOR EACH STATEMENT EXECUTE FUNCTION usuario_segundo_factor_evento_no_mutate();

-- 5. Clasificación (CLAUDE.md §10).
INSERT INTO municipio_tabla_clase (tabla, clase, nota) VALUES
    ('usuario_segundo_factor', 'mixta', 'NULL = cuenta del super administrador'),
    ('usuario_codigo_emergencia', 'mixta', 'NULL = cuenta del super administrador'),
    ('usuario_segundo_factor_evento', 'mixta', 'NULL = cuenta del super administrador; append-only')
ON CONFLICT (tabla) DO UPDATE
    SET clase = EXCLUDED.clase, nota = EXCLUDED.nota, fecha_modificacion = NOW();
