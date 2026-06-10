-- Migracion 82: Modulo Emergencias - Fase 2: tablas catalogo.
-- Plan: PLAN_MODULO_EMERGENCIAS.md (secciones 2.1-2.6, adaptadas a CLAUDE.md).
--
-- 6 tablas en orden de FK:
--   emergencia_organismo_derivacion, emergencia_canal_ingreso,
--   emergencia_prioridad, emergencia_estado
--   -> emergencia_tipo (FK a subarea + prioridad + organismo)
--   -> emergencia_subtipo (FK a tipo + prioridad override)
--
-- Convenciones del proyecto (ganan sobre el plan, CLAUDE.md SS28):
--   - PK estilo id_<tabla> (NO id generico). SERIAL/INTEGER como el resto
--     del schema (el plan decia BIGINT; subarea/usuarios son INTEGER).
--   - Estandar SS10 completo: activo, id_municipio, id_subarea, fecha_alta,
--     fecha_modificacion, id_usuario_alta, id_usuario_modificacion.
--   - id_municipio queda INTEGER nullable sin FK fisica ("FK futura" SS10).
--   - RLS habilitado sin politicas (deny-all; el backend postgres bypassea).
--   - SIN seeds aca: los datos van por backend/seed_catalogos_emergencias.py
--     (DDL y seeds separados, patron 75b).
--
-- Idempotente: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.

BEGIN;

-- =============================================================================
-- 1. emergencia_organismo_derivacion
-- =============================================================================
CREATE TABLE IF NOT EXISTS emergencia_organismo_derivacion (
    id_emergencia_organismo_derivacion SERIAL PRIMARY KEY,
    codigo                  VARCHAR(40) NOT NULL UNIQUE,
    nombre                  VARCHAR(150) NOT NULL,
    descripcion             TEXT,
    telefono_contacto       VARCHAR(30),
    es_municipal            BOOLEAN NOT NULL DEFAULT FALSE,
    -- estandar SS10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

ALTER TABLE emergencia_organismo_derivacion ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 2. emergencia_canal_ingreso
-- =============================================================================
CREATE TABLE IF NOT EXISTS emergencia_canal_ingreso (
    id_emergencia_canal_ingreso SERIAL PRIMARY KEY,
    codigo                  VARCHAR(40) NOT NULL UNIQUE,
    nombre                  VARCHAR(150) NOT NULL,
    descripcion             TEXT,
    requiere_operador       BOOLEAN NOT NULL DEFAULT TRUE,
    -- estandar SS10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

ALTER TABLE emergencia_canal_ingreso ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 3. emergencia_prioridad
-- =============================================================================
CREATE TABLE IF NOT EXISTS emergencia_prioridad (
    id_emergencia_prioridad SERIAL PRIMARY KEY,
    codigo                  VARCHAR(10) NOT NULL UNIQUE,    -- P1, P2, P3
    nombre                  VARCHAR(150) NOT NULL,
    descripcion             TEXT,
    sla_minutos_arribo      INTEGER NOT NULL,
    color_token             VARCHAR(40) NOT NULL,           -- nombre de token DS, no hex
    orden_visual            INTEGER NOT NULL,
    -- estandar SS10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

ALTER TABLE emergencia_prioridad ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 4. emergencia_estado
-- =============================================================================
CREATE TABLE IF NOT EXISTS emergencia_estado (
    id_emergencia_estado    SERIAL PRIMARY KEY,
    codigo                  VARCHAR(30) NOT NULL UNIQUE,
    nombre                  VARCHAR(150) NOT NULL,
    descripcion             TEXT,
    es_inicial              BOOLEAN NOT NULL DEFAULT FALSE,
    es_terminal             BOOLEAN NOT NULL DEFAULT FALSE,
    es_terminal_positivo    BOOLEAN NOT NULL DEFAULT FALSE,
    orden_visual            INTEGER NOT NULL,
    -- estandar SS10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

ALTER TABLE emergencia_estado ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 5. emergencia_tipo
-- =============================================================================
CREATE TABLE IF NOT EXISTS emergencia_tipo (
    id_emergencia_tipo      SERIAL PRIMARY KEY,
    id_subarea              INTEGER NOT NULL REFERENCES subarea(id_subarea),
    codigo_oficial          INTEGER,                        -- numero MinSeg PBA si aplica
    codigo                  VARCHAR(60) NOT NULL,           -- snake_case mayusculas
    nombre                  VARCHAR(150) NOT NULL,
    descripcion             TEXT,
    id_prioridad_default    INTEGER NOT NULL
        REFERENCES emergencia_prioridad(id_emergencia_prioridad),
    id_organismo_derivacion_default INTEGER
        REFERENCES emergencia_organismo_derivacion(id_emergencia_organismo_derivacion),
    requiere_911            BOOLEAN NOT NULL DEFAULT FALSE,
    es_emergencia           BOOLEAN NOT NULL,
    -- estandar SS10 (id_subarea ya esta arriba como FK semantica)
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT uq_emergencia_tipo_subarea_codigo UNIQUE (id_subarea, codigo)
);

CREATE INDEX IF NOT EXISTS idx_emergencia_tipo_subarea_activo
    ON emergencia_tipo (id_subarea, activo);

ALTER TABLE emergencia_tipo ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 6. emergencia_subtipo
-- =============================================================================
CREATE TABLE IF NOT EXISTS emergencia_subtipo (
    id_emergencia_subtipo   SERIAL PRIMARY KEY,
    id_tipo                 INTEGER NOT NULL
        REFERENCES emergencia_tipo(id_emergencia_tipo) ON DELETE CASCADE,
    codigo                  VARCHAR(60) NOT NULL,
    nombre                  VARCHAR(150) NOT NULL,
    descripcion             TEXT,
    id_prioridad_override   INTEGER
        REFERENCES emergencia_prioridad(id_emergencia_prioridad),
    -- estandar SS10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT uq_emergencia_subtipo_tipo_codigo UNIQUE (id_tipo, codigo)
);

CREATE INDEX IF NOT EXISTS idx_emergencia_subtipo_tipo
    ON emergencia_subtipo (id_tipo);

ALTER TABLE emergencia_subtipo ENABLE ROW LEVEL SECURITY;

COMMIT;
