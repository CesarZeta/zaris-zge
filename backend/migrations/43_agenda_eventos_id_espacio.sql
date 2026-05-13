-- =============================================================================
-- Migracion 43 - Agenda: eventos.id_espacio
--
-- Permite asociar opcionalmente un evento a un espacio concreto donde se
-- realiza (sala, oficina, vehiculo, etc.). Es opcional porque hay eventos
-- itinerantes / al aire libre / virtuales que no usan espacio fisico.
--
-- Cuando el evento tiene id_espacio, el frontend lo pinta como bloque en la
-- fila del espacio en la vista por espacios (igual que un encargado en la
-- fila del agente). Backend NO sincroniza automaticamente esto con ocupaciones
-- porque el espacio puede ser "destino del publico" sin que haya un recurso
-- bloqueado (el cupo del evento es lo que limita, no la ocupacion del espacio).
-- =============================================================================

ALTER TABLE eventos
  ADD COLUMN IF NOT EXISTS id_espacio INTEGER REFERENCES espacios_agenda(id_espacio) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_eventos_id_espacio
  ON eventos (id_espacio) WHERE id_espacio IS NOT NULL AND activo = TRUE;
