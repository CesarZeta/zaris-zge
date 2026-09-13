-- ============================================================================
-- 107: Historia clinica minima viable (proyecto ATENCION, F5) — registro de accesos.
--      Plan: PLAN_MODULO_ATENCION.md §2.4 y §3-F5. Decision de Cesar (2026-09-01):
--      historia clinica = timeline por ciudadano leyendo DOS fuentes (turno_atencion
--      mig 86 + emergencia_atencion mig 106), permiso restringido a la gestion Salud
--      + nivel 1 (dato sensible Ley 25.326 art. 7; HC informatizada Ley 26.529 art. 13).
--
-- Sin DDL sobre las fuentes: tablas e indices por ciudadano ya existen
-- (idx_turno_atencion_ciudadano mig 86, ix_emergencia_atencion_ciudadano mig 106).
--
-- Piezas:
--   1. Tabla historia_clinica_acceso: UNA fila por consulta de la historia clinica
--      (ok | denegado | inexistente): quien, a quien, cuando, desde donde, cuantos
--      registros. Append-only (triggers) + RLS deny-all, como emergencia_log (mig 83).
--      Sin FK a ciudadanos a proposito: registra tambien los intentos sobre ids
--      inexistentes (barrido de ids secuenciales). Sin activo/fecha_modificacion:
--      es un log, no un maestro (misma excepcion al §10 que emergencia_log).
--   2. Indices por ciudadano y por usuario ("quien miro la HC de X").
-- La clave de config id_area_salud va en 107b (seed separado del DDL, §21).
--
-- Idempotente (IF NOT EXISTS / DROP TRIGGER IF EXISTS / CREATE OR REPLACE).
-- ============================================================================

-- 1. Tabla de accesos ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS historia_clinica_acceso (
    id_historia_clinica_acceso  BIGSERIAL PRIMARY KEY,
    id_usuario      INTEGER      NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    id_ciudadano    INTEGER      NOT NULL,                      -- sin FK (ver cabecera)
    fecha_hora      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    origen          VARCHAR(16)  NOT NULL DEFAULT 'historia',   -- 'historia' hoy; 'export' en etapa 2
    contexto        VARCHAR(16)  NOT NULL DEFAULT 'otro',       -- desde donde se abrio en la UI
    resultado       VARCHAR(16)  NOT NULL,
    motivo          VARCHAR(20)  NOT NULL,                      -- motivo evaluado por permiso_historia_clinica
    n_registros     INTEGER,                                    -- NULL si denegado
    ip              VARCHAR(64),
    user_agent      VARCHAR(255),
    id_municipio    INTEGER,
    CONSTRAINT ck_hc_acceso_origen    CHECK (origen    IN ('historia', 'export')),
    CONSTRAINT ck_hc_acceso_contexto  CHECK (contexto  IN ('turno', 'guardia', 'mesa', 'consulta', 'otro')),
    CONSTRAINT ck_hc_acceso_resultado CHECK (resultado IN ('ok', 'denegado', 'inexistente'))
);

COMMENT ON TABLE historia_clinica_acceso IS
  'Registro append-only de accesos a la historia clinica (mig 107, F5): una fila por consulta, incluidos los denegados por el guard Salud y los ids inexistentes.';
COMMENT ON COLUMN historia_clinica_acceso.resultado IS
  'ok = devolvio datos (n_registros); denegado = 403 del guard; inexistente = guard ok pero el ciudadano no existe (mig 107)';
COMMENT ON COLUMN historia_clinica_acceso.motivo IS
  'admin | admin_sin_config | salud | nivel | sin_agente | sin_subarea | fuera_salud | sin_config (mig 107)';
COMMENT ON COLUMN historia_clinica_acceso.contexto IS
  'turno (detalle del turno) | guardia (mesa/atender Guardia) | mesa (colero) | consulta (consulta por ciudadano) | otro (mig 107)';

CREATE INDEX IF NOT EXISTS ix_hc_acceso_ciudadano ON historia_clinica_acceso (id_ciudadano, fecha_hora DESC);
CREATE INDEX IF NOT EXISTS ix_hc_acceso_usuario   ON historia_clinica_acceso (id_usuario,   fecha_hora DESC);

-- RLS deny-all: el backend conecta como postgres y la bypassea (§21).
ALTER TABLE historia_clinica_acceso ENABLE ROW LEVEL SECURITY;

-- 2. Append-only (mismo patron que emergencia_log_no_mutate, mig 83) ----------
CREATE OR REPLACE FUNCTION historia_clinica_acceso_no_mutate()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'historia_clinica_acceso es append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS historia_clinica_acceso_no_update ON historia_clinica_acceso;
CREATE TRIGGER historia_clinica_acceso_no_update
BEFORE UPDATE ON historia_clinica_acceso
FOR EACH ROW EXECUTE FUNCTION historia_clinica_acceso_no_mutate();

DROP TRIGGER IF EXISTS historia_clinica_acceso_no_delete ON historia_clinica_acceso;
CREATE TRIGGER historia_clinica_acceso_no_delete
BEFORE DELETE ON historia_clinica_acceso
FOR EACH ROW EXECUTE FUNCTION historia_clinica_acceso_no_mutate();
