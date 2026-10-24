-- Migración 126 — IT-01 F2: sin default de municipio
-- Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, Tarea 19. Requiere la 125c y el código de F2 desplegado
-- (todo INSERT manda su id_municipio: R2).
--
-- Anula la compatibilidad TEMPORAL que dejó la 125c:
--   1. id_municipio sin DEFAULT en toda tabla catalogo/operativo (incluye usuarios): un INSERT que
--      se olvide del municipio falla por NOT NULL en vez de caer en el municipio 1.
--   2. fn_municipio_por_defecto queda inerte (CREATE OR REPLACE, sin DROP): ya no lleva NULL/377
--      al municipio 1. Los triggers trg_000_municipio_defecto los borra el lote de limpieza.
-- Re-aplicable y sin DROP.

CREATE OR REPLACE FUNCTION fn_municipio_por_defecto()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Inerte desde la 126 (IT-01 F2): el código manda el municipio en cada INSERT.
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT m.tabla
          FROM municipio_tabla_clase m
         WHERE m.clase IN ('catalogo', 'operativo')
           AND to_regclass('public.' || quote_ident(m.tabla)) IS NOT NULL
         ORDER BY m.tabla
    LOOP
        EXECUTE format('ALTER TABLE %I ALTER COLUMN id_municipio SET DEFAULT NULL', r.tabla);
    END LOOP;
END $$;
