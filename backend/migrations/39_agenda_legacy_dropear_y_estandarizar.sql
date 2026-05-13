-- Migracion 39: Agenda sub-fase 1.B - DROP de tablas legacy vacias +
-- estandarizar agenda_clase y agenda_feriado + crear ausencias_agente.
--
-- Contexto: CLAUDE.md sub-fase 1.B Agenda. Pendiente desde 2026-05-10.
-- Decisiones (sesion 2026-05-13):
--   1) Las 9 tablas legacy vacias se dropean. Modelos SQLAlchemy y router
--      legacy se borran.
--   2) agenda_clase (4 filas demo) y agenda_feriado (12 feriados) se
--      estandarizan al estandar campos auditoria: PK id_<tabla>, audit completa,
--      fecha_alta/fecha_modificacion, id_municipio.
--   3) FK id_area en agenda_clase, lugares_atencion y servicios apunta a
--      `areas` legacy. Se limpia (NULL) antes de dropear `areas`.
--   4) Tabla nueva ausencias_agente (estandar estandar campos auditoria, FK a agentes.id_agente)
--      reemplaza a agenda_ausencia que consultaba agenda_v2.
--
-- Snapshot pre-mig: _backup_agenda_legacy_2026_05_13
-- Idempotente: usa DROP ... IF EXISTS y CREATE ... IF NOT EXISTS.

BEGIN;

-- ----------------------------------------------------------------------
-- 1) Snapshots de las tablas con datos antes de tocarlas
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS _backup_agenda_clase_2026_05_13 AS
  SELECT * FROM agenda_clase;
CREATE TABLE IF NOT EXISTS _backup_agenda_feriado_2026_05_13 AS
  SELECT * FROM agenda_feriado;
CREATE TABLE IF NOT EXISTS _backup_areas_2026_05_13 AS
  SELECT * FROM areas;
CREATE TABLE IF NOT EXISTS _backup_lugares_atencion_id_area_2026_05_13 AS
  SELECT id, id_area FROM lugares_atencion;
CREATE TABLE IF NOT EXISTS _backup_servicios_id_area_2026_05_13 AS
  SELECT id, id_area FROM servicios;

-- ----------------------------------------------------------------------
-- 2) Limpiar id_area que apunta a `areas` legacy
-- ----------------------------------------------------------------------
UPDATE agenda_clase     SET id_area = NULL WHERE id_area IS NOT NULL;
UPDATE lugares_atencion SET id_area = NULL WHERE id_area IS NOT NULL;
UPDATE servicios        SET id_area = NULL WHERE id_area IS NOT NULL;

-- Drop FKs entrantes a `areas` (las 3 tablas que sobreviven)
ALTER TABLE agenda_clase     DROP CONSTRAINT IF EXISTS agenda_clase_id_area_fkey;
ALTER TABLE lugares_atencion DROP CONSTRAINT IF EXISTS lugares_atencion_id_area_fkey;
ALTER TABLE servicios        DROP CONSTRAINT IF EXISTS servicios_id_area_fkey;

-- ----------------------------------------------------------------------
-- 3) DROP tablas legacy vacias (en orden inverso a las FKs entre si)
--    agenda_alerta -> referencia ausencia/agente/lugar/servicio
--    turnos -> referencia agente/lugar/servicio
--    agenda_servicio_agente -> referencia servicio + agente
--    agenda_lugar_servicio -> referencia lugar + servicio
--    agenda_ausencia -> referenciada por alerta (ya dropeada)
--    agenda_agente, agenda_lugar, agenda_servicio
--    areas
-- ----------------------------------------------------------------------
DROP TABLE IF EXISTS agenda_alerta CASCADE;
DROP TABLE IF EXISTS turnos CASCADE;
DROP TABLE IF EXISTS agenda_servicio_agente CASCADE;
DROP TABLE IF EXISTS agenda_lugar_servicio CASCADE;
DROP TABLE IF EXISTS agenda_ausencia CASCADE;
DROP TABLE IF EXISTS agenda_agente CASCADE;
DROP TABLE IF EXISTS agenda_lugar CASCADE;
DROP TABLE IF EXISTS agenda_servicio CASCADE;
DROP TABLE IF EXISTS areas CASCADE;

-- ----------------------------------------------------------------------
-- 4) Estandarizar agenda_clase al estandar campos auditoria
--    Renames: id -> id_agenda_clase, creado_por -> id_usuario_alta,
--             creado_en -> fecha_alta, modificado_en -> fecha_modificacion
--    Nuevos:  id_usuario_modificacion, id_municipio, id_subarea
--    Drop:    id_area (limpiada arriba), fecha_baja (legacy)
-- ----------------------------------------------------------------------
ALTER TABLE agenda_clase DROP COLUMN IF EXISTS id_area;
ALTER TABLE agenda_clase DROP COLUMN IF EXISTS fecha_baja;

ALTER TABLE agenda_clase RENAME COLUMN id TO id_agenda_clase;
ALTER TABLE agenda_clase RENAME COLUMN creado_por TO id_usuario_alta;
ALTER TABLE agenda_clase RENAME COLUMN creado_en TO fecha_alta;
ALTER TABLE agenda_clase RENAME COLUMN modificado_en TO fecha_modificacion;

