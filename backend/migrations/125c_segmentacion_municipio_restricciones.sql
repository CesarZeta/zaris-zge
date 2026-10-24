-- Migración 125c — IT-01 F1: id_municipio NOT NULL + FK, únicos por municipio y numeración con código
-- Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, Tarea 2. Requiere la 125 y la 125b.
--
-- Re-aplicable y sin DROP. Compatible con el código actual: las tablas quedan con DEFAULT 1
-- TEMPORAL (los INSERT de hoy no mandan el municipio); la 126 lo anula con SET DEFAULT NULL
-- cuando el código de F2 ya manda el municipio en cada INSERT.
-- Los únicos globales viejos (DNI, CUIL, CUIT, números, clave de configuración) quedan hasta el
-- lote de limpieza: borrarlos exige DROP.

-- 1. NOT NULL, DEFAULT 1 temporal, FK a municipios e índice en toda tabla catalogo/operativo.
DO $$
DECLARE
    r RECORD;
    v_tiene_fk BOOLEAN;
BEGIN
    FOR r IN
        SELECT m.tabla
          FROM municipio_tabla_clase m
         WHERE m.clase IN ('catalogo', 'operativo')
           AND to_regclass('public.' || quote_ident(m.tabla)) IS NOT NULL
         ORDER BY m.tabla
    LOOP
        EXECUTE format('ALTER TABLE %I ALTER COLUMN id_municipio SET NOT NULL', r.tabla);
        EXECUTE format('ALTER TABLE %I ALTER COLUMN id_municipio SET DEFAULT 1', r.tabla);

        SELECT EXISTS (
            SELECT 1
              FROM pg_constraint c
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
             WHERE c.conrelid = ('public.' || quote_ident(r.tabla))::regclass
               AND c.contype = 'f' AND c.confrelid = 'municipios'::regclass
               AND a.attname = 'id_municipio' AND array_length(c.conkey, 1) = 1
        ) INTO v_tiene_fk;
        IF NOT v_tiene_fk THEN
            EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (id_municipio) REFERENCES municipios (id_municipio)',
                           r.tabla, left('fkmun_' || r.tabla, 63));
        END IF;

        EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (id_municipio)', left('ix_' || r.tabla || '_mun', 63), r.tabla);
    END LOOP;
END $$;

-- 2. configuracion_general (clase mixta): FK, sin NOT NULL (NULL = parámetro global).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fkmun_configuracion_general') THEN
        ALTER TABLE configuracion_general ADD CONSTRAINT fkmun_configuracion_general
            FOREIGN KEY (id_municipio) REFERENCES municipios (id_municipio);
    END IF;
END $$;

ALTER TABLE municipios ALTER COLUMN codigo_pais SET NOT NULL;

-- 3. Únicos por municipio (coexisten con los globales viejos hasta el lote de limpieza).
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_ciudadanos_doc   ON ciudadanos (id_municipio, doc_pais, doc_tipo, doc_nro);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_ciudadanos_cuil  ON ciudadanos (id_municipio, cuil);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_empresas_cuit    ON empresas (id_municipio, doc_pais, cuit);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_usuarios_username ON usuarios (id_municipio, username);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_reclamos_nro     ON reclamos (id_municipio, nro_reclamo);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_ot_nro           ON ordenes_trabajo (id_municipio, nro_ot);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_emergencia_nro   ON emergencia_evento (id_municipio, numero_operativo);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_activos_codigo   ON activos (id_municipio, codigo_unico);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_feriado_fecha    ON agenda_feriado (id_municipio, fecha);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_emerg_canal_cod  ON emergencia_canal_ingreso (id_municipio, codigo);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_emerg_prio_cod   ON emergencia_prioridad (id_municipio, codigo);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_emerg_org_cod    ON emergencia_organismo_derivacion (id_municipio, codigo);
CREATE UNIQUE INDEX IF NOT EXISTS uqmun_config_clave     ON configuracion_general (id_municipio, clave) NULLS NOT DISTINCT;

-- 4. Numeración por municipio con el código corto en el número: REC-SAN-2026-002983.
--    El contador sigue desde el último número emitido (125b). Los números viejos no cambian.
--    El año sale de NOW() como hasta ahora (la zona horaria por municipio es de F5b).
CREATE OR REPLACE FUNCTION fn_codigo_municipio(p_mun INTEGER)
RETURNS TEXT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_cod TEXT;
BEGIN
    SELECT codigo_corto INTO v_cod FROM municipios WHERE id_municipio = p_mun;
    IF v_cod IS NULL OR v_cod = '' THEN
        RAISE EXCEPTION 'El municipio % no tiene codigo_corto', p_mun;
    END IF;
    RETURN v_cod;
END;
$$;

CREATE OR REPLACE FUNCTION public.fn_generar_nro_reclamo()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_anio INTEGER := CAST(EXTRACT(YEAR FROM NOW()) AS integer);
BEGIN
    IF NEW.nro_reclamo IS NULL THEN
        NEW.nro_reclamo := 'REC-' || fn_codigo_municipio(NEW.id_municipio) || '-' || v_anio::text || '-'
                           || lpad(fn_siguiente_numero(NEW.id_municipio, 'reclamo', v_anio)::text, 6, '0');
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.fn_generar_nro_ot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_anio INTEGER := CAST(EXTRACT(YEAR FROM NOW()) AS integer);
BEGIN
    IF NEW.nro_ot IS NULL THEN
        NEW.nro_ot := 'OT-' || fn_codigo_municipio(NEW.id_municipio) || '-' || v_anio::text || '-'
                      || lpad(fn_siguiente_numero(NEW.id_municipio, 'ot', v_anio)::text, 6, '0');
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.fn_generar_numero_emergencia()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_anio INTEGER := CAST(EXTRACT(YEAR FROM NOW()) AS integer);
BEGIN
    IF NEW.numero_operativo IS NULL OR NEW.numero_operativo = '' THEN
        NEW.numero_operativo := 'EM-' || fn_codigo_municipio(NEW.id_municipio) || '-' || v_anio::text || '-'
                                || lpad(fn_siguiente_numero(NEW.id_municipio, 'emergencia', v_anio)::text, 6, '0');
    END IF;
    RETURN NEW;
END;
$$;
