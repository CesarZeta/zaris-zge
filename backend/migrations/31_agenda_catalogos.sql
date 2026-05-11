-- =============================================================================
-- Migracion 31 — Agenda sub-fase 1.A — Catalogos
-- =============================================================================
-- Tablas: estado_evento, estado_reserva (catalogos de estados).
-- Seeds idempotentes via ON CONFLICT (codigo) DO NOTHING.
-- =============================================================================

BEGIN;

-- estado_evento ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS estado_evento (
    id_estado_evento    SERIAL PRIMARY KEY,
    codigo              VARCHAR(20) UNIQUE NOT NULL,
    descripcion         VARCHAR(120),
    orden               INTEGER,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio        INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

INSERT INTO estado_evento (codigo, descripcion, orden) VALUES
    ('activo',     'Evento activo, acepta reservas',          1),
    ('finalizado', 'Evento concluido',                        2),
    ('cancelado',  'Evento cancelado, reservas invalidadas',  3)
ON CONFLICT (codigo) DO NOTHING;

-- estado_reserva -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS estado_reserva (
    id_estado_reserva   SERIAL PRIMARY KEY,
    codigo              VARCHAR(20) UNIQUE NOT NULL,
    descripcion         VARCHAR(120),
    orden               INTEGER,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio        INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

INSERT INTO estado_reserva (codigo, descripcion, orden) VALUES
    ('reservada', 'Reserva confirmada, pendiente de asistencia', 1),
    ('asistio',   'Ciudadano se presento',                       2),
    ('cancelada', 'Reserva cancelada por ciudadano u operador',  3)
ON CONFLICT (codigo) DO NOTHING;

COMMIT;
