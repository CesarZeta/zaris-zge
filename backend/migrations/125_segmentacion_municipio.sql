-- Migración 125 — IT-01 F1: segmentación de la base por municipio (DDL nuevo)
-- Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, Tarea 1. Spec: PLAN_MULTI_MUNICIPIO.md §1, §2 y §7.
--
-- Solo agrega (tablas, columnas, índices, función). Re-aplicable y SIN DROP: apply_migration
-- rechaza cualquier sentencia con DROP. Los datos (clasificación, backfill, numeradores) van en
-- la 125b; las restricciones (NOT NULL, FK, únicos, triggers de numeración) en la 125c.
-- Compatible con el código actual: no cambia nada que el backend lea o escriba hoy.

-- 1. Municipios: subdominio, país normalizado, zona horaria y municipio de las direcciones sin prefijo.
ALTER TABLE municipios ADD COLUMN IF NOT EXISTS subdominio VARCHAR(63);
ALTER TABLE municipios ADD COLUMN IF NOT EXISTS codigo_pais CHAR(2);
ALTER TABLE municipios ADD COLUMN IF NOT EXISTS zona_horaria VARCHAR(64) NOT NULL
    DEFAULT 'America/Argentina/Buenos_Aires';
ALTER TABLE municipios ADD COLUMN IF NOT EXISTS direccion_base BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN municipios.subdominio IS
    'Prefijo de las direcciones del municipio (<subdominio>.zge|vecinos|agentes.zaris.com.ar). IT-01.';
COMMENT ON COLUMN municipios.codigo_pais IS 'País ISO 3166-1 alfa-2 (AR, VE…). `pais` queda como nombre visible.';
COMMENT ON COLUMN municipios.zona_horaria IS 'Zona IANA del municipio. El código la usa desde F5b.';
COMMENT ON COLUMN municipios.direccion_base IS
    'TRUE en el único municipio que atienden las direcciones sin prefijo (zge/vecinos/agentes.zaris.com.ar).';

CREATE UNIQUE INDEX IF NOT EXISTS uq_municipios_subdominio
    ON municipios (subdominio) WHERE subdominio IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_municipios_direccion_base
    ON municipios (direccion_base) WHERE direccion_base;
CREATE UNIQUE INDEX IF NOT EXISTS uq_municipios_codigo_corto
    ON municipios (upper(codigo_corto)) WHERE codigo_corto IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_municipios_subdominio') THEN
        ALTER TABLE municipios ADD CONSTRAINT ck_municipios_subdominio
            CHECK (subdominio IS NULL OR subdominio ~ '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_municipios_codigo_pais') THEN
        ALTER TABLE municipios ADD CONSTRAINT ck_municipios_codigo_pais
            CHECK (codigo_pais IS NULL OR codigo_pais ~ '^[A-Z]{2}$');
    END IF;
END $$;

-- 2. Catálogo geográfico global con país (el árbol de hoy es el argentino).
ALTER TABLE provincias ADD COLUMN IF NOT EXISTS codigo_pais CHAR(2) NOT NULL DEFAULT 'AR';

-- 3. Tipos de documento por país (global). El módulo que los parametriza es un tema reservado
--    (spec §7); acá solo queda el modelo: país + tipo + número.
CREATE TABLE IF NOT EXISTS tipo_documento (
    id_tipo_documento       SERIAL PRIMARY KEY,
    codigo_pais             CHAR(2)      NOT NULL,
    codigo                  VARCHAR(20)  NOT NULL,
    nombre                  VARCHAR(80)  NOT NULL,
    aplica_a                VARCHAR(10)  NOT NULL CHECK (aplica_a IN ('persona', 'empresa')),
    activo                  BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_alta              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT uq_tipo_documento UNIQUE (codigo_pais, codigo)
);
ALTER TABLE tipo_documento ENABLE ROW LEVEL SECURITY;

ALTER TABLE ciudadanos ADD COLUMN IF NOT EXISTS doc_pais CHAR(2) NOT NULL DEFAULT 'AR';
ALTER TABLE empresas   ADD COLUMN IF NOT EXISTS doc_pais CHAR(2) NOT NULL DEFAULT 'AR';
COMMENT ON COLUMN ciudadanos.doc_pais IS 'País emisor del documento (doc_pais, doc_tipo, doc_nro). IT-01 §7.';
COMMENT ON COLUMN empresas.doc_pais   IS 'País del CUIT o identificador fiscal. IT-01 §7.';

-- 4. id_municipio en las tablas por municipio que todavía no lo tienen (nullable hasta la 125c).
ALTER TABLE configuracion_general ADD COLUMN IF NOT EXISTS id_municipio INTEGER;
ALTER TABLE reclamo_historial     ADD COLUMN IF NOT EXISTS id_municipio INTEGER;
ALTER TABLE usuario_login_log     ADD COLUMN IF NOT EXISTS id_municipio INTEGER;
ALTER TABLE ciudadano_empresa     ADD COLUMN IF NOT EXISTS id_municipio INTEGER;
ALTER TABLE lugares_atencion      ADD COLUMN IF NOT EXISTS id_municipio INTEGER;
ALTER TABLE servicios             ADD COLUMN IF NOT EXISTS id_municipio INTEGER;
COMMENT ON COLUMN configuracion_general.id_municipio IS
    'Municipio dueño de la clave. NULL = parámetro global (valor por defecto para todos). IT-01.';

-- 5. Clasificación de tablas: fuente única para las migraciones de F1, el barrido de aislamiento,
--    el vaciado y la exportación de F4 y las políticas RLS de F6. Toda tabla nueva lleva su fila.
CREATE TABLE IF NOT EXISTS municipio_tabla_clase (
    tabla              TEXT PRIMARY KEY,
    clase              TEXT NOT NULL CHECK (clase IN ('global', 'catalogo', 'operativo', 'mixta', 'legado')),
    nota               TEXT,
    fecha_alta         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE municipio_tabla_clase ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE municipio_tabla_clase IS
    'Clase de cada tabla de public: global | catalogo (por municipio, se copia del modelo) | '
    'operativo (por municipio) | mixta (NULL = global) | legado (sin uso, a borrar). IT-01.';

-- 6. Numeración por municipio, entidad y año (reclamos, OT, emergencias). Reemplaza a
--    emergencia_numerador y a los números derivados del id.
CREATE TABLE IF NOT EXISTS numerador_municipio (
    id_municipio       INTEGER     NOT NULL REFERENCES municipios(id_municipio),
    entidad            VARCHAR(20) NOT NULL CHECK (entidad IN ('reclamo', 'ot', 'emergencia')),
    anio               INTEGER     NOT NULL,
    ultimo_numero      INTEGER     NOT NULL DEFAULT 0,
    fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id_municipio, entidad, anio)
);
ALTER TABLE numerador_municipio ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION fn_siguiente_numero(p_mun INTEGER, p_entidad TEXT, p_anio INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_num INTEGER;
BEGIN
    INSERT INTO numerador_municipio (id_municipio, entidad, anio, ultimo_numero)
    VALUES (p_mun, p_entidad, p_anio, 1)
    ON CONFLICT (id_municipio, entidad, anio) DO UPDATE
        SET ultimo_numero      = numerador_municipio.ultimo_numero + 1,
            fecha_modificacion = NOW()
    RETURNING ultimo_numero INTO v_num;
    RETURN v_num;
END;
$$;
