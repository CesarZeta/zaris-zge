-- Migración 94 — Catálogo de municipios: campo país (IT-02, reunión Config/UX 06/07/2026)
-- Agrega la columna `pais` a `municipios`. El nombre real, el prefijo (codigo_corto)
-- y el valor de país del municipio de trabajo se setean como UPDATE de datos aparte
-- (94b), separado del DDL por atomicidad (§21).
--
-- Nota: NO se agrega `logo` acá. La identidad visual del municipio (logo/nombre)
-- vive hoy en configuracion_general (municipio_logo_url / municipio_nombre, §41) y
-- se edita desde Config → Identidad. Consolidar todo en una ficha única es parte de
-- IT-01 (multi-tenant), que se diseña aparte.

ALTER TABLE municipios ADD COLUMN IF NOT EXISTS pais VARCHAR(80);

COMMENT ON COLUMN municipios.pais IS 'País del municipio (IT-02). Ej: Argentina.';
