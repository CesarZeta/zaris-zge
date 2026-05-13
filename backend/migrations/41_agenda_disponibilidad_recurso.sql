-- =============================================================================
-- Migracion 41 - Agenda: disponibilidad_recurso (horarios laborales multi-rango)
--
-- Define horarios de trabajo / atencion de los recursos de agenda. Una fila
-- representa UN rango contiguo (dias_semana bitmask + hora_inicio + hora_fin)
-- que aplica a un recurso (agente | equipo | espacio). Multiples filas por
-- recurso soportan turnos rotativos:
--
--   Agente 42, turno manana:
--     dias_semana=31 (Lun-Vie), hi=08:00, hf=14:00, etiqueta='turno manana'
--   Agente 42, turno tarde (semana siguiente, vigente a partir de X):
--     dias_semana=31, hi=14:00, hf=20:00, etiqueta='turno tarde',
--     vigente_desde='2026-06-01'
--
-- Las columnas vigente_desde / vigente_hasta permiten:
--   - Cambios programados de horario (futuros).
--   - Auditoria historica (manteniendo registros pasados con vigente_hasta
--     seteado y activo=TRUE para no perder el historial).
--   - Rotaciones por semanas/meses (filas multiples con ventanas alternadas).
--
-- Convencion §27: dias_semana SMALLINT bitmask (Lun=1, Mar=2, Mie=4, Jue=8,
-- Vie=16, Sab=32, Dom=64; rango 0-127). Helper UI obligatorio.
--
-- Disponibilidad efectiva de un recurso EN UNA FECHA F y HORA H:
--   EXISTS (SELECT 1 FROM disponibilidad_recurso
--           WHERE tipo_recurso = X AND id_recurso = Y AND activo = TRUE
--             AND (dias_semana & (1 << ((dow_lunes_base(F))))) <> 0
--             AND H >= hora_inicio AND H < hora_fin
--             AND (vigente_desde IS NULL OR F >= vigente_desde)
--             AND (vigente_hasta IS NULL OR F <= vigente_hasta))
--
-- donde dow_lunes_base(F) = EXTRACT(ISODOW FROM F) - 1 (0=Lun, 6=Dom).
-- =============================================================================

CREATE TABLE IF NOT EXISTS disponibilidad_recurso (
  id_disponibilidad       SERIAL PRIMARY KEY,
  tipo_recurso            VARCHAR(10) NOT NULL,
  id_recurso              INTEGER NOT NULL,
  dias_semana             SMALLINT NOT NULL,
  hora_inicio             TIME NOT NULL,
  hora_fin                TIME NOT NULL,
  vigente_desde           DATE,
  vigente_hasta           DATE,
  etiqueta                VARCHAR(60),
  -- Estandar §10
  activo                  BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio            INTEGER NOT NULL DEFAULT 1,
  id_subarea              INTEGER REFERENCES subarea(id_subarea) ON DELETE SET NULL,
  fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  CONSTRAINT ck_disp_tipo_recurso CHECK (tipo_recurso IN ('agente','equipo','espacio')),
  CONSTRAINT ck_disp_dias_semana  CHECK (dias_semana BETWEEN 0 AND 127),
  CONSTRAINT ck_disp_horario      CHECK (hora_fin > hora_inicio),
  CONSTRAINT ck_disp_vigencia     CHECK (vigente_hasta IS NULL OR vigente_desde IS NULL OR vigente_hasta >= vigente_desde)
);

CREATE INDEX IF NOT EXISTS idx_disp_recurso_lookup
  ON disponibilidad_recurso (tipo_recurso, id_recurso) WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_disp_vigencia
  ON disponibilidad_recurso (vigente_desde, vigente_hasta) WHERE activo = TRUE;
