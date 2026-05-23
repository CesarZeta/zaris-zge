-- Migracion 57: Modulo Encuestas (CSAT).
-- Encuestas de satisfaccion disparadas al cierre de reclamos.
-- Encuesta estandar ZARIS (no editable por municipio en v1), con
-- ramificacion condicional segun la satisfaccion inicial (1-5).
--
-- 6 tablas en orden de FK:
--   encuesta_plantilla -> encuesta_pregunta -> encuesta_opcion
--   encuesta_envio (FK fisica a ciudadanos + reclamos) -> encuesta_respuesta
--   -> encuesta_respuesta_detalle
--
-- Convenciones del proyecto:
--   - PK estilo id_<tabla> (NO id generico). Ver CLAUDE.md §5/§28.
--   - Estandar §10 completo: activo, id_municipio, id_subarea, fecha_alta,
--     fecha_modificacion, id_usuario_alta, id_usuario_modificacion.
--   - id_municipio/id_subarea quedan INTEGER nullable sin FK fisica
--     ("FK futura" §10), igual que el resto del schema.
--   - BUC obligatoria (§2): id_ciudadano es FK FISICA a ciudadanos(id_ciudadano).
--
-- Idempotente: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.

BEGIN;

-- =============================================================================
-- 1. encuesta_plantilla
-- =============================================================================
CREATE TABLE IF NOT EXISTS encuesta_plantilla (
    id_encuesta_plantilla   SERIAL PRIMARY KEY,
    nombre                  VARCHAR(100) NOT NULL,
    descripcion             TEXT,
    version                 VARCHAR(20) NOT NULL DEFAULT '1.0',
    tipo                    VARCHAR(30) NOT NULL,
    -- estandar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_encuesta_plantilla_tipo
        CHECK (tipo IN ('reclamos', 'tramites', 'turnos'))
);

-- =============================================================================
-- 2. encuesta_pregunta
-- =============================================================================
CREATE TABLE IF NOT EXISTS encuesta_pregunta (
    id_encuesta_pregunta    SERIAL PRIMARY KEY,
    id_plantilla            INTEGER NOT NULL
        REFERENCES encuesta_plantilla(id_encuesta_plantilla) ON DELETE CASCADE,
    texto                   TEXT NOT NULL,
    tipo                    VARCHAR(20) NOT NULL,
    orden                   INTEGER NOT NULL,
    rama                    VARCHAR(20) NOT NULL,
    obligatoria             BOOLEAN NOT NULL DEFAULT TRUE,
    -- estandar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_encuesta_pregunta_tipo
        CHECK (tipo IN ('likert5', 'texto_libre', 'si_no', 'multiple')),
    CONSTRAINT ck_encuesta_pregunta_rama
        CHECK (rama IN ('todos', 'satisfechos', 'neutrales', 'insatisfechos'))
);

CREATE INDEX IF NOT EXISTS idx_encuesta_pregunta_plantilla
    ON encuesta_pregunta (id_plantilla);

