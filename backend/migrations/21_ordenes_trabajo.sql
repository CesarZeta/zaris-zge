-- ============================================================
-- Migración 21: Tablas ordenes_trabajo, estado_ot, equipo_agentes,
--               configuracion_general + trigger nro_ot
-- ============================================================

-- ── 1. estado_ot ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS estado_ot (
    id_estado_ot        SERIAL PRIMARY KEY,
    nombre              VARCHAR(100) NOT NULL UNIQUE,
    descripcion         TEXT,
    color               VARCHAR(20),
    es_final            BOOLEAN NOT NULL DEFAULT FALSE,
    orden               INTEGER NOT NULL DEFAULT 0,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio        INTEGER,
    fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO estado_ot (nombre, color, es_final, orden) VALUES
    ('En gestión', '#f59e0b', FALSE, 1),
    ('En espera',  '#6b7280', FALSE, 2),
    ('Pendiente',  '#3b82f6', FALSE, 3),
    ('Terminada',  '#10b981', TRUE,  4),
    ('Cancelada',  '#ef4444', TRUE,  5)
ON CONFLICT (nombre) DO NOTHING;

-- ── 2. ordenes_trabajo ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ordenes_trabajo (
    id_ot                   SERIAL PRIMARY KEY,
    nro_ot                  VARCHAR(20) UNIQUE,
    id_reclamo              INTEGER NOT NULL REFERENCES reclamos(id_reclamo) ON DELETE RESTRICT,
    id_estado               INTEGER NOT NULL REFERENCES estado_ot(id_estado_ot) ON DELETE RESTRICT,
    id_agente               INTEGER REFERENCES agentes(id_agente) ON DELETE SET NULL,
    id_equipo               INTEGER REFERENCES equipos(id_equipo) ON DELETE SET NULL,
    es_auditoria            BOOLEAN NOT NULL DEFAULT FALSE,
    resultado_auditoria     VARCHAR(20) CHECK (resultado_auditoria IN ('aprobada','rechazada')),
    observaciones_auditoria TEXT,
    id_ot_origen            INTEGER REFERENCES ordenes_trabajo(id_ot) ON DELETE SET NULL,
    id_supervisor_asigna    INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    fecha_creacion          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_cierre            TIMESTAMPTZ,
    observaciones           TEXT,
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ot_reclamo   ON ordenes_trabajo(id_reclamo);
CREATE INDEX IF NOT EXISTS idx_ot_agente    ON ordenes_trabajo(id_agente);
CREATE INDEX IF NOT EXISTS idx_ot_equipo    ON ordenes_trabajo(id_equipo);
CREATE INDEX IF NOT EXISTS idx_ot_estado    ON ordenes_trabajo(id_estado);
CREATE INDEX IF NOT EXISTS idx_ot_auditoria ON ordenes_trabajo(es_auditoria);

-- ── 3. Trigger nro_ot ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_generar_nro_ot()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.nro_ot IS NULL THEN
        NEW.nro_ot := 'OT-' || TO_CHAR(NOW(), 'YYYY') || '-' || LPAD(NEW.id_ot::TEXT, 6, '0');
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_nro_ot ON ordenes_trabajo;
CREATE TRIGGER trg_nro_ot
    BEFORE INSERT ON ordenes_trabajo
    FOR EACH ROW EXECUTE FUNCTION fn_generar_nro_ot();

-- ── 4. equipo_agentes ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS equipo_agentes (
    id_equipo_agente    SERIAL PRIMARY KEY,
    id_equipo           INTEGER NOT NULL REFERENCES equipos(id_equipo) ON DELETE CASCADE,
    id_agente           INTEGER NOT NULL REFERENCES agentes(id_agente) ON DELETE CASCADE,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio        INTEGER,
    id_subarea          INTEGER,
    fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ea_equipo ON equipo_agentes(id_equipo);
CREATE INDEX IF NOT EXISTS idx_ea_agente ON equipo_agentes(id_agente);

-- ── 5. configuracion_general ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS configuracion_general (
    id_config           SERIAL PRIMARY KEY,
    clave               VARCHAR(100) NOT NULL UNIQUE,
    valor               TEXT NOT NULL,
    tipo                VARCHAR(20) NOT NULL DEFAULT 'string',
    descripcion         TEXT,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO configuracion_general (clave, valor, tipo, descripcion) VALUES
    ('auditor_misma_subarea_permitido', 'false', 'boolean', 'Si false, auditor no puede pertenecer a la subárea del reclamo'),
    ('ot_pendiente_dias_vencimiento',   '7',     'integer', 'Días máximos que una OT Pendiente puede estar sin reasignarse')
ON CONFLICT (clave) DO NOTHING;

-- ── 6. Campos faltantes en reclamos (v1.2) ───────────────────────────────────
ALTER TABLE reclamos
    ADD COLUMN IF NOT EXISTS id_reclamo_padre INTEGER REFERENCES reclamos(id_reclamo) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_reclamos_padre ON reclamos(id_reclamo_padre);

-- Ampliar el CHECK de estado para incluir los nuevos estados v1.2
ALTER TABLE reclamos DROP CONSTRAINT IF EXISTS reclamos_estado_check;
ALTER TABLE reclamos DROP CONSTRAINT IF EXISTS ck_reclamo_estado;
ALTER TABLE reclamos ADD CONSTRAINT ck_reclamo_estado
    CHECK (estado IN ('Sin asignar','En gestión','En espera','En auditoría','Resuelto','Cancelado'));

-- Migrar registros con estados legacy al nuevo esquema
UPDATE reclamos SET estado = 'Sin asignar'  WHERE estado IN ('Ingresado', 'Sin asignar') AND estado NOT IN ('Sin asignar','En gestión','En espera','En auditoría','Resuelto','Cancelado');
UPDATE reclamos SET estado = 'Resuelto'     WHERE estado = 'Cerrado';
UPDATE reclamos SET estado = 'Cancelado'    WHERE estado IN ('Rechazado');

-- Agregar columna audit en tipo_reclamo si no existe
ALTER TABLE tipo_reclamo
    ADD COLUMN IF NOT EXISTS audit BOOLEAN NOT NULL DEFAULT FALSE;

-- FIN MIGRACIÓN 21
