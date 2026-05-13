-- =============================================================================
-- Migracion 40 - Agenda: espacios_agenda + espacio_agentes (N:M)
--
-- Crea el catalogo de "espacios" usados por el modulo Agenda como tercer tipo
-- de recurso (junto con agentes y equipos). Un espacio puede ser:
--   - atendido: necesita agentes vinculados (via espacio_agentes); su
--     disponibilidad horaria efectiva es la union de los horarios de sus
--     agentes interseccion con su propio horario de atencion.
--   - desatendido: no requiere agentes; se reserva directamente sobre su
--     horario de atencion (ej. sala de reuniones autogestionada).
--
-- Catalogo separado de `lugares_atencion` (legacy) por dos motivos:
--   1. Ese legacy tiene PK `id` (no estandar §10) y campos `creado_por/_en`
--      en lugar de `id_usuario_alta/fecha_alta`.
--   2. Lugares de atencion del producto general (front, padron, etc.) y
--      espacios de agenda no son 1:1: hay espacios de agenda sin presencia
--      ciudadana publica (back office) y lugares de atencion sin agenda
--      (ventanilla sin turnos).
--
-- Idempotente: CREATE TABLE IF NOT EXISTS + ON CONFLICT en eventuales seeds.
-- =============================================================================

CREATE TABLE IF NOT EXISTS espacios_agenda (
  id_espacio              SERIAL PRIMARY KEY,
  nombre                  VARCHAR(150) NOT NULL,
  descripcion             TEXT,
  direccion               VARCHAR(300),
  capacidad_personas      INTEGER,
  atendido                BOOLEAN NOT NULL DEFAULT TRUE,
  -- Estandar §10
  activo                  BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio            INTEGER NOT NULL DEFAULT 1,
  id_subarea              INTEGER REFERENCES subarea(id_subarea) ON DELETE SET NULL,
  fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_espacios_agenda_municipio
  ON espacios_agenda (id_municipio) WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_espacios_agenda_atendido
  ON espacios_agenda (atendido) WHERE activo = TRUE;

-- N:M espacio <-> agente. Solo aplica cuando espacio.atendido = TRUE.
-- Validacion del invariante "atendido => al menos 1 agente vinculado" queda
-- en backend (la DB permite atendido sin agentes para no bloquear el alta
-- inicial; backend devuelve warning si se publica un espacio atendido sin
-- agentes en evento_encargados / ocupacion).
CREATE TABLE IF NOT EXISTS espacio_agentes (
  id_espacio_agente       SERIAL PRIMARY KEY,
  id_espacio              INTEGER NOT NULL REFERENCES espacios_agenda(id_espacio) ON DELETE CASCADE,
  id_agente               INTEGER NOT NULL REFERENCES agentes(id_agente) ON DELETE CASCADE,
  -- Estandar §10
  activo                  BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio            INTEGER NOT NULL DEFAULT 1,
  id_subarea              INTEGER REFERENCES subarea(id_subarea) ON DELETE SET NULL,
  fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  CONSTRAINT uq_espacio_agentes UNIQUE (id_espacio, id_agente)
);

CREATE INDEX IF NOT EXISTS idx_espacio_agentes_espacio
  ON espacio_agentes (id_espacio) WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_espacio_agentes_agente
  ON espacio_agentes (id_agente) WHERE activo = TRUE;
