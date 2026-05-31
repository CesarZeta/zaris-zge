-- =====================================================================
-- Migración 73: Aprobaciones por etapa (visados) en Trámites
-- =====================================================================
-- Marca paralela a los estados que indica que un área aprobó/rechazó una
-- etapa (o un documento). Opcionalmente bloquea el avance del trámite.
--   - Catálogo versionado: tipo_tramite_aprobacion_requerida (se copia al
--     crear borrador, igual que campos/estados/transiciones/docs).
--   - Instancia: tramite_aprobacion (una fila por marca pendiente/resuelta).
-- Diseño cerrado con el usuario 2026-05-31. Patrón catálogo+instancia (§35).
-- Depende de: 47 (catálogos), 48 (instancias).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Catálogo: tipo_tramite_aprobacion_requerida (versionado con el circuito)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tipo_tramite_aprobacion_requerida (
    id_tipo_tramite_aprobacion_requerida SERIAL PRIMARY KEY,
    id_tipo_tramite_version  INTEGER NOT NULL REFERENCES tipo_tramite_version(id_tipo_tramite_version) ON DELETE CASCADE,
    id_tipo_tramite_estado   INTEGER NOT NULL REFERENCES tipo_tramite_estado(id_tipo_tramite_estado) ON DELETE CASCADE,

    -- Aprobador polimórfico (exactamente uno)
    aprobador_tipo           VARCHAR(15) NOT NULL CHECK (aprobador_tipo IN ('subarea','equipo','agente')),
    id_subarea_aprobadora    INTEGER REFERENCES subarea(id_subarea),
    id_equipo_aprobador      INTEGER REFERENCES equipos(id_equipo),
    id_agente_aprobador      INTEGER REFERENCES agentes(id_agente),

    etiqueta                 VARCHAR(150) NOT NULL,
    bloqueante               BOOLEAN NOT NULL DEFAULT TRUE,
    -- Documento opcional sobre el que recae la aprobación
    id_tipo_tramite_documento_requerido INTEGER
        REFERENCES tipo_tramite_documento_requerido(id_tipo_tramite_documento_requerido) ON DELETE SET NULL,
    orden                    SMALLINT NOT NULL DEFAULT 1,

    -- Estándar §10
    activo                   BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio             INTEGER NOT NULL DEFAULT 1,
    id_subarea               INTEGER,
    fecha_alta               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta          INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion  INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,

    CONSTRAINT ck_ttar_aprobador_exactamente_uno CHECK (
        (aprobador_tipo = 'subarea' AND id_subarea_aprobadora IS NOT NULL AND id_equipo_aprobador IS NULL AND id_agente_aprobador IS NULL)
     OR (aprobador_tipo = 'equipo'  AND id_equipo_aprobador  IS NOT NULL AND id_subarea_aprobadora IS NULL AND id_agente_aprobador IS NULL)
     OR (aprobador_tipo = 'agente'  AND id_agente_aprobador  IS NOT NULL AND id_subarea_aprobadora IS NULL AND id_equipo_aprobador IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_ttar_version_estado
    ON tipo_tramite_aprobacion_requerida (id_tipo_tramite_version, id_tipo_tramite_estado)
    WHERE activo = TRUE;

-- ---------------------------------------------------------------------
-- 2. Instancia: tramite_aprobacion (marca real por trámite)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tramite_aprobacion (
    id_tramite_aprobacion    SERIAL PRIMARY KEY,
    id_tramite               INTEGER NOT NULL REFERENCES tramite(id_tramite) ON DELETE CASCADE,
    id_tipo_tramite_aprobacion_requerida INTEGER NOT NULL
        REFERENCES tipo_tramite_aprobacion_requerida(id_tipo_tramite_aprobacion_requerida),
    -- Desnormalizado para guard rápido por estado
    id_tipo_tramite_estado   INTEGER NOT NULL REFERENCES tipo_tramite_estado(id_tipo_tramite_estado),

    estado                   VARCHAR(12) NOT NULL DEFAULT 'pendiente'
                             CHECK (estado IN ('pendiente','aprobada','rechazada')),
    resuelto_por_agente      INTEGER REFERENCES agentes(id_agente),
    resuelto_en              TIMESTAMPTZ,
    comentario               TEXT,
    -- Documento adjunto sobre el que se resolvió (opcional)
    id_tramite_documento     INTEGER REFERENCES tramite_documento(id_tramite_documento) ON DELETE SET NULL,

    -- Estándar §10
    activo                   BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio             INTEGER NOT NULL DEFAULT 1,
    id_subarea               INTEGER,
    fecha_alta               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta          INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion  INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,

    -- Una sola instancia activa por (trámite, requisito) — idempotencia de la
    -- instanciación al entrar a una etapa.
    CONSTRAINT uq_tramite_aprobacion_activa UNIQUE (id_tramite, id_tipo_tramite_aprobacion_requerida)
);

CREATE INDEX IF NOT EXISTS idx_tramite_aprobacion_tramite_estado
    ON tramite_aprobacion (id_tramite, id_tipo_tramite_estado)
    WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_tramite_aprobacion_pendientes
    ON tramite_aprobacion (id_tramite)
    WHERE activo = TRUE AND estado = 'pendiente';

-- ---------------------------------------------------------------------
-- 3. Movimiento 'aprobacion' en el ledger (timeline)
-- ---------------------------------------------------------------------
ALTER TABLE tramite_movimiento DROP CONSTRAINT IF EXISTS tramite_movimiento_tipo_check;
ALTER TABLE tramite_movimiento ADD CONSTRAINT tramite_movimiento_tipo_check
  CHECK ((tipo)::text = ANY (ARRAY[
    'creacion','numeracion','pase','toma','liberacion','cambio_estado','transicion',
    'adjunto','firma_solicitada','firma_realizada','firma_rechazada','comentario',
    'relacion','desistido','reapertura','aprobacion'
  ]::text[]));

COMMENT ON TABLE tipo_tramite_aprobacion_requerida IS 'Catálogo versionado de aprobaciones/visados requeridos por etapa de un tipo de trámite';
COMMENT ON TABLE tramite_aprobacion IS 'Instancia de una aprobación de etapa para un trámite concreto (pendiente/aprobada/rechazada)';
COMMENT ON COLUMN tipo_tramite_aprobacion_requerida.bloqueante IS 'Si TRUE, el trámite no puede avanzar de la etapa hasta que esta marca esté aprobada';
