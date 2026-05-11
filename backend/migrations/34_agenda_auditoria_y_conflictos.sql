-- =============================================================================
-- Migracion 34 — Agenda sub-fase 1.A — Conflictos y auditoria
-- =============================================================================
-- conflictos_log    : detectados al asignar/reasignar (dos ocupaciones se pisan).
-- agenda_audit_log  : trazabilidad de cambios sobre eventos/ocupaciones/reservas.
-- =============================================================================

BEGIN;

-- conflictos_log ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS conflictos_log (
    id_conflicto             SERIAL PRIMARY KEY,
    fecha_deteccion          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tipo_recurso             VARCHAR(10) NOT NULL,
    id_recurso               INTEGER NOT NULL,
    id_ocupacion_origen      INTEGER REFERENCES ocupaciones(id_ocupacion) ON DELETE SET NULL,
    id_ocupacion_conflicto   INTEGER REFERENCES ocupaciones(id_ocupacion) ON DELETE SET NULL,
    resuelto                 BOOLEAN NOT NULL DEFAULT FALSE,
    observaciones            TEXT,
    id_municipio             INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta          INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_conf_tipo_recurso CHECK (tipo_recurso IN ('agente','equipo'))
);

CREATE INDEX IF NOT EXISTS idx_conflictos_recurso  ON conflictos_log (tipo_recurso, id_recurso);
CREATE INDEX IF NOT EXISTS idx_conflictos_resuelto ON conflictos_log (resuelto) WHERE resuelto = FALSE;

-- agenda_audit_log ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS agenda_audit_log (
    id_audit            SERIAL PRIMARY KEY,
    fecha               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario          INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    entidad             VARCHAR(20) NOT NULL,
    id_entidad          INTEGER NOT NULL,
    accion              VARCHAR(20) NOT NULL,
    datos_anteriores    JSONB,
    datos_nuevos        JSONB,
    id_municipio        INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_audit_entidad CHECK (entidad IN ('evento','ocupacion','reserva')),
    CONSTRAINT ck_audit_accion  CHECK (accion  IN ('crear','modificar','cancelar','asignar'))
);

CREATE INDEX IF NOT EXISTS idx_audit_entidad ON agenda_audit_log (entidad, id_entidad);
CREATE INDEX IF NOT EXISTS idx_audit_fecha   ON agenda_audit_log (fecha DESC);
CREATE INDEX IF NOT EXISTS idx_audit_usuario ON agenda_audit_log (id_usuario);

COMMIT;
