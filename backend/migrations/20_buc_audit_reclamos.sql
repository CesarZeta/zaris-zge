-- ============================================================
-- Migración 20: Auditoría en tablas BUC + tabla reclamos transaccional
-- + quitar reclamos_area/reclamos_subarea (usar area/subarea generales)
-- + agregar tabla cargos real (desde seed), tipo_reclamo con id_area
-- ============================================================

-- ── 1. Auditoría y baja lógica en tablas BUC legacy ──────────────────────────

-- nacionalidades
ALTER TABLE nacionalidades
    ADD COLUMN IF NOT EXISTS activo              BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS id_subarea          INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- tipo_representacion
ALTER TABLE tipo_representacion
    ADD COLUMN IF NOT EXISTS activo              BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS id_subarea          INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- actividades
ALTER TABLE actividades
    ADD COLUMN IF NOT EXISTS activo              BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS id_subarea          INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- ciudadanos: ya tiene activo y modificado_por; agregar campos de auditoría faltantes
ALTER TABLE ciudadanos
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS id_subarea          INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_modificacion  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- renombrar fecha_modif → fecha_modificacion en ciudadanos (si fecha_modificacion no existe aún)
-- (lo hacemos solo si fecha_modif existe y fecha_modificacion fue recién creada)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='ciudadanos' AND column_name='fecha_modif'
    ) THEN
        UPDATE ciudadanos SET fecha_modificacion = fecha_modif WHERE fecha_modificacion IS NULL AND fecha_modif IS NOT NULL;
    END IF;
END $$;

-- empresas: misma lógica
ALTER TABLE empresas
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS id_subarea          INTEGER,
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- empresas mantiene fecha_modif (legacy BUC); los campos audit id_usuario_alta/modificacion
-- se agregan arriba. No renombrar fecha_modif — el ORM y el código existente lo usan.

-- ── 2. Tabla area (secretarías municipales) ─────────────────────────────────
-- Ya existe la tabla 'area' (para maestros generales).
-- Nos aseguramos de que tenga todos los campos estándar.
ALTER TABLE area
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS id_subarea          INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- ── 3. Tabla subarea (con FK a area) ─────────────────────────────────────────
ALTER TABLE subarea
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS id_subarea_padre    INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- ── 4. Tabla cargos ──────────────────────────────────────────────────────────
-- Si no existe crearla con todos los campos estándar
CREATE TABLE IF NOT EXISTS cargos (
    id_cargo             SERIAL PRIMARY KEY,
    nombre               VARCHAR(200) NOT NULL,
    descripcion          TEXT,
    activo               BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio         INTEGER,
    id_subarea           INTEGER,
    fecha_alta           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta      INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

-- Si cargos ya existía con id_cargo como texto o estructura diferente, agregar campos faltantes
ALTER TABLE cargos
    ADD COLUMN IF NOT EXISTS descripcion         TEXT,
    ADD COLUMN IF NOT EXISTS activo              BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS id_subarea          INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- ── 5. Tabla tipo_reclamo (redefinida con id_area referenciando area) ─────────
-- Recrear con campos completos si no existe; si existe, agregar columnas faltantes
CREATE TABLE IF NOT EXISTS tipo_reclamo (
    id_tipo_reclamo      SERIAL PRIMARY KEY,
    nombre               VARCHAR(200) NOT NULL,
    descripcion          TEXT,
    id_area              INTEGER REFERENCES area(id_area) ON DELETE SET NULL,
    sla_dias             INTEGER DEFAULT 5,
    activo               BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio         INTEGER,
    id_subarea           INTEGER,
    fecha_alta           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta      INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

ALTER TABLE tipo_reclamo
    ADD COLUMN IF NOT EXISTS id_area             INTEGER REFERENCES area(id_area) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS sla_dias            INTEGER DEFAULT 5,
    ADD COLUMN IF NOT EXISTS activo              BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS id_subarea          INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- ── 6. Tabla reclamos (transaccional) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reclamos (
    id_reclamo           SERIAL PRIMARY KEY,
    nro_reclamo          VARCHAR(20) UNIQUE,        -- ej: "REC-2026-001001"
    id_ciudadano         INTEGER REFERENCES ciudadanos(id_ciudadano) ON DELETE RESTRICT,
    id_tipo_reclamo      INTEGER REFERENCES tipo_reclamo(id_tipo_reclamo) ON DELETE SET NULL,
    id_area              INTEGER REFERENCES area(id_area) ON DELETE SET NULL,
    descripcion          TEXT NOT NULL,
    domicilio_reclamo    VARCHAR(300),
    prioridad            VARCHAR(10) NOT NULL DEFAULT 'Media'
                             CHECK (prioridad IN ('Alta','Media','Baja')),
    estado               VARCHAR(30) NOT NULL DEFAULT 'Ingresado'
                             CHECK (estado IN ('Ingresado','En revisión','En gestión','Resuelto','Rechazado','Cerrado')),
    id_agente_asignado   INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    observaciones        TEXT,
    activo               BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio         INTEGER,
    id_subarea           INTEGER,
    fecha_alta           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta      INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_reclamos_ciudadano  ON reclamos(id_ciudadano);
CREATE INDEX IF NOT EXISTS idx_reclamos_area       ON reclamos(id_area);
CREATE INDEX IF NOT EXISTS idx_reclamos_estado     ON reclamos(estado);
CREATE INDEX IF NOT EXISTS idx_reclamos_fecha_alta ON reclamos(fecha_alta);

-- ── 7. Tabla reclamo_historial (timeline de cambios de estado) ────────────────
CREATE TABLE IF NOT EXISTS reclamo_historial (
    id_historial         SERIAL PRIMARY KEY,
    id_reclamo           INTEGER NOT NULL REFERENCES reclamos(id_reclamo) ON DELETE CASCADE,
    accion               VARCHAR(100) NOT NULL,
    estado_anterior      VARCHAR(30),
    estado_nuevo         VARCHAR(30),
    nota                 TEXT,
    fecha_alta           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta      INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_reclamo_hist_reclamo ON reclamo_historial(id_reclamo);

-- ── 8. Función para generar nro_reclamo automáticamente ──────────────────────
CREATE OR REPLACE FUNCTION fn_generar_nro_reclamo()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.nro_reclamo IS NULL THEN
        NEW.nro_reclamo := 'REC-' || TO_CHAR(NOW(), 'YYYY') || '-' || LPAD(NEW.id_reclamo::TEXT, 6, '0');
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_nro_reclamo ON reclamos;
CREATE TRIGGER trg_nro_reclamo
    BEFORE INSERT ON reclamos
    FOR EACH ROW EXECUTE FUNCTION fn_generar_nro_reclamo();

-- ── 9. Limpiar reclamos_area y reclamos_subarea (las tablas existentes area/subarea las reemplazan) ──
-- NO dropeamos para no perder datos existentes; simplemente dejamos de usarlas en el código.
-- Si hay datos en reclamos_tipo que apuntan a reclamos_subarea, los dejamos intactos.

-- ── 10. agentes: agregar campos de auditoría faltantes ───────────────────────
ALTER TABLE agentes
    ADD COLUMN IF NOT EXISTS id_municipio        INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS id_usuario_alta     INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

-- FIN MIGRACIÓN 20
