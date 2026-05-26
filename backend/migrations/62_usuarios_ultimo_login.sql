-- Migración 62: registrar el login de los usuarios internos.
--   1. usuarios.fecha_ultimo_login: denormalizado para mostrar rápido en la UI
--      (previa + detalle del form del módulo Usuarios).
--   2. usuario_login_log: auditoría append-only de cada login exitoso (timestamp
--      + IP + user agent). Permite revisar el historial de accesos por usuario.
-- Ambos los escribe POST /api/v1/auth/login en cada login exitoso (scope agente).
-- Idempotente.

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS fecha_ultimo_login TIMESTAMPTZ NULL;

COMMENT ON COLUMN usuarios.fecha_ultimo_login IS
    'Timestamp del último login exitoso (scope agente). NULL = nunca ingresó.';

CREATE TABLE IF NOT EXISTS usuario_login_log (
    id_login_log    BIGSERIAL PRIMARY KEY,
    id_usuario      INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    fecha_login     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip              VARCHAR(64),
    user_agent      TEXT
);

CREATE INDEX IF NOT EXISTS idx_usuario_login_log_usuario_fecha
    ON usuario_login_log (id_usuario, fecha_login DESC);

COMMENT ON TABLE usuario_login_log IS
    'Auditoría append-only de logins exitosos de usuarios internos (scope agente).';
