-- IT-01 F6 — Segunda barrera por municipio (PLAN_MULTI_MUNICIPIO_F6_DISENO.md §4.2, F6_2.md Task 1).
--
-- Requiere que exista el usuario `zaris_app` (sin BYPASSRLS, no dueño): en local lo crea
-- tools/crear_usuario_zaris_app_local.sql; en prod lo crea César en el SQL Editor (F6.3).
-- No lleva claves. Idempotente (DROP POLICY IF EXISTS antes de cada CREATE).
--
-- Mientras el backend se conecte como `postgres` (dueño, BYPASSRLS) estas políticas no cambian
-- nada: rigen recién con DB_BARRERA=true. `anon` y `authenticated` siguen sin ninguna política.
--
-- Políticas, generadas desde municipio_tabla_clase:
--   catalogo / operativo / mixta (y usuarios): id_municipio = app.id_municipio, para ver y escribir.
--     Sin la variable la comparación da NULL: no se ve nada (falla cerrada).
--   configuracion_general: además ve (solo lectura) los parámetros globales (id_municipio NULL).
--   global: todo (no tiene municipio que separar).
-- Los respaldos _backup_* no reciben ningún permiso.

DO $$
DECLARE
    t RECORD;
    lista jsonb;
    barrera CONSTANT text :=
        'id_municipio = (SELECT NULLIF(current_setting(''app.id_municipio'', true), '''')::int)';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zaris_app') THEN
        RAISE EXCEPTION 'Falta el usuario zaris_app: crearlo antes de aplicar la 138 (ver el encabezado).';
    END IF;

    EXECUTE 'GRANT USAGE ON SCHEMA public TO zaris_app';
    EXECUTE 'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO zaris_app';
    EXECUTE 'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO zaris_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public '
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zaris_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public '
            'GRANT USAGE, SELECT ON SEQUENCES TO zaris_app';

    -- Se materializa la lista antes del bucle: municipio_tabla_clase también recibe su ALTER TABLE
    -- y no se puede alterar una tabla mientras un cursor la recorre.
    SELECT jsonb_agg(jsonb_build_object('tabla', tabla, 'clase', clase) ORDER BY tabla) INTO lista
      FROM municipio_tabla_clase
     WHERE to_regclass('public.' || quote_ident(tabla)) IS NOT NULL;

    FOR t IN SELECT x->>'tabla' AS tabla, x->>'clase' AS clase FROM jsonb_array_elements(lista) AS x
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tabla);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO zaris_app', t.tabla);
        EXECUTE format('DROP POLICY IF EXISTS barrera_municipio ON public.%I', t.tabla);
        EXECUTE format('DROP POLICY IF EXISTS barrera_global ON public.%I', t.tabla);
        EXECUTE format('DROP POLICY IF EXISTS barrera_parametros_globales ON public.%I', t.tabla);

        IF t.clase = 'global' THEN
            EXECUTE format('CREATE POLICY barrera_global ON public.%I FOR ALL TO zaris_app '
                           'USING (true) WITH CHECK (true)', t.tabla);
        ELSE
            EXECUTE format('CREATE POLICY barrera_municipio ON public.%I FOR ALL TO zaris_app '
                           'USING (%s) WITH CHECK (%s)', t.tabla, barrera, barrera);
        END IF;

        IF t.tabla = 'configuracion_general' THEN
            EXECUTE 'CREATE POLICY barrera_parametros_globales ON public.configuracion_general '
                    'FOR SELECT TO zaris_app USING (id_municipio IS NULL)';
        END IF;
    END LOOP;
END $$;
