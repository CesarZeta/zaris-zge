-- Migración 69: novedades de agentes (inasistencias/licencias) + switch global
--
-- Dos cosas:
--
-- 1) Tabla `agente_novedad`: ausencias de un agente en un rango de fechas
--    (inasistencia, licencia, vacaciones, etc.). Resta disponibilidad efectiva
--    para Turnos/Agenda. Si `hora_inicio`/`hora_fin` son NULL = todo el día;
--    si vienen, es una ausencia parcial (ej. solo la mañana).
--
-- 2) Clave `turnos_respeta_disponibilidad` en configuracion_general (default
--    'true'): switch global. Con 'true' los turnos solo se pueden reservar
--    dentro de la disponibilidad efectiva del recurso (horario - feriados -
--    novedades). Con 'false' se puede reservar cualquier horario (modo libre).
--
-- Estándar §10. Idempotente.

-- =============================================================================
-- 1) Novedades de agentes
-- =============================================================================
CREATE TABLE IF NOT EXISTS agente_novedad (
  id_agente_novedad       SERIAL PRIMARY KEY,
  id_agente               INTEGER NOT NULL REFERENCES agentes(id_agente) ON DELETE CASCADE,
  tipo                    VARCHAR(20) NOT NULL DEFAULT 'inasistencia',
  fecha_desde             DATE NOT NULL,
  fecha_hasta             DATE NOT NULL,
  hora_inicio             TIME,                 -- NULL = todo el día
  hora_fin                TIME,                 -- NULL = todo el día
  motivo                  VARCHAR(300),
  -- estándar §10
  activo                  BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio            INTEGER,
  id_subarea              INTEGER,
  fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

-- tipo válido
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'agente_novedad'::regclass AND conname = 'ck_agente_novedad_tipo'
  ) THEN
    ALTER TABLE agente_novedad
      ADD CONSTRAINT ck_agente_novedad_tipo
      CHECK (tipo IN ('inasistencia', 'licencia', 'vacaciones', 'comision', 'otro'));
  END IF;
END $$;

-- rango coherente
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'agente_novedad'::regclass AND conname = 'ck_agente_novedad_rango'
  ) THEN
    ALTER TABLE agente_novedad
      ADD CONSTRAINT ck_agente_novedad_rango
      CHECK (fecha_hasta >= fecha_desde
             AND (hora_inicio IS NULL) = (hora_fin IS NULL)
             AND (hora_inicio IS NULL OR hora_fin > hora_inicio));
  END IF;
END $$;

-- lookup por agente + rango de fechas (lo que pega disponibilidad_efectiva)
CREATE INDEX IF NOT EXISTS idx_agente_novedad_lookup
  ON agente_novedad (id_agente, fecha_desde, fecha_hasta) WHERE activo = TRUE;

-- =============================================================================
-- 2) Switch global: turnos respetan disponibilidad efectiva
-- =============================================================================
-- OJO: configuracion_general tiene `tipo` y `activo` NOT NULL sin default.
INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
VALUES (
  'turnos_respeta_disponibilidad',
  'true',
  'boolean',
  'Si es true, los turnos solo pueden reservarse dentro de la disponibilidad efectiva del recurso (horario de atención menos feriados y novedades de agentes). Si es false, se puede reservar cualquier horario.',
  TRUE
)
ON CONFLICT (clave) DO NOTHING;