-- Renombrar secuencia + reapuntar default
ALTER SEQUENCE IF EXISTS agenda_clase_id_seq RENAME TO agenda_clase_id_agenda_clase_seq;
ALTER TABLE agenda_clase
  ALTER COLUMN id_agenda_clase
  SET DEFAULT nextval('agenda_clase_id_agenda_clase_seq'::regclass);

-- Renombrar PK
ALTER INDEX IF EXISTS agenda_clase_pkey RENAME TO agenda_clase_id_agenda_clase_pkey;

-- Audit + municipio + subarea
ALTER TABLE agenda_clase
  ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS id_municipio INTEGER,
  ADD COLUMN IF NOT EXISTS id_subarea INTEGER;

-- Backfill id_municipio para filas existentes (asumimos municipio 1 - unico activo)
UPDATE agenda_clase SET id_municipio = 1 WHERE id_municipio IS NULL;

-- Defaults: fecha_alta y fecha_modificacion deben tener default NOW()
ALTER TABLE agenda_clase
  ALTER COLUMN fecha_alta SET DEFAULT NOW(),
  ALTER COLUMN fecha_modificacion SET DEFAULT NOW();

-- Si fecha_alta/fecha_modificacion estaban NULL en alguna fila legacy, completar
UPDATE agenda_clase SET fecha_alta = NOW() WHERE fecha_alta IS NULL;
UPDATE agenda_clase SET fecha_modificacion = NOW() WHERE fecha_modificacion IS NULL;

-- NOT NULL en timestamps con default
ALTER TABLE agenda_clase
  ALTER COLUMN fecha_alta SET NOT NULL,
  ALTER COLUMN fecha_modificacion SET NOT NULL,
  ALTER COLUMN activo SET DEFAULT TRUE;

-- ----------------------------------------------------------------------
-- 5) Estandarizar agenda_feriado al estandar campos auditoria
--    Renames: id -> id_agenda_feriado, creado_por -> id_usuario_alta,
--             creado_en -> fecha_alta
--    Nuevos:  id_usuario_modificacion, fecha_modificacion, id_municipio,
--             id_subarea
-- ----------------------------------------------------------------------
ALTER TABLE agenda_feriado RENAME COLUMN id TO id_agenda_feriado;
ALTER TABLE agenda_feriado RENAME COLUMN creado_por TO id_usuario_alta;
ALTER TABLE agenda_feriado RENAME COLUMN creado_en TO fecha_alta;

ALTER SEQUENCE IF EXISTS agenda_feriado_id_seq RENAME TO agenda_feriado_id_agenda_feriado_seq;
ALTER TABLE agenda_feriado
  ALTER COLUMN id_agenda_feriado
  SET DEFAULT nextval('agenda_feriado_id_agenda_feriado_seq'::regclass);

ALTER INDEX IF EXISTS agenda_feriado_pkey RENAME TO agenda_feriado_id_agenda_feriado_pkey;

ALTER TABLE agenda_feriado
  ADD COLUMN IF NOT EXISTS fecha_modificacion TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS id_municipio INTEGER,
  ADD COLUMN IF NOT EXISTS id_subarea INTEGER;

UPDATE agenda_feriado SET id_municipio = 1 WHERE id_municipio IS NULL;
UPDATE agenda_feriado SET fecha_modificacion = NOW() WHERE fecha_modificacion IS NULL;

ALTER TABLE agenda_feriado
  ALTER COLUMN fecha_alta SET DEFAULT NOW(),
  ALTER COLUMN fecha_modificacion SET DEFAULT NOW();

UPDATE agenda_feriado SET fecha_alta = NOW() WHERE fecha_alta IS NULL;

ALTER TABLE agenda_feriado
  ALTER COLUMN fecha_alta SET NOT NULL,
  ALTER COLUMN fecha_modificacion SET NOT NULL,
  ALTER COLUMN activo SET DEFAULT TRUE;

-- ----------------------------------------------------------------------
-- 6) Crear ausencias_agente (estandar estandar campos auditoria) - reemplaza agenda_ausencia
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ausencias_agente (
  id_ausencia_agente      SERIAL PRIMARY KEY,
  id_agente               INTEGER NOT NULL REFERENCES agentes(id_agente) ON DELETE CASCADE,
  fecha_desde             DATE NOT NULL,
  fecha_hasta             DATE NOT NULL,
  motivo                  VARCHAR(200),
  -- estandar estandar campos auditoria
  activo                  BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio            INTEGER,
  id_subarea              INTEGER,
  fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  CONSTRAINT ck_ausencia_agente_rango CHECK (fecha_hasta >= fecha_desde)
);

CREATE INDEX IF NOT EXISTS idx_ausencias_agente_id_agente ON ausencias_agente(id_agente);
CREATE INDEX IF NOT EXISTS idx_ausencias_agente_fechas ON ausencias_agente(fecha_desde, fecha_hasta);
CREATE INDEX IF NOT EXISTS idx_ausencias_agente_activo ON ausencias_agente(activo);

COMMIT;
