-- =============================================================================
-- Migracion 42 - Agenda: ampliar tipo_recurso para incluir 'espacio'
--
-- Modifica los CHECK constraints de `ocupaciones.tipo_recurso` y
-- `evento_encargados.tipo_recurso` para aceptar 'espacio' ademas de
-- 'agente' y 'equipo'.
--
-- Sin FK fisica a espacios_agenda porque `id_recurso` es polimorfica
-- (puede apuntar a agentes, equipos o espacios segun tipo_recurso).
-- La validacion de existencia del recurso queda en el backend (igual que
-- hoy con agente/equipo).
--
-- Idempotente: drop solo si el CHECK existe, recreate con el set ampliado.
-- =============================================================================

ALTER TABLE ocupaciones DROP CONSTRAINT IF EXISTS ck_ocup_tipo_recurso;
ALTER TABLE ocupaciones ADD  CONSTRAINT ck_ocup_tipo_recurso
  CHECK (tipo_recurso IN ('agente','equipo','espacio'));

ALTER TABLE evento_encargados DROP CONSTRAINT IF EXISTS ck_evt_enc_tipo_recurso;
ALTER TABLE evento_encargados ADD  CONSTRAINT ck_evt_enc_tipo_recurso
  CHECK (tipo_recurso IN ('agente','equipo','espacio'));
