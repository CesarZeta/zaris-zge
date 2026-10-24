-- Migración 125d — IT-01 F1: FK compuestas entre tablas del mismo municipio
-- Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, Tarea 3. Requiere la 125c (id_municipio NOT NULL).
--
-- Por cada FK simple declarada entre dos tablas catalogo/operativo (hija.col → padre.ref), agrega
-- una FK compuesta (id_municipio, col) → padre (id_municipio, ref). Así la base rechaza, por
-- ejemplo, un reclamo de un municipio con el tipo de reclamo de otro, y un JOIN por una FK
-- declarada no puede cruzar municipios (regla R1 de F2: alcanza con filtrar la tabla raíz).
--
-- Excluidas: las FK hacia `usuarios` (columnas de auditoría id_usuario_*: el super administrador
-- de F3 no tiene municipio) y las FK hacia tablas globales. MATCH SIMPLE: con la columna en NULL
-- no se verifica. La FK compuesta COPIA la acción ON DELETE de la original (CASCADE, RESTRICT, o SET NULL /
-- SET DEFAULT solo sobre la columna, sin tocar id_municipio): Postgres dispara los triggers de FK
-- por orden de nombre interno, y una compuesta NO ACTION frenaría el borrado antes de que la
-- cascada original borre los hijos (cazado por smoke_publico_auth.py, que limpia por DELETE).
-- Re-aplicable y sin DROP.

DO $$
DECLARE
    r RECORD;
    v_fk TEXT;
    v_uq TEXT;
    v_accion TEXT;
    v_creadas INTEGER := 0;
BEGIN
    FOR r IN
        SELECT c.conname,
               ch.relname AS hija,
               pa.relname AS padre,
               (SELECT a.attname FROM pg_attribute a WHERE a.attrelid = c.conrelid  AND a.attnum = c.conkey[1])  AS col,
               (SELECT a.attname FROM pg_attribute a WHERE a.attrelid = c.confrelid AND a.attnum = c.confkey[1]) AS ref,
               c.confdeltype
          FROM pg_constraint c
          JOIN pg_class ch ON ch.oid = c.conrelid
          JOIN pg_class pa ON pa.oid = c.confrelid
          JOIN municipio_tabla_clase mh ON mh.tabla = ch.relname AND mh.clase IN ('catalogo', 'operativo')
          JOIN municipio_tabla_clase mp ON mp.tabla = pa.relname AND mp.clase IN ('catalogo', 'operativo')
         WHERE c.contype = 'f'
           AND array_length(c.conkey, 1) = 1
           AND ch.relnamespace = 'public'::regnamespace
           AND pa.relname <> 'usuarios'
           AND c.conname NOT LIKE 'fkm\_%'
         ORDER BY ch.relname, c.conname
    LOOP
        CONTINUE WHEN r.col = 'id_municipio';

        v_uq := left('uqm_' || r.padre || '_' || r.ref, 63);
        EXECUTE format('CREATE UNIQUE INDEX IF NOT EXISTS %I ON %I (id_municipio, %I)', v_uq, r.padre, r.ref);

        v_fk := left('fkm_' || r.conname, 63);
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
                        WHERE conrelid = ('public.' || quote_ident(r.hija))::regclass AND conname = v_fk) THEN
            v_accion := CASE r.confdeltype
                            WHEN 'c' THEN ' ON DELETE CASCADE'
                            WHEN 'r' THEN ' ON DELETE RESTRICT'
                            WHEN 'n' THEN format(' ON DELETE SET NULL (%I)', r.col)
                            WHEN 'd' THEN format(' ON DELETE SET DEFAULT (%I)', r.col)
                            ELSE '' END;
            EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (id_municipio, %I) '
                           'REFERENCES %I (id_municipio, %I)%s NOT VALID',
                           r.hija, v_fk, r.col, r.padre, r.ref, v_accion);
            EXECUTE format('ALTER TABLE %I VALIDATE CONSTRAINT %I', r.hija, v_fk);
            v_creadas := v_creadas + 1;
        END IF;
    END LOOP;
    RAISE NOTICE 'Mig 125d: % FK compuestas creadas', v_creadas;
END $$;
