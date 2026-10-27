-- Migración 131 — IT-01 F4+F5, corte B: código corto de 4 letras y un municipio por partido.
-- Decisiones de César (2026-10-27): el municipio ES el partido (obligatorio, salvo los ficticios de
-- demo y prueba, que no lo llevan); el código corto de un municipio nuevo tiene 4 letras (los que ya
-- existen conservan el suyo: sus números ya emitidos lo llevan).
--
-- Sin DROP (va por MCP). Re-aplicable. Ampliar un VARCHAR no reescribe la tabla.

-- REC-<4 letras>-AAAA-NNNNNN ocupa 20: se amplían los números a 24 para no quedar justos.
ALTER TABLE municipios ALTER COLUMN codigo_corto TYPE VARCHAR(4);
ALTER TABLE reclamos ALTER COLUMN nro_reclamo TYPE VARCHAR(24);
ALTER TABLE ordenes_trabajo ALTER COLUMN nro_ot TYPE VARCHAR(24);
ALTER TABLE emergencia_evento ALTER COLUMN numero_operativo TYPE VARCHAR(24);

-- Un partido, un municipio vigente (uno de baja libera el partido).
CREATE UNIQUE INDEX IF NOT EXISTS uq_municipios_partido_vigente
    ON municipios (id_partido) WHERE id_partido IS NOT NULL AND estado <> 'baja';
