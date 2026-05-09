-- ════════════════════════════════════════════════════════════════════════════
-- ZARIS — Migración 22: Geolocalización + Activos + Adjuntos en Reclamos
-- ════════════════════════════════════════════════════════════════════════════
-- Cambios:
--   1. Tablas geo: provincias / partidos / localidades (PBA + CABA + resto AR)
--   2. Tablas de activos: tipos_activo / activos
--   3. Tabla de adjuntos: reclamo_adjuntos (storage path en Supabase Storage)
--   4. Reclamos: estado VARCHAR → id_estado FK, + lat/lon, localidad, activo,
--      canal_origen, fuente_geolocalizacion, fecha_cierre,
--      fecha_primer_asignacion, sla_vencimiento, rename domicilio_reclamo → direccion.
--   5. Sub-reclamo: sin cambios (auto-referencia, max 1 nivel).
-- ════════════════════════════════════════════════════════════════════════════

-- ── 1. Provincias ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS provincias (
    id_provincia SERIAL PRIMARY KEY,
    nombre       VARCHAR(100) NOT NULL UNIQUE,
    iso_code     VARCHAR(10),
    activo       BOOLEAN NOT NULL DEFAULT TRUE
);

-- ── 2. Partidos / Departamentos ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS partidos (
    id_partido   SERIAL PRIMARY KEY,
    id_provincia INTEGER NOT NULL REFERENCES provincias(id_provincia) ON DELETE RESTRICT,
    nombre       VARCHAR(150) NOT NULL,
    activo       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(id_provincia, nombre)
);
CREATE INDEX IF NOT EXISTS idx_partidos_provincia ON partidos(id_provincia);

-- ── 3. Localidades ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS localidades (
    id_localidad  SERIAL PRIMARY KEY,
    id_partido    INTEGER NOT NULL REFERENCES partidos(id_partido) ON DELETE RESTRICT,
    nombre        VARCHAR(150) NOT NULL,
    codigo_postal VARCHAR(8),
    activo        BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(id_partido, nombre)
);
CREATE INDEX IF NOT EXISTS idx_localidades_partido ON localidades(id_partido);
CREATE INDEX IF NOT EXISTS idx_localidades_nombre  ON localidades(nombre);

