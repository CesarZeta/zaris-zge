-- ============================================================================
-- 106: Guardia + atencion derivada desde Emergencias (proyecto ATENCION, F4).
--      Plan: PLAN_MODULO_ATENCION.md §2.3 y §3-F4. Decision de Cesar
--      (2026-09-01): las atenciones derivadas del COM NO van con turno — son
--      un registro propio, vinculado al evento, que la Guardia completa.
--      Decision de Cesar (2026-09-06): la Guardia vive en Secretaria de Salud,
--      subarea "Emergencias" (la crea la 106b, seed separado — §21).
--
-- Piezas:
--   1. emergencia_log: dos tipos de accion nuevos en el CHECK
--      (DERIVACION_GUARDIA al derivar desde el COM, ATENCION_GUARDIA cuando la
--      Guardia atiende o marca ausente). Los triggers no-update/no-delete del
--      log NO se tocan.
--   2. emergencia_atencion: la derivacion. Nace 'pendiente' con el motivo del
--      COM; la Guardia la cierra 'atendida' (intervencion obligatoria +
--      recomendaciones) o 'ausente' (el vecino no llego). El paciente puede ser
--      un ciudadano BUC (id_ciudadano) o un nombre libre (paciente_nombre): el
--      denunciante del evento no es necesariamente quien se atiende.
--      Una sola derivacion PENDIENTE por evento (UNIQUE parcial). Base de la
--      historia clinica (F5) junto con turno_atencion.
--
-- Idempotente (IF NOT EXISTS / DROP CONSTRAINT IF EXISTS).
-- ============================================================================

-- 1. Tipos de accion nuevos en el log del evento -----------------------------
ALTER TABLE emergencia_log DROP CONSTRAINT IF EXISTS ck_emergencia_log_tipo_accion;
ALTER TABLE emergencia_log
    ADD CONSTRAINT ck_emergencia_log_tipo_accion CHECK (
        tipo_accion IN (
            'CREACION', 'CAMBIO_ESTADO', 'CAMBIO_TIPO', 'CAMBIO_PRIORIDAD', 'CAMBIO_SUBTIPO',
            'DERIVACION', 'NOTA', 'ASIGNACION_RECURSO', 'CIERRE', 'PROMOCION_BUC',
            'DERIVACION_GUARDIA', 'ATENCION_GUARDIA'
        )
    );

-- 2. Atencion derivada a la Guardia -----------------------------------------
CREATE TABLE IF NOT EXISTS emergencia_atencion (
    id_emergencia_atencion  SERIAL PRIMARY KEY,
    id_emergencia_evento    INTEGER NOT NULL REFERENCES emergencia_evento(id_emergencia_evento),
    id_espacio_ubicacion    INTEGER NOT NULL REFERENCES espacios_agenda(id_espacio),  -- la Guardia
    id_ciudadano            INTEGER REFERENCES ciudadanos(id_ciudadano) ON DELETE SET NULL,
    paciente_nombre         VARCHAR(150),        -- cuando el paciente no esta en la BUC
    motivo_derivacion       TEXT NOT NULL,       -- lo escribe el COM al derivar
    estado                  VARCHAR(12) NOT NULL DEFAULT 'pendiente'
                            CHECK (estado IN ('pendiente', 'atendida', 'ausente')),
    derivado_en             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_deriva       INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_agente_atiende       INTEGER REFERENCES agentes(id_agente) ON DELETE SET NULL,
    intervencion            TEXT,                -- obligatoria al pasar a 'atendida' (CHECK abajo)
    recomendaciones         TEXT,
    atendido_en             TIMESTAMPTZ,
    -- estandar §10
    activo                  BOOLEAN DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_emergencia_atencion_atendida CHECK (
        estado <> 'atendida' OR (intervencion IS NOT NULL AND atendido_en IS NOT NULL)
    )
);

COMMENT ON TABLE emergencia_atencion IS
    'Atencion en la Guardia derivada desde un evento del COM (mig 106, F4). Sin turno de por medio.';
COMMENT ON COLUMN emergencia_atencion.id_ciudadano IS
    'Paciente (BUC). NULL si no esta en la BUC: ver paciente_nombre. No es necesariamente el denunciante del evento.';

-- Una sola derivacion pendiente por evento (re-derivar mientras hay una abierta => 409).
CREATE UNIQUE INDEX IF NOT EXISTS uq_emergencia_atencion_pendiente
    ON emergencia_atencion (id_emergencia_evento)
    WHERE activo = TRUE AND estado = 'pendiente';

-- La mesa de la Guardia lista pendientes por ubicacion y las cerradas del dia.
CREATE INDEX IF NOT EXISTS ix_emergencia_atencion_ubicacion
    ON emergencia_atencion (id_espacio_ubicacion, estado, derivado_en DESC);

-- Historia clinica (F5): consulta por ciudadano.
CREATE INDEX IF NOT EXISTS ix_emergencia_atencion_ciudadano
    ON emergencia_atencion (id_ciudadano)
    WHERE id_ciudadano IS NOT NULL;

-- RLS deny-all: el backend conecta como postgres y la bypassea (§21).
ALTER TABLE emergencia_atencion ENABLE ROW LEVEL SECURITY;
