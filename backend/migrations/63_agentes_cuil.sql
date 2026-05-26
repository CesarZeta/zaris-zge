-- Migración 63: agregar CUIL al maestro de Agentes.
-- El agente (persona física que ejecuta OT/turnos) debe tener CUIL, además del
-- cargo (id_cargo) y la subárea (id_subarea) que ya tenía. Se administra desde
-- Maestros (admin_tablas → Agentes). Idempotente.

ALTER TABLE agentes
    ADD COLUMN IF NOT EXISTS cuil VARCHAR(11) NULL;

COMMENT ON COLUMN agentes.cuil IS 'CUIL del agente (11 dígitos, sin guiones).';
