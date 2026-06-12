-- Migracion 87: claves de configuracion para el sesgo geografico del geocoding.
--
-- Hasta ahora el bounding box del municipio (regla de diseno S23: "Avenida
-- Maipu" no debe traer la de Mendoza) vivia hardcodeado en constantes de
-- backend/app/api/routes/geo.py (GEO_BBOX_*). Un deploy de otro municipio
-- exigia tocar codigo. Estas claves lo hacen configurable desde
-- Config -> Sistema (S41); geo.py las lee con cache (TTL 5 min) y cae a las
-- constantes (Vicente Lopez demo) si faltan o son invalidas.
--
-- Claves:
--   geo_bbox_centro_lat     latitud del centro del municipio (decimal WGS84).
--   geo_bbox_centro_lon     longitud del centro del municipio (decimal WGS84).
--   geo_bbox_delta_grados   semi-lado del bbox en grados (~0.27 = ~28 km).
--
-- tipo='string' (los valores son decimales; 'integer' no aplica).
-- Idempotente (ON CONFLICT DO NOTHING - no pisa un valor ajustado a mano).
--
-- DRIFT prod vs local (regla S24/S41): prod tiene columna `tipo` NOT NULL,
-- local NO la tiene. El DO block arma el INSERT segun exista la columna
-- (patron de 75b_tramites_retencion_config.sql).

DO $$
DECLARE
    tiene_tipo BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'configuracion_general' AND column_name = 'tipo'
    ) INTO tiene_tipo;

    IF tiene_tipo THEN
        INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
        VALUES
            ('geo_bbox_centro_lat',   '-34.5305', 'string', 'Latitud del centro del municipio (decimal, WGS84). Centra la zona donde el buscador de direcciones acepta resultados. Cambios aplican en ~5 minutos.', TRUE),
            ('geo_bbox_centro_lon',   '-58.4779', 'string', 'Longitud del centro del municipio (decimal, WGS84). Centra la zona donde el buscador de direcciones acepta resultados. Cambios aplican en ~5 minutos.', TRUE),
            ('geo_bbox_delta_grados', '0.27',     'string', 'Radio de la zona de busqueda de direcciones, en grados (~0.27 = ~28 km). Resultados fuera de la zona se descartan. Cambios aplican en ~5 minutos.', TRUE)
        ON CONFLICT (clave) DO NOTHING;
    ELSE
        INSERT INTO configuracion_general (clave, valor, descripcion, activo)
        VALUES
            ('geo_bbox_centro_lat',   '-34.5305', 'Latitud del centro del municipio (decimal, WGS84). Centra la zona donde el buscador de direcciones acepta resultados. Cambios aplican en ~5 minutos.', TRUE),
            ('geo_bbox_centro_lon',   '-58.4779', 'Longitud del centro del municipio (decimal, WGS84). Centra la zona donde el buscador de direcciones acepta resultados. Cambios aplican en ~5 minutos.', TRUE),
            ('geo_bbox_delta_grados', '0.27',     'Radio de la zona de busqueda de direcciones, en grados (~0.27 = ~28 km). Resultados fuera de la zona se descartan. Cambios aplican en ~5 minutos.', TRUE)
        ON CONFLICT (clave) DO NOTHING;
    END IF;
END $$;
