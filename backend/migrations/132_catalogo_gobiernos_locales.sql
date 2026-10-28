-- Migración 132 — catálogo de gobiernos locales con su código oficial (Georef).
-- Diseño: PLAN_CONTORNO_MUNICIPIO_DISENO.md §4.2 (aprobado por César, 2026-10-28). El código une
-- cada fila con su contorno oficial del IGN (capa ign:municipio, campo in1 = código de Georef).
--
-- Sin DROP (va por MCP). Re-aplicable. Las dos tablas siguen siendo `global` en municipio_tabla_clase.
-- Los datos van en la 132b (generada por tools/georef_catalogo.py).

ALTER TABLE provincias ADD COLUMN IF NOT EXISTS codigo_georef CHAR(2);
CREATE UNIQUE INDEX IF NOT EXISTS uq_provincias_codigo_georef ON provincias (codigo_georef)
    WHERE codigo_georef IS NOT NULL;

ALTER TABLE partidos ADD COLUMN IF NOT EXISTS codigo_georef VARCHAR(6);
ALTER TABLE partidos ADD COLUMN IF NOT EXISTS categoria VARCHAR(40);
ALTER TABLE partidos ADD COLUMN IF NOT EXISTS nombre_completo VARCHAR(200);
CREATE UNIQUE INDEX IF NOT EXISTS uq_partidos_codigo_georef ON partidos (codigo_georef)
    WHERE codigo_georef IS NOT NULL;
