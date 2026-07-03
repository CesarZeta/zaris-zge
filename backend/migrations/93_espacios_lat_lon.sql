-- Migración 93: geoposicionamiento de espacios de atención (Dashboard "Resumen de actividad municipal")
-- espacios_agenda ya tiene `direccion` (texto libre); se agregan coordenadas para
-- poder mostrar espacios (y turnos/entradas, que se ubican vía su espacio) en el mapa.
-- Mismo tipo NUMERIC(10,7) que reclamos/ciudadanos/empresas/emergencia_evento.

ALTER TABLE espacios_agenda
    ADD COLUMN IF NOT EXISTS latitud  NUMERIC(10,7) NULL,
    ADD COLUMN IF NOT EXISTS longitud NUMERIC(10,7) NULL;

COMMENT ON COLUMN espacios_agenda.latitud  IS 'Latitud del espacio (pin OSM del form de espacios)';
COMMENT ON COLUMN espacios_agenda.longitud IS 'Longitud del espacio (pin OSM del form de espacios)';
