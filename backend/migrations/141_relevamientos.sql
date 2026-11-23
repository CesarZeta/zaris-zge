-- Migración 141 — Relevamientos: incidentes que carga un agente municipal desde la app de agentes.
-- Plan: PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md (§2b y §2c, decisiones de César del 2026-11-22).
--
-- Un relevamiento es un reclamo que no pidió ningún vecino: lo lleva a cabo un agente. Usa el
-- mismo catálogo de tipos, el mismo circuito (OT, asignación automática, auditoría) y la misma
-- tabla `reclamos`, con una marca propia y numeración propia (REL-<municipio>-<año>-<número>).
-- No tiene solicitante: no lleva ciudadano, no avisa a nadie y no tiene encuesta.
--
-- Qué hace:
--   1. reclamos.es_relevamiento (FALSE por defecto) + CHECK: un relevamiento no lleva ciudadano.
--   2. Índice parcial para «mis relevamientos» y para contarlos aparte.
--   3. numerador_municipio admite la entidad 'relevamiento' (se recrea el CHECK).
--   4. El trigger de numeración da REL- a los relevamientos y REC- al resto, cada uno con su contador.
--
-- No hay tablas nuevas: `reclamos` ya está clasificada (operativo) y con su política de barrera.
-- Lleva DROP CONSTRAINT: en prod la corre César en el SQL Editor de Supabase (el permiso del MCP
-- rechaza los DROP); en local, con asyncpg `driver_connection.execute`. Re-aplicable.

-- 1. La marca y su regla.
ALTER TABLE reclamos ADD COLUMN IF NOT EXISTS es_relevamiento BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE reclamos DROP CONSTRAINT IF EXISTS ck_reclamos_relevamiento_sin_ciudadano;
ALTER TABLE reclamos ADD CONSTRAINT ck_reclamos_relevamiento_sin_ciudadano
    CHECK (NOT es_relevamiento OR id_ciudadano IS NULL);

-- 2. Índice para listarlos (mis relevamientos, filtro del backoffice, Datos).
CREATE INDEX IF NOT EXISTS idx_reclamos_relevamiento
    ON reclamos (id_municipio, id_usuario_alta, fecha_alta DESC)
    WHERE es_relevamiento;

-- 3. Contador propio por municipio y año.
ALTER TABLE numerador_municipio DROP CONSTRAINT IF EXISTS numerador_municipio_entidad_check;
ALTER TABLE numerador_municipio ADD CONSTRAINT numerador_municipio_entidad_check
    CHECK (entidad IN ('reclamo', 'ot', 'emergencia', 'relevamiento'));

-- 4. Numeración: REL- para los relevamientos, REC- para el resto.
CREATE OR REPLACE FUNCTION public.fn_generar_nro_reclamo()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_anio INTEGER := CAST(EXTRACT(YEAR FROM NOW()) AS integer);
BEGIN
    IF NEW.nro_reclamo IS NULL THEN
        IF NEW.es_relevamiento THEN
            NEW.nro_reclamo := 'REL-' || fn_codigo_municipio(NEW.id_municipio) || '-' || v_anio::text || '-'
                               || lpad(fn_siguiente_numero(NEW.id_municipio, 'relevamiento', v_anio)::text, 6, '0');
        ELSE
            NEW.nro_reclamo := 'REC-' || fn_codigo_municipio(NEW.id_municipio) || '-' || v_anio::text || '-'
                               || lpad(fn_siguiente_numero(NEW.id_municipio, 'reclamo', v_anio)::text, 6, '0');
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;
