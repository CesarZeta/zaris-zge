-- Migracion 120 — SLA de los tipos de reclamo en minutos (2026-10-23)
--
-- Decision de Cesar (2026-10-23): el SLA se carga como numero + unidad
-- (minutos, horas o dias) y se guarda en minutos. Los dias son CORRIDOS, como
-- hasta ahora (sabados, domingos y feriados cuentan).
--
-- 1. tipo_reclamo.sla_minutos: la fuente del SLA (el backfill va en 120b).
-- 2. tipo_reclamo.sla_dias queda DERIVADO = CEIL(sla_minutos / 1440), por
--    compatibilidad: lo siguen devolviendo las APIs (la PWA y la app de agentes
--    lo tienen en sus tipos) y lo escriben los seeds viejos (un INSERT o UPDATE
--    que solo trae sla_dias deriva los minutos).
-- 3. trg_sla_reclamo calcula el vencimiento con los minutos (COALESCE con los
--    dias por si 120b todavia no corrio).
--
-- tipo_reclamo.duracion_estimada_min no se toca: sin uso desde que los reclamos
-- no se agendan (2026-10-21); sale del formulario de Maestros.
--
-- Idempotente. Verificado antes de aplicar (2026-10-23): ninguna DB tiene
-- sla_minutos; prod tiene los 282 tipos activos con sla_dias = 3.

ALTER TABLE tipo_reclamo ADD COLUMN IF NOT EXISTS sla_minutos INTEGER;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_tipo_reclamo_sla_minutos') THEN
    ALTER TABLE tipo_reclamo
      ADD CONSTRAINT ck_tipo_reclamo_sla_minutos CHECK (sla_minutos IS NULL OR sla_minutos > 0);
  END IF;
END $$;

CREATE OR REPLACE FUNCTION fn_tipo_reclamo_sla_sync()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.sla_minutos IS NULL AND NEW.sla_dias IS NOT NULL THEN
            NEW.sla_minutos := NEW.sla_dias * 1440;
        END IF;
    ELSIF NEW.sla_minutos IS NOT DISTINCT FROM OLD.sla_minutos
          AND NEW.sla_dias IS DISTINCT FROM OLD.sla_dias THEN
        -- Quien todavia escribe el SLA en dias.
        NEW.sla_minutos := NEW.sla_dias * 1440;
    END IF;
    NEW.sla_dias := CASE WHEN NEW.sla_minutos IS NULL THEN NULL
                         ELSE CEIL(NEW.sla_minutos / 1440.0)::INTEGER END;
    RETURN NEW;
END;
$function$;

-- CREATE OR REPLACE TRIGGER (PG 14+): re-aplicable sin un DROP previo.
CREATE OR REPLACE TRIGGER trg_tipo_reclamo_sla_sync
    BEFORE INSERT OR UPDATE ON tipo_reclamo
    FOR EACH ROW EXECUTE FUNCTION fn_tipo_reclamo_sla_sync();

CREATE OR REPLACE FUNCTION fn_set_sla_vencimiento()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_sla_minutos INTEGER;
BEGIN
    IF NEW.sla_vencimiento IS NULL AND NEW.id_tipo_reclamo IS NOT NULL THEN
        SELECT COALESCE(sla_minutos, sla_dias * 1440) INTO v_sla_minutos
          FROM tipo_reclamo
         WHERE id_tipo_reclamo = NEW.id_tipo_reclamo;
        IF v_sla_minutos IS NOT NULL THEN
            NEW.sla_vencimiento := NEW.fecha_alta + make_interval(mins => v_sla_minutos);
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;

COMMENT ON COLUMN tipo_reclamo.sla_minutos IS
  'SLA del tipo en minutos (mig 120): plazo corrido desde el alta del reclamo. Fuente del vencimiento (trg_sla_reclamo) y del % dentro del SLA del BI.';
COMMENT ON COLUMN tipo_reclamo.sla_dias IS
  'DERIVADO de sla_minutos (CEIL / 1440, trg_tipo_reclamo_sla_sync, mig 120). Solo por compatibilidad: no escribirlo.';
COMMENT ON COLUMN tipo_reclamo.duracion_estimada_min IS
  'Sin uso desde 2026-10-21 (los reclamos no se agendan). Fuera del formulario de Maestros.';
