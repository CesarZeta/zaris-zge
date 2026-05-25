-- Migración 59 — Trigger de numeración para ordenes_trabajo (nro_ot)
--
-- Hallazgo QA 2026-05-25: las OT creadas vía POST /ot y /ot/con-agenda quedaban
-- con nro_ot NULL. CLAUDE.md §18 afirmaba que existía trg_nro_ot, pero el trigger
-- NO existía en prod (drift). El backend devolvía un fallback "OT-{id}" en la
-- respuesta pero nunca lo persistía.
--
-- Fix: recrear la función + trigger BEFORE INSERT, espejo de fn_generar_nro_reclamo,
-- y backfillear las filas históricas con nro_ot NULL.
-- Idempotente.

CREATE OR REPLACE FUNCTION public.fn_generar_nro_ot()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.nro_ot IS NULL THEN
        NEW.nro_ot := 'OT-' || TO_CHAR(NOW(), 'YYYY') || '-' || LPAD(NEW.id_ot::TEXT, 6, '0');
    END IF;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_nro_ot ON public.ordenes_trabajo;
CREATE TRIGGER trg_nro_ot
    BEFORE INSERT ON public.ordenes_trabajo
    FOR EACH ROW
    EXECUTE FUNCTION public.fn_generar_nro_ot();

-- Backfill de filas existentes sin número. Usa la fecha_alta de la OT (no NOW())
-- para que el año del número refleje cuándo se creó realmente.
UPDATE public.ordenes_trabajo
SET nro_ot = 'OT-' || TO_CHAR(COALESCE(fecha_alta, NOW()), 'YYYY') || '-' || LPAD(id_ot::TEXT, 6, '0')
WHERE nro_ot IS NULL;
