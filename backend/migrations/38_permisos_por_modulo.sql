-- =============================================================================
-- Migracion 38 — Permisos por modulo (CLAUDE.md §30)
-- =============================================================================
-- Modelo hibrido: nivel minimo por modulo (default por jerarquia de
-- usuarios.nivel_acceso) + override explicito por usuario via usuario_modulos.
--
--   * usuario_modulos.permitido = TRUE  -> override otorga (le da acceso aunque
--                                          su nivel sea mas alto que min_nivel_acceso).
--   * usuario_modulos.permitido = FALSE -> override bloquea (le quita acceso
--                                          aunque su nivel lo permitiria).
--   * Sin fila                          -> cae al default por nivel.
--
-- Nivel jerarquico (menor numero = mas permisos):
--   1 = Administrador  2 = Supervisor  3 = Operador  4 = Consultor
-- min_nivel_acceso = 4 significa "todos los niveles pueden ver el modulo".
-- min_nivel_acceso = 1 significa "solo administradores".
--
-- Idempotente.
-- =============================================================================

BEGIN;

-- 1) Catalogo de modulos ----------------------------------------------------
CREATE TABLE IF NOT EXISTS modulos (
    modulo_codigo       VARCHAR(50) PRIMARY KEY,
    nombre              VARCHAR(100) NOT NULL,
    descripcion         TEXT,
    min_nivel_acceso    SMALLINT NOT NULL DEFAULT 4 CHECK (min_nivel_acceso BETWEEN 1 AND 4),
    -- estandar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

-- Seeds del catalogo (idempotente)
INSERT INTO modulos (modulo_codigo, nombre, descripcion, min_nivel_acceso) VALUES
  ('reclamos',     'Reclamos',           'Gestion de reclamos ciudadanos',                  4),
  ('ot_supervisor','OT - Supervisor',    'Mesa de asignacion y reasignacion de OTs',        2),
  ('ot_agente',    'OT - Agente',        'Mesa de OTs propias del agente',                  3),
  ('ot_auditoria', 'OT - Auditoria',     'Mesa de auditoria de OTs cerradas',               2),
  ('turnos',       'Turnos y eventos',   'Modulo Agenda (timeline, eventos, ocupaciones)',  3),
  ('padrones',     'Padrones',           'Ciudadanos y Empresas (BUC)',                     4),
  ('usuarios',     'Usuarios',           'Maestro de usuarios del sistema',                 1),
  ('admin_tablas', 'Maestros',           'CRUD generico de tablas maestras del sistema',    1)
ON CONFLICT (modulo_codigo) DO NOTHING;

-- 2) Overrides por usuario ---------------------------------------------------
CREATE TABLE IF NOT EXISTS usuario_modulos (
    id_usuario_modulo   SERIAL PRIMARY KEY,
    id_usuario          INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    modulo_codigo       VARCHAR(50) NOT NULL REFERENCES modulos(modulo_codigo) ON DELETE CASCADE,
    permitido           BOOLEAN NOT NULL,
    motivo              TEXT,
    -- estandar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    -- Solo un override activo por (usuario, modulo). Las filas con activo=FALSE
    -- son historicas/soft-deleted.
    CONSTRAINT uq_usuario_modulo_activo UNIQUE (id_usuario, modulo_codigo)
);

CREATE INDEX IF NOT EXISTS idx_usuario_modulos_id_usuario
    ON usuario_modulos (id_usuario) WHERE activo = TRUE;

COMMIT;
