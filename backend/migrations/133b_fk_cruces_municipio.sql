-- Migración 133b — IT-01: las FK que faltaban en prod para que el clonador no cruce municipios
-- Requiere la 133 (sin cruces). En local estas FK ya existían (drift viejo, cazado en la prueba de
-- cierre de F4+F5 el 2026-10-30); en prod faltaban, y el clonador de municipios reapunta solo las
-- columnas con FK. Agrega la FK simple de cada columna (mismo nombre y acción que en local) y su FK
-- compuesta por municipio (como la 125d), así la base rechaza cualquier referencia a otro municipio.
--
-- Sin DROP. Re-aplicable: la FK simple se crea solo si la columna no tiene ninguna; la compuesta, si
-- no existe una con su nombre.

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('tipo_reclamo', 'id_subarea', 'subarea', 'id_subarea', 'tipo_reclamo_id_subarea_fkey'),
            ('subarea',      'id_area',    'area',    'id_area',    'subarea_id_area_fkey'),
            ('agentes',      'id_cargo',   'cargos',  'id_cargo',   'agentes_id_cargo_fkey'),
            ('equipos',      'id_subarea', 'subarea', 'id_subarea', 'equipos_id_subarea_fkey')
        ) AS v(hija, col, padre, ref, nombre)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint c
             WHERE c.conrelid = ('public.' || r.hija)::regclass AND c.contype = 'f'
               AND c.conkey = ARRAY[(SELECT attnum FROM pg_attribute
                                      WHERE attrelid = ('public.' || r.hija)::regclass AND attname = r.col)]) THEN
            EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES %I (%I) ON DELETE SET NULL',
                           r.hija, r.nombre, r.col, r.padre, r.ref);
        END IF;

        EXECUTE format('CREATE UNIQUE INDEX IF NOT EXISTS %I ON %I (id_municipio, %I)',
                       left('uqm_' || r.padre || '_' || r.ref, 63), r.padre, r.ref);

        IF NOT EXISTS (SELECT 1 FROM pg_constraint
                        WHERE conrelid = ('public.' || r.hija)::regclass AND conname = 'fkm_' || r.nombre) THEN
            EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (id_municipio, %I) '
                           'REFERENCES %I (id_municipio, %I) ON DELETE SET NULL (%I) NOT VALID',
                           r.hija, 'fkm_' || r.nombre, r.col, r.padre, r.ref, r.col);
            EXECUTE format('ALTER TABLE %I VALIDATE CONSTRAINT %I', r.hija, 'fkm_' || r.nombre);
        END IF;
    END LOOP;
END $$;
