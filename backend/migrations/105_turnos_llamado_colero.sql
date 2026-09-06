-- ============================================================================
-- 105: Ciclo de llamado + colero (proyecto ATENCION, F3).
--      Plan: PLAN_MODULO_ATENCION.md §2.2 y §3-F3.
--      (Era la "mig 104" del plan; la 104 la tomo tipo_tramite.id_subarea el
--       2026-09-06, asi que el colero corrio a la 105 y la guardia a la 106.)
--
-- FSM resultante:
--     reservado -> llamado -> cumplido | ausente
--     reservado -> cumplido            (mesa SIN colero, flujo historico)
--     reservado | llamado -> cancelado
--     llamado   -> llamado             (re-llamado: no cambia estado, suma log)
--
-- Piezas:
--   1. turnos.estado += 'llamado', 'ausente' (recrear el CHECK).
--   2. turnos.numero_diario: numero visible del colero ('A-014' o '014'),
--      secuencia diaria por UBICACION. Se asigna al PRIMER llamado, no al
--      reservar: un turno que nunca se llama no consume numero.
--   3. turno_llamado: log append-only de llamados (re-llamar = fila nueva).
--   4. espacios_agenda.token_pantalla: URL publica no enumerable de la pantalla
--      de sala. UUID como token_turno (mig 46) y token_reserva.
--   5. espacios_agenda.prefijo_colero: prefijo del numero, configurable por
--      ubicacion (pendiente "formato del numero" del plan §4). NULL/'' => el
--      numero sale sin prefijo. VARCHAR(4) para 'A', 'ODO', 'MESA'.
--
-- Los UNIQUE parciales de slot (mig 95) filtran `estado <> 'cancelado'`, asi que
-- 'llamado' y 'ausente' siguen bloqueando su slot historico: correcto, el turno
-- ocurrio. Solo cancelar libera el slot.
--
-- Idempotente (IF NOT EXISTS / DROP CONSTRAINT IF EXISTS).
-- ============================================================================

-- 1. Estados nuevos ---------------------------------------------------------
ALTER TABLE turnos DROP CONSTRAINT IF EXISTS turnos_estado_check;
ALTER TABLE turnos DROP CONSTRAINT IF EXISTS ck_turnos_estado;
ALTER TABLE turnos
    ADD CONSTRAINT ck_turnos_estado CHECK (
        estado IN ('reservado', 'llamado', 'cumplido', 'ausente', 'cancelado')
    );

-- 2. Numero visible del colero ---------------------------------------------
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS numero_diario VARCHAR(10);

COMMENT ON COLUMN turnos.numero_diario IS
    'Numero visible del colero (mig 105). Secuencia diaria por ubicacion, asignada al primer llamado.';

-- Sirve al calculo del proximo numero y a la pantalla publica.
CREATE INDEX IF NOT EXISTS ix_turnos_numero_diario
    ON turnos (id_espacio_ubicacion, fecha)
    WHERE numero_diario IS NOT NULL;

-- 3. Log de llamados (append-only) -----------------------------------------
CREATE TABLE IF NOT EXISTS turno_llamado (
    id_turno_llamado    SERIAL PRIMARY KEY,
    id_turno            INTEGER NOT NULL REFERENCES turnos(id_turno) ON DELETE CASCADE,
    puesto              VARCHAR(40),          -- box/ventanilla, opcional
    llamado_en          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_llama    INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    -- estandar §10
    activo                  BOOLEAN DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

COMMENT ON TABLE turno_llamado IS
    'Log append-only de llamados del colero (mig 105). Re-llamar = fila nueva, nunca UPDATE.';

-- La pantalla lee "ultimos llamados": ordena por llamado_en DESC.
CREATE INDEX IF NOT EXISTS ix_turno_llamado_turno ON turno_llamado (id_turno, llamado_en DESC);
CREATE INDEX IF NOT EXISTS ix_turno_llamado_fecha ON turno_llamado (llamado_en DESC);

-- RLS deny-all: el backend conecta como postgres y la bypassea (§21).
ALTER TABLE turno_llamado ENABLE ROW LEVEL SECURITY;

-- 4 y 5. Pantalla publica por ubicacion ------------------------------------
-- pgcrypto ya existe (mig 35), gen_random_uuid() es nativo en PG13+.
ALTER TABLE espacios_agenda
    ADD COLUMN IF NOT EXISTS token_pantalla UUID DEFAULT gen_random_uuid();

ALTER TABLE espacios_agenda
    ADD COLUMN IF NOT EXISTS prefijo_colero VARCHAR(4);

COMMENT ON COLUMN espacios_agenda.token_pantalla IS
    'Token no enumerable de la pantalla de sala (mig 105): GET /turnos/pantalla/{token}, sin auth.';
COMMENT ON COLUMN espacios_agenda.prefijo_colero IS
    'Prefijo del numero del colero (mig 105). NULL o vacio => numero sin prefijo.';

-- Backfill de los espacios que ya existian (el DEFAULT solo cubre filas nuevas).
UPDATE espacios_agenda SET token_pantalla = gen_random_uuid()
 WHERE token_pantalla IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_espacios_token_pantalla
    ON espacios_agenda (token_pantalla);