-- ── 4. Tipos de activo ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tipos_activo (
    id_tipo_activo  SERIAL PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL UNIQUE,
    descripcion     TEXT,
    icono           VARCHAR(50),
    requiere_ciudadano BOOLEAN NOT NULL DEFAULT FALSE,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_alta      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

-- ── 5. Activos (luminarias, semáforos, contenedores, etc.) ───────────────────
CREATE TABLE IF NOT EXISTS activos (
    id_activo       SERIAL PRIMARY KEY,
    codigo_unico    VARCHAR(50) UNIQUE,
    id_tipo_activo  INTEGER NOT NULL REFERENCES tipos_activo(id_tipo_activo) ON DELETE RESTRICT,
    descripcion     TEXT,
    direccion       VARCHAR(300),
    id_localidad    INTEGER REFERENCES localidades(id_localidad) ON DELETE SET NULL,
    latitud         NUMERIC(10, 7),
    longitud        NUMERIC(10, 7),
    metros_cuadrados NUMERIC(10, 2),
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio    INTEGER,
    id_subarea      INTEGER,
    fecha_alta      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_activos_tipo       ON activos(id_tipo_activo);
CREATE INDEX IF NOT EXISTS idx_activos_localidad  ON activos(id_localidad);
CREATE INDEX IF NOT EXISTS idx_activos_codigo     ON activos(codigo_unico);
-- Indice geo para queries por bounding box
CREATE INDEX IF NOT EXISTS idx_activos_lat_lon    ON activos(latitud, longitud);

-- ── 6. Reclamos: agregar columnas geo + activo + canal + SLA ────────────────
ALTER TABLE reclamos
    ADD COLUMN IF NOT EXISTS id_estado_fk             INTEGER,
    ADD COLUMN IF NOT EXISTS direccion                VARCHAR(300),
    ADD COLUMN IF NOT EXISTS latitud                  NUMERIC(10, 7),
    ADD COLUMN IF NOT EXISTS longitud                 NUMERIC(10, 7),
    ADD COLUMN IF NOT EXISTS id_localidad             INTEGER,
    ADD COLUMN IF NOT EXISTS id_activo                INTEGER,
    ADD COLUMN IF NOT EXISTS canal_origen             VARCHAR(20),
    ADD COLUMN IF NOT EXISTS fuente_geolocalizacion   VARCHAR(20),
    ADD COLUMN IF NOT EXISTS fecha_cierre             TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS fecha_primer_asignacion  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS sla_vencimiento          TIMESTAMPTZ;

-- Migrar contenido de domicilio_reclamo → direccion (sólo si direccion vacía)
UPDATE reclamos
   SET direccion = domicilio_reclamo
 WHERE direccion IS NULL
   AND domicilio_reclamo IS NOT NULL;

-- FKs (idempotente vía DO block — Postgres no tiene IF NOT EXISTS para constraints)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_reclamos_estado') THEN
        ALTER TABLE reclamos
            ADD CONSTRAINT fk_reclamos_estado
            FOREIGN KEY (id_estado_fk) REFERENCES estado_reclamo(id_estado_reclamo) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_reclamos_localidad') THEN
        ALTER TABLE reclamos
            ADD CONSTRAINT fk_reclamos_localidad
            FOREIGN KEY (id_localidad) REFERENCES localidades(id_localidad) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_reclamos_activo') THEN
        ALTER TABLE reclamos
            ADD CONSTRAINT fk_reclamos_activo
            FOREIGN KEY (id_activo) REFERENCES activos(id_activo) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_reclamos_canal') THEN
        ALTER TABLE reclamos
            ADD CONSTRAINT ck_reclamos_canal
            CHECK (canal_origen IS NULL OR canal_origen IN
                   ('web','whatsapp','telefono','presencial','oficio','app_movil','otro'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_reclamos_fuente_geo') THEN
        ALTER TABLE reclamos
            ADD CONSTRAINT ck_reclamos_fuente_geo
            CHECK (fuente_geolocalizacion IS NULL OR fuente_geolocalizacion IN
                   ('pin_manual','geocoding_osm','gps_dispositivo','activo_referenciado'));
    END IF;
END $$;

-- Migrar estado VARCHAR → id_estado_fk (lookup por nombre)
UPDATE reclamos r
   SET id_estado_fk = e.id_estado_reclamo
  FROM estado_reclamo e
 WHERE r.id_estado_fk IS NULL
   AND r.estado = e.nombre;

CREATE INDEX IF NOT EXISTS idx_reclamos_estado_fk    ON reclamos(id_estado_fk);
CREATE INDEX IF NOT EXISTS idx_reclamos_localidad    ON reclamos(id_localidad);
CREATE INDEX IF NOT EXISTS idx_reclamos_activo_ref   ON reclamos(id_activo);
CREATE INDEX IF NOT EXISTS idx_reclamos_lat_lon      ON reclamos(latitud, longitud);
CREATE INDEX IF NOT EXISTS idx_reclamos_sla_venc     ON reclamos(sla_vencimiento) WHERE sla_vencimiento IS NOT NULL;

-- NOTA: la columna `estado` (VARCHAR) se mantiene por compatibilidad; se deprecará
-- una vez que el frontend y endpoints estén 100% migrados a id_estado_fk.

-- ── 7. Adjuntos de reclamo (Supabase Storage) ───────────────────────────────
CREATE TABLE IF NOT EXISTS reclamo_adjuntos (
    id_adjunto      SERIAL PRIMARY KEY,
    id_reclamo      INTEGER NOT NULL REFERENCES reclamos(id_reclamo) ON DELETE CASCADE,
    storage_bucket  VARCHAR(100) NOT NULL DEFAULT 'reclamos-adjuntos',
    storage_path    VARCHAR(500) NOT NULL,
    nombre_archivo  VARCHAR(255) NOT NULL,
    mime_type       VARCHAR(100),
    tamano_bytes    BIGINT,
    descripcion     TEXT,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio    INTEGER,
    id_subarea      INTEGER,
    fecha_alta      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_adjuntos_reclamo ON reclamo_adjuntos(id_reclamo);

-- ── 8. Trigger para calcular SLA al alta ─────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_set_sla_vencimiento()
RETURNS TRIGGER AS $$
DECLARE
    v_sla_dias INTEGER;
BEGIN
    IF NEW.sla_vencimiento IS NULL AND NEW.id_tipo_reclamo IS NOT NULL THEN
        SELECT sla_dias INTO v_sla_dias
          FROM tipo_reclamo
         WHERE id_tipo_reclamo = NEW.id_tipo_reclamo;
        IF v_sla_dias IS NOT NULL THEN
            NEW.sla_vencimiento := NEW.fecha_alta + (v_sla_dias || ' days')::INTERVAL;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sla_reclamo ON reclamos;
CREATE TRIGGER trg_sla_reclamo
    BEFORE INSERT ON reclamos
    FOR EACH ROW EXECUTE FUNCTION fn_set_sla_vencimiento();