-- =============================================================================
-- 3. encuesta_opcion (solo para preguntas tipo 'multiple')
-- =============================================================================
CREATE TABLE IF NOT EXISTS encuesta_opcion (
    id_encuesta_opcion      SERIAL PRIMARY KEY,
    id_pregunta             INTEGER NOT NULL
        REFERENCES encuesta_pregunta(id_encuesta_pregunta) ON DELETE CASCADE,
    texto                   VARCHAR(200) NOT NULL,
    valor                   VARCHAR(50) NOT NULL,
    orden                   INTEGER NOT NULL,
    -- estandar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_encuesta_opcion_pregunta
    ON encuesta_opcion (id_pregunta);

-- =============================================================================
-- 4. encuesta_envio (FK fisica a ciudadanos + reclamos)
-- =============================================================================
CREATE TABLE IF NOT EXISTS encuesta_envio (
    id_encuesta_envio       SERIAL PRIMARY KEY,
    id_plantilla            INTEGER NOT NULL
        REFERENCES encuesta_plantilla(id_encuesta_plantilla) ON DELETE RESTRICT,
    -- BUC obligatoria (§2): FK fisica al ciudadano
    id_ciudadano            INTEGER NOT NULL
        REFERENCES ciudadanos(id_ciudadano) ON DELETE RESTRICT,
    id_reclamo              INTEGER NOT NULL
        REFERENCES reclamos(id_reclamo) ON DELETE RESTRICT,
    token_unico             UUID NOT NULL DEFAULT gen_random_uuid(),
    -- snapshot del email al momento del envio (el ciudadano puede cambiarlo despues)
    email_destino_snapshot  VARCHAR(150) NOT NULL,
    fecha_envio             TIMESTAMPTZ,
    fecha_apertura          TIMESTAMPTZ,
    fecha_completada        TIMESTAMPTZ,
    fecha_expiracion        TIMESTAMPTZ NOT NULL,
    estado                  VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    intentos_envio          SMALLINT NOT NULL DEFAULT 0,
    ultimo_error_envio      TEXT,
    -- estandar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_encuesta_envio_estado
        CHECK (estado IN ('pendiente', 'enviada', 'abierta', 'completada', 'expirada', 'error_envio'))
);

-- lookup publico por token (link de la encuesta)
CREATE UNIQUE INDEX IF NOT EXISTS idx_encuesta_envio_token
    ON encuesta_envio (token_unico);
-- evitar enviar 2 veces por reclamo
CREATE INDEX IF NOT EXISTS idx_encuesta_envio_reclamo
    ON encuesta_envio (id_reclamo);
-- job de expiracion
CREATE INDEX IF NOT EXISTS idx_encuesta_envio_estado
    ON encuesta_envio (estado, fecha_expiracion);

-- =============================================================================
-- 5. encuesta_respuesta (un envio = una respuesta)
-- =============================================================================
CREATE TABLE IF NOT EXISTS encuesta_respuesta (
    id_encuesta_respuesta   SERIAL PRIMARY KEY,
    id_envio                INTEGER NOT NULL UNIQUE
        REFERENCES encuesta_envio(id_encuesta_envio) ON DELETE CASCADE,
    clasificacion_inicial   SMALLINT NOT NULL,
    rama_seguida            VARCHAR(20) NOT NULL,
    tiempo_completado_seg   INTEGER,
    solicita_contacto       BOOLEAN NOT NULL DEFAULT FALSE,
    ip_origen               VARCHAR(45),
    -- estandar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_encuesta_respuesta_clasificacion
        CHECK (clasificacion_inicial BETWEEN 1 AND 5),
    CONSTRAINT ck_encuesta_respuesta_rama
        CHECK (rama_seguida IN ('satisfechos', 'neutrales', 'insatisfechos'))
);

-- =============================================================================
-- 6. encuesta_respuesta_detalle (cada pregunta respondida)
-- =============================================================================
CREATE TABLE IF NOT EXISTS encuesta_respuesta_detalle (
    id_encuesta_respuesta_detalle SERIAL PRIMARY KEY,
    id_respuesta            INTEGER NOT NULL
        REFERENCES encuesta_respuesta(id_encuesta_respuesta) ON DELETE CASCADE,
    id_pregunta             INTEGER NOT NULL
        REFERENCES encuesta_pregunta(id_encuesta_pregunta) ON DELETE RESTRICT,
    valor_numerico          SMALLINT,
    valor_texto             TEXT,
    id_opcion_seleccionada  INTEGER
        REFERENCES encuesta_opcion(id_encuesta_opcion) ON DELETE SET NULL,
    -- estandar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_encuesta_resp_detalle_respuesta
    ON encuesta_respuesta_detalle (id_respuesta);
CREATE INDEX IF NOT EXISTS idx_encuesta_resp_detalle_pregunta
    ON encuesta_respuesta_detalle (id_pregunta);

-- =============================================================================
-- Config de sistema: toggle global de encuestas (§18 configuracion_general)
-- Reusa la tabla key/value existente; NO se crea tabla nueva.
-- Si 'encuestas_activas' = 'false', el backend no debe disparar ninguna encuesta.
-- Default 'true'. Idempotente por la UNIQUE en clave.
-- =============================================================================
INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
VALUES (
    'encuestas_activas',
    'true',
    'boolean',
    'Habilita el disparo de encuestas de satisfaccion (CSAT) al cierre de reclamos. false desactiva el envio en todo el municipio.',
    TRUE
)
ON CONFLICT (clave) DO NOTHING;

COMMIT;
