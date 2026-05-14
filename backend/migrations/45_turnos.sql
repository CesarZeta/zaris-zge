-- =============================================================================
-- Migracion 45 - Modulo Turnos: tipo_servicio_turno + turnos
--
-- El modulo Turnos gestiona turnos de atencion: un ciudadano reserva un bloque
-- de la disponibilidad de un agente para realizar un tramite (tipo de servicio).
--
-- Modelo de datos (decidido con el usuario 2026-05-14):
--   - tipo_servicio_turno: catalogo propio (gestionado desde admin_tablas),
--     con duracion_min para sugerir el bloque a ocupar.
--   - turnos: tabla dedicada. Cada turno referencia ciudadano + agente +
--     tipo_servicio + estado (reservado|cumplido|cancelado) + fecha/horario.
--     Mantiene id_ocupacion -> fila espejo en `ocupaciones` (tipo='turno')
--     para que el turno aparezca en la grilla del modulo Agenda. El backend
--     sincroniza ambas tablas (crear/cancelar).
--
-- Idempotente: CREATE TABLE IF NOT EXISTS + ON CONFLICT en seeds.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Catalogo: tipo_servicio_turno
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tipo_servicio_turno (
  id_tipo_servicio_turno  SERIAL PRIMARY KEY,
  nombre                  VARCHAR(150) NOT NULL,
  descripcion             TEXT,
  duracion_min            INTEGER NOT NULL DEFAULT 30,
  -- Estandar §10
  activo                  BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio            INTEGER NOT NULL DEFAULT 1,
  id_subarea              INTEGER REFERENCES subarea(id_subarea) ON DELETE SET NULL,
  fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  CONSTRAINT ck_tipo_servicio_turno_duracion CHECK (duracion_min > 0)
);

-- Seeds minimos idempotentes
INSERT INTO tipo_servicio_turno (nombre, descripcion, duracion_min)
SELECT v.nombre, v.descripcion, v.duracion_min
  FROM (VALUES
    ('Atencion general', 'Consulta o tramite general en ventanilla', 30),
    ('Licencia de conducir', 'Tramite de licencia de conducir', 45),
    ('Habilitacion comercial', 'Inicio o renovacion de habilitacion comercial', 60)
  ) AS v(nombre, descripcion, duracion_min)
 WHERE NOT EXISTS (
   SELECT 1 FROM tipo_servicio_turno t WHERE LOWER(t.nombre) = LOWER(v.nombre)
 );

-- -----------------------------------------------------------------------------
-- Transaccional: turnos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS turnos (
  id_turno                SERIAL PRIMARY KEY,
  id_ciudadano            INTEGER NOT NULL REFERENCES ciudadanos(id_ciudadano) ON DELETE RESTRICT,
  id_agente               INTEGER NOT NULL REFERENCES agentes(id_agente) ON DELETE RESTRICT,
  id_tipo_servicio_turno  INTEGER NOT NULL REFERENCES tipo_servicio_turno(id_tipo_servicio_turno) ON DELETE RESTRICT,
  id_ocupacion            INTEGER REFERENCES ocupaciones(id_ocupacion) ON DELETE SET NULL,
  fecha                   DATE NOT NULL,
  hora_inicio             TIME NOT NULL,
  hora_fin                TIME NOT NULL,
  estado                  VARCHAR(12) NOT NULL DEFAULT 'reservado',
  observaciones           TEXT,
  -- Estandar §10
  activo                  BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio            INTEGER NOT NULL DEFAULT 1,
  id_subarea              INTEGER REFERENCES subarea(id_subarea) ON DELETE SET NULL,
  fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  CONSTRAINT ck_turnos_horario CHECK (hora_fin > hora_inicio),
  CONSTRAINT ck_turnos_estado CHECK (estado IN ('reservado', 'cumplido', 'cancelado'))
);

CREATE INDEX IF NOT EXISTS idx_turnos_agente_fecha ON turnos (id_agente, fecha);
CREATE INDEX IF NOT EXISTS idx_turnos_ciudadano ON turnos (id_ciudadano);
CREATE INDEX IF NOT EXISTS idx_turnos_estado ON turnos (estado);
CREATE INDEX IF NOT EXISTS idx_turnos_municipio ON turnos (id_municipio);
