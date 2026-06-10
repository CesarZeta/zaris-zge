-- Migración 80 — Habilitar RLS en catálogos legacy sin Row-Level Security
-- Motivo: advisor de Supabase `rls_disabled_in_public` (mail 2026-06-08).
-- Tablas en schema public expuestas a PostgREST sin RLS: cualquiera con la
-- anon key podía leer/escribir. Patrón deny-all (RLS habilitado SIN políticas,
-- §26): el backend no se afecta porque conecta como `postgres`, dueño de las
-- tablas, que bypassea RLS. Idempotente (ENABLE ROW LEVEL SECURITY lo es) y
-- tolera que la tabla no exista en local (drift de catálogos legacy).

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['actividades', 'nacionalidades', 'tipos_representacion', 'tipo_representacion']
    LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        END IF;
    END LOOP;
END $$;
