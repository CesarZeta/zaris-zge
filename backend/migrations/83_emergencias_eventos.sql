-- Migracion 83: Modulo Emergencias - Fase 3: contacto eventual + evento + log.
-- Plan: PLAN_MODULO_EMERGENCIAS.md (secciones 2.7-2.10, adaptadas a CLAUDE.md).
--
-- 3 tablas + secuencia + trigger de numeracion + triggers anti-mutacion del log:
--   emergencia_contacto_eventual  (vecino cargado al vuelo, no encontrado en BUC)
--   emergencia_evento             (transaccional principal)
--   emergencia_log                (append-only: SIN activo / fecha_modificacion,
--                                  con triggers que rechazan UPDATE y DELETE)
--
-- Convenciones (ganan sobre el plan, SS28): PK id_<tabla>, INTEGER/SERIAL,
-- estandar SS10 (salvo el log, exceptuado a proposito), tablas reales
-- ciudadanos/usuarios/subarea, lat/lon como latitud/longitud NUMERIC(10,7)
-- (igual que reclamos SS22), id_municipio nullable sin FK fisica, RLS deny-all.
--
-- numero_operativo: secuencia + trigger BEFORE INSERT (patron trg_nro_reclamo
-- SS18) -> 'EM-YYYY-NNNNNN'. El backend no lo manda; lo genera la DB.
--
-- Idempotente: IF NOT EXISTS + CREATE OR REPLACE + DROP TRIGGER IF EXISTS.

BEGIN;

