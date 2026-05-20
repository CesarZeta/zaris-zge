-- Migracion 54: Adjuntos de Ordenes de Trabajo (hallazgo QA Royman #4).
-- Espeja reclamo_adjuntos (mig 22) pero apunta a ordenes_trabajo(id_ot).
-- Evidencia del trabajo realizado: el agente asignado (o supervisor) sube
-- fotos; todas las mesas las ven. Binarios en Supabase Storage; aqui solo
-- metadatos. Reusa el bucket 'reclamos-adjuntos' (privado, ya existente).
-- Idempotente: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.

BEGIN;

CREATE TABLE IF NOT EXISTS ot_adjuntos (
    id_adjunto              SERIAL PRIMARY KEY,
    id_ot                   INTEGER NOT NULL REFERENCES ordenes_trabajo(id_ot) ON DELETE CASCADE,
    storage_bucket          VARCHAR(100) NOT NULL DEFAULT 'reclamos-adjuntos',
    storage_path            VARCHAR(500) NOT NULL,
    nombre_archivo          VARCHAR(255) NOT NULL,
    mime_type               VARCHAR(100),
    tamano_bytes            BIGINT,
    descripcion             TEXT,
    -- estandar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ot_adjuntos_ot ON ot_adjuntos (id_ot);

COMMIT;
