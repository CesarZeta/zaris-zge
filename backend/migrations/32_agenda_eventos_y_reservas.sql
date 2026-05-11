-- =============================================================================
-- Migracion 32 — Agenda sub-fase 1.A — Eventos y reservas
-- =============================================================================
-- Tablas: eventos, evento_encargados, evento_reservas.
-- Todas las FKs apuntan a las PKs reales del proyecto:
--   subarea.id_subarea, ciudadanos.id_ciudadano, estado_evento.id_estado_evento,
--   estado_reserva.id_estado_reserva, usuarios.id_usuario.
-- =============================================================================

BEGIN;

-- eventos ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eventos (
    id_evento               SERIAL PRIMARY KEY,
    nombre                  VARCHAR(200) NOT NULL,
    descripcion             TEXT,
    id_subarea              INTEGER REFERENCES subarea(id_subarea) ON DELETE SET NULL,
    fecha                   DATE NOT NULL,
    hora_inicio             TIME NOT NULL,
    hora_fin                TIME NOT NULL,
    capacidad_ciudadanos    INTEGER NOT NULL DEFAULT 1,
    cantidad_encargados     INTEGER NOT NULL DEFAULT 0,
    tipo_qr                 VARCHAR(10) NOT NULL DEFAULT 'ninguno',
    admite_autoservicio     BOOLEAN NOT NULL DEFAULT FALSE,
    id_estado_evento        INTEGER NOT NULL REFERENCES estado_evento(id_estado_evento) ON DELETE RESTRICT,
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_eventos_tipo_qr     CHECK (tipo_qr IN ('nominal','generico','ninguno')),
    CONSTRAINT ck_eventos_horario     CHECK (hora_fin > hora_inicio),
    CONSTRAINT ck_eventos_capacidad   CHECK (capacidad_ciudadanos >= 0),
    CONSTRAINT ck_eventos_encargados  CHECK (cantidad_encargados  >= 0)
);

CREATE INDEX IF NOT EXISTS idx_eventos_fecha_mun ON eventos (fecha, id_municipio);
CREATE INDEX IF NOT EXISTS idx_eventos_subarea   ON eventos (id_subarea);
CREATE INDEX IF NOT EXISTS idx_eventos_estado    ON eventos (id_estado_evento);

-- evento_encargados --------------------------------------------------------
-- recurso = agente o equipo. id_recurso apunta a agentes.id_agente o equipos.id_equipo.
-- No se usa FK fisica porque depende de tipo_recurso; consistencia validada
-- por el backend o por triggers futuros si se requiere.
CREATE TABLE IF NOT EXISTS evento_encargados (
    id_evento_encargado     SERIAL PRIMARY KEY,
    id_evento               INTEGER NOT NULL REFERENCES eventos(id_evento) ON DELETE CASCADE,
    tipo_recurso            VARCHAR(10) NOT NULL,
    id_recurso              INTEGER NOT NULL,
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_evt_enc_tipo_recurso CHECK (tipo_recurso IN ('agente','equipo')),
    CONSTRAINT uq_evt_enc UNIQUE (id_evento, tipo_recurso, id_recurso)
);

CREATE INDEX IF NOT EXISTS idx_evt_enc_evento  ON evento_encargados (id_evento);
CREATE INDEX IF NOT EXISTS idx_evt_enc_recurso ON evento_encargados (tipo_recurso, id_recurso);

-- evento_reservas ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS evento_reservas (
    id_evento_reserva       SERIAL PRIMARY KEY,
    id_evento               INTEGER NOT NULL REFERENCES eventos(id_evento) ON DELETE CASCADE,
    id_ciudadano            INTEGER NOT NULL REFERENCES ciudadanos(id_ciudadano) ON DELETE RESTRICT,
    id_estado_reserva       INTEGER NOT NULL REFERENCES estado_reserva(id_estado_reserva) ON DELETE RESTRICT,
    origen                  VARCHAR(15) NOT NULL,
    qr_codigo               VARCHAR(255),
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_evt_res_origen CHECK (origen IN ('backoffice','autoservicio'))
);

CREATE INDEX IF NOT EXISTS idx_evt_res_evento    ON evento_reservas (id_evento);
CREATE INDEX IF NOT EXISTS idx_evt_res_ciudadano ON evento_reservas (id_ciudadano);
CREATE INDEX IF NOT EXISTS idx_evt_res_estado    ON evento_reservas (id_estado_reserva);

COMMIT;