-- =============================================================================
-- 1. emergencia_contacto_eventual
-- =============================================================================
CREATE TABLE IF NOT EXISTS emergencia_contacto_eventual (
    id_emergencia_contacto_eventual SERIAL PRIMARY KEY,
    dni                     VARCHAR(15) NOT NULL,       -- normalizado, solo digitos
    nombre_apellido         VARCHAR(150) NOT NULL,
    telefono                VARCHAR(30) NOT NULL,
    direccion               VARCHAR(300) NOT NULL,
    contacto_alt_nombre     VARCHAR(150),
    contacto_alt_telefono   VARCHAR(30),
    convertido_a_buc        BOOLEAN NOT NULL DEFAULT FALSE,
    id_ciudadano_buc_destino INTEGER REFERENCES ciudadanos(id_ciudadano),
    observaciones           TEXT,
    -- estandar SS10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_emerg_contacto_dni
    ON emergencia_contacto_eventual (dni);
CREATE INDEX IF NOT EXISTS idx_emerg_contacto_telefono
    ON emergencia_contacto_eventual (telefono);
CREATE INDEX IF NOT EXISTS idx_emerg_contacto_nombre
    ON emergencia_contacto_eventual (lower(nombre_apellido));

ALTER TABLE emergencia_contacto_eventual ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 2. emergencia_evento (tabla principal)
-- =============================================================================
CREATE TABLE IF NOT EXISTS emergencia_evento (
    id_emergencia_evento    SERIAL PRIMARY KEY,
    numero_operativo        VARCHAR(20) NOT NULL UNIQUE,    -- 'EM-2026-000123' (trigger)
    id_subarea              INTEGER NOT NULL REFERENCES subarea(id_subarea),
    id_tipo                 INTEGER NOT NULL REFERENCES emergencia_tipo(id_emergencia_tipo),
    id_subtipo              INTEGER REFERENCES emergencia_subtipo(id_emergencia_subtipo),
    id_prioridad            INTEGER NOT NULL REFERENCES emergencia_prioridad(id_emergencia_prioridad),
    id_estado               INTEGER NOT NULL REFERENCES emergencia_estado(id_emergencia_estado),
    id_canal_ingreso        INTEGER NOT NULL REFERENCES emergencia_canal_ingreso(id_emergencia_canal_ingreso),
    id_organismo_derivacion INTEGER REFERENCES emergencia_organismo_derivacion(id_emergencia_organismo_derivacion),
    id_operador_receptor    INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    denunciante_anonimo     BOOLEAN NOT NULL DEFAULT FALSE,
    id_ciudadano_buc        INTEGER REFERENCES ciudadanos(id_ciudadano),
    id_contacto_eventual    INTEGER REFERENCES emergencia_contacto_eventual(id_emergencia_contacto_eventual),
    direccion_evento        VARCHAR(300) NOT NULL,
    latitud                 NUMERIC(10,7),
    longitud                NUMERIC(10,7),
    referencia_ubicacion    VARCHAR(300),
    audio_grabacion_url     TEXT,
    observaciones_recepcion TEXT,
    observaciones_cierre    TEXT,
    veracidad               VARCHAR(20),
    fecha_hora_recepcion    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_hora_despacho     TIMESTAMPTZ,
    fecha_hora_arribo       TIMESTAMPTZ,
    fecha_hora_cierre       TIMESTAMPTZ,
    -- estandar SS10 (id_subarea ya esta arriba como FK semantica)
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_emergencia_evento_veracidad CHECK (
        veracidad IS NULL OR veracidad IN ('CONFIRMADA', 'FALSA_ALARMA', 'NO_VERIFICABLE')
    ),
    CONSTRAINT ck_emergencia_evento_denunciante CHECK (
        (denunciante_anonimo = TRUE
         AND id_ciudadano_buc IS NULL
         AND id_contacto_eventual IS NULL)
        OR
        (denunciante_anonimo = FALSE
         AND ((id_ciudadano_buc IS NOT NULL AND id_contacto_eventual IS NULL)
              OR (id_ciudadano_buc IS NULL AND id_contacto_eventual IS NOT NULL)))
    )
);

CREATE INDEX IF NOT EXISTS idx_emerg_evento_estado_fecha
    ON emergencia_evento (id_estado, fecha_hora_recepcion DESC);
CREATE INDEX IF NOT EXISTS idx_emerg_evento_subarea_estado
    ON emergencia_evento (id_subarea, id_estado);
CREATE INDEX IF NOT EXISTS idx_emerg_evento_ciudadano
    ON emergencia_evento (id_ciudadano_buc);
CREATE INDEX IF NOT EXISTS idx_emerg_evento_contacto
    ON emergencia_evento (id_contacto_eventual);

ALTER TABLE emergencia_evento ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 3. Secuencia + trigger de numeracion EM-YYYY-NNNNNN
--    (reset anual: pendiente, Fase 3+ del plan seccion 8)
-- =============================================================================
CREATE SEQUENCE IF NOT EXISTS emergencia_evento_numero_seq START 1;

CREATE OR REPLACE FUNCTION fn_generar_numero_emergencia()
RETURNS trigger AS $$
BEGIN
    IF NEW.numero_operativo IS NULL OR NEW.numero_operativo = '' THEN
        NEW.numero_operativo := 'EM-' || to_char(NOW(), 'YYYY') || '-' ||
            lpad(nextval('emergencia_evento_numero_seq')::text, 6, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_numero_emergencia ON emergencia_evento;
CREATE TRIGGER trg_numero_emergencia
BEFORE INSERT ON emergencia_evento
FOR EACH ROW EXECUTE FUNCTION fn_generar_numero_emergencia();

-- El NOT NULL de numero_operativo se evalua DESPUES de los triggers BEFORE
-- INSERT: el backend inserta sin numero y el trigger lo completa siempre.

-- =============================================================================
-- 4. emergencia_log (APPEND-ONLY)
--    Excepcion deliberada al estandar SS10: sin activo / fecha_modificacion /
--    auditoria de modificacion — el log no se modifica nunca (triggers abajo).
-- =============================================================================
CREATE TABLE IF NOT EXISTS emergencia_log (
    id_emergencia_log       SERIAL PRIMARY KEY,
    id_evento               INTEGER NOT NULL REFERENCES emergencia_evento(id_emergencia_evento) ON DELETE RESTRICT,
    id_usuario              INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    fecha_hora              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tipo_accion             VARCHAR(30) NOT NULL,
    estado_anterior         VARCHAR(30),
    estado_nuevo            VARCHAR(30),
    payload_json            JSONB,
    observaciones           TEXT,
    id_municipio            INTEGER,
    CONSTRAINT ck_emergencia_log_tipo_accion CHECK (tipo_accion IN (
        'CREACION', 'CAMBIO_ESTADO', 'CAMBIO_TIPO', 'CAMBIO_PRIORIDAD',
        'CAMBIO_SUBTIPO', 'DERIVACION', 'NOTA', 'ASIGNACION_RECURSO',
        'CIERRE', 'PROMOCION_BUC'
    ))
);

CREATE INDEX IF NOT EXISTS idx_emerg_log_evento
    ON emergencia_log (id_evento, fecha_hora);

ALTER TABLE emergencia_log ENABLE ROW LEVEL SECURITY;

-- Triggers anti-mutacion (responsabilidad civil: el registro de tiempos no se toca)
CREATE OR REPLACE FUNCTION emergencia_log_no_mutate()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'emergencia_log es append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS emergencia_log_no_update ON emergencia_log;
CREATE TRIGGER emergencia_log_no_update
BEFORE UPDATE ON emergencia_log
FOR EACH ROW EXECUTE FUNCTION emergencia_log_no_mutate();

DROP TRIGGER IF EXISTS emergencia_log_no_delete ON emergencia_log;
CREATE TRIGGER emergencia_log_no_delete
BEFORE DELETE ON emergencia_log
FOR EACH ROW EXECUTE FUNCTION emergencia_log_no_mutate();

COMMIT;
