-- Migracion 117 — Texto de resolucion del reclamo (2026-10-21)
--
-- Decision de Cesar (2026-10-21): quien cierra un reclamo (el agente que lo tomo,
-- el supervisor o el admin) escribe una resolucion, y el VECINO la ve en su app y
-- en el aviso de cierre. Hasta hoy el texto de cierre de la OT quedaba solo en
-- ordenes_trabajo.observaciones y la nota del cambio de estado PISABA las
-- observaciones del alta (que tambien le llegaban al vecino).
--
-- Aditiva e idempotente: el codigo anterior no la lee.

ALTER TABLE reclamos ADD COLUMN IF NOT EXISTS resolucion TEXT;

COMMENT ON COLUMN reclamos.resolucion IS
  'Texto de resolucion que ve el vecino (app y aviso de cierre). Lo escribe quien resuelve: POST /reclamos/{id}/resolver, PUT /reclamos/{id}/estado a Resuelto o el cierre de la OT (mig 117).';
