-- Migración 26 — Cleanup de áreas duplicadas con/sin tilde (idempotente, por nombre)
--
-- Algunas áreas existen dos veces: una con tildes ("Secretaría de Cultura")
-- y otra sin tildes ("Secretaria de Cultura"), heredadas del proceso de
-- importación de datos legacy. Esta migración consolida cada par en un
-- canónico (el que tenga más referencias, o el activo, o el ID menor),
-- re-routea las FKs entrantes y soft-deletea el resto.
--
-- Opera por NOMBRE NORMALIZADO (lowercase + sin tildes), no por IDs
-- hardcodeados — los IDs difieren entre local y prod, así que la misma
-- migración aplica correctamente en ambos entornos. Ver CLAUDE.md §24.
--
-- Idempotente: corrida dos veces no rompe nada porque después de la primera
-- ya no hay duplicados activos.

-- 1. Snapshot defensivo (skip si ya existe de una corrida previa)
CREATE TABLE IF NOT EXISTS _backup_area_2026_05_10 AS
SELECT * FROM area;

-- 2. Función helper: ASCII fold de texto sin la extensión unaccent
CREATE OR REPLACE FUNCTION _ascii_fold(t TEXT) RETURNS TEXT AS $$
    SELECT LOWER(TRANSLATE(
        COALESCE(t, ''),
        'áéíóúüñÁÉÍÓÚÜÑàèìòùÀÈÌÒÙâêîôûÂÊÎÔÛ',
        'aeiouunAEIOUUNaeiouAEIOUaeiouAEIOU'
    ));
$$ LANGUAGE sql IMMUTABLE;

DO $$
DECLARE
    grupo RECORD;
    canonico_id INTEGER;
    otros_ids INTEGER[];
    grupo_tenia_activo BOOLEAN;
BEGIN
    -- 3. Procesar cada grupo de áreas con mismo nombre normalizado
    FOR grupo IN
        SELECT _ascii_fold(nombre) AS norm,
               array_agg(id_area ORDER BY id_area) AS ids,
               bool_or(activo) AS algun_activo
        FROM area
        GROUP BY _ascii_fold(nombre)
        HAVING COUNT(*) > 1
    LOOP
        grupo_tenia_activo := grupo.algun_activo;

        -- 3a. Elegir canónico: el con más referencias entrantes; en empate,
        -- el activo; en empate, el id menor.
        WITH refs AS (
            SELECT a.id_area,
                   a.activo::int AS act,
                   COALESCE((SELECT COUNT(*) FROM subarea WHERE id_area = a.id_area), 0) +
                   COALESCE((SELECT COUNT(*) FROM tipo_reclamo WHERE id_area = a.id_area), 0) +
                   COALESCE((SELECT COUNT(*) FROM reclamos WHERE id_area = a.id_area), 0) +
                   COALESCE((SELECT COUNT(*) FROM lugares_atencion WHERE id_area = a.id_area), 0)
                   AS total_refs
            FROM area a
            WHERE a.id_area = ANY(grupo.ids)
        )
        SELECT id_area INTO canonico_id
        FROM refs
        ORDER BY total_refs DESC, act DESC, id_area ASC
        LIMIT 1;

        otros_ids := ARRAY(SELECT unnest(grupo.ids) EXCEPT SELECT canonico_id);

        RAISE NOTICE 'Grupo "%": canonico=% otros=% algun_activo=%',
            grupo.norm, canonico_id, otros_ids, grupo_tenia_activo;

        -- 3b. Re-routear FKs entrantes desde otros_ids hacia canonico
        UPDATE reclamos SET id_area = canonico_id, fecha_modificacion = NOW()
            WHERE id_area = ANY(otros_ids);
        UPDATE subarea SET id_area = canonico_id, fecha_modificacion = NOW()
            WHERE id_area = ANY(otros_ids);
        UPDATE tipo_reclamo SET id_area = canonico_id, fecha_modificacion = NOW()
            WHERE id_area = ANY(otros_ids);
        -- lugares_atencion usa columnas legacy (modificado_en, no fecha_modificacion)
        UPDATE lugares_atencion SET id_area = canonico_id, modificado_en = NOW()
            WHERE id_area = ANY(otros_ids);

        -- 3c. Soft-delete los duplicados no canónicos
        UPDATE area SET activo = FALSE, fecha_modificacion = NOW()
            WHERE id_area = ANY(otros_ids) AND activo = TRUE;

        -- 3d. Si en el grupo había algún activo, asegurar que el canónico
        -- quede activo. Si TODOS estaban inactivos, no reactivar nada
        -- (área histórica sin uso).
        IF grupo_tenia_activo THEN
            UPDATE area SET activo = TRUE, fecha_modificacion = NOW()
                WHERE id_area = canonico_id AND activo = FALSE;
        END IF;
    END LOOP;
END $$;

-- 4. Cleanup del helper (no queremos dejar funciones aleatorias en el schema)
DROP FUNCTION _ascii_fold(TEXT);

-- Verificación esperada:
-- SELECT _ascii_fold(nombre) AS norm, COUNT(*) FROM area
--   GROUP BY _ascii_fold(nombre) HAVING COUNT(*) > 1;  -- 0 filas si todo OK
