-- =============================================================================
-- Migracion 44 — Separar permiso 'turnos' en 'agenda' / 'turnos' / 'entradas'
-- =============================================================================
-- CLAUDE.md §30. Hasta ahora un unico codigo 'turnos' ("Turnos y eventos")
-- cubria todo el modulo Agenda. Con la definicion de los modulos Turnos y
-- Entradas como modulos propios (scaffold 2026-05-14) se separan en tres:
--
--   * 'agenda'   -> el sustrato: disponibilidad horaria de agentes y espacios.
--   * 'turnos'   -> ocupaciones tipo turno sobre la disponibilidad de agentes.
--   * 'entradas' -> reservas a eventos que ocupan disponibilidad de espacios.
--
-- La fila 'turnos' preexistente se RECONVIERTE en 'agenda' (UPDATE de la PK):
-- es seguro porque usuario_modulos.modulo_codigo tiene ON UPDATE implicito via
-- la FK, y ademas hoy no hay ninguna fila de override apuntando a 'turnos'
-- (verificado en prod 2026-05-14). Luego se insertan 'turnos' y 'entradas'.
--
-- Idempotente.
-- =============================================================================

BEGIN;

-- 1) Reconvertir 'turnos' -> 'agenda' (solo si todavia no se hizo) ------------
UPDATE modulos
   SET modulo_codigo = 'agenda',
       nombre        = 'Agenda',
       descripcion   = 'Disponibilidad horaria de agentes y espacios (sustrato de turnos y entradas)',
       fecha_modificacion = NOW()
 WHERE modulo_codigo = 'turnos';

-- Reapuntar overrides historicos que pudieran existir (defensa; hoy 0 filas)
UPDATE usuario_modulos
   SET modulo_codigo = 'agenda'
 WHERE modulo_codigo = 'turnos';

-- 2) Insertar los modulos nuevos --------------------------------------------
INSERT INTO modulos (modulo_codigo, nombre, descripcion, min_nivel_acceso) VALUES
  ('turnos',   'Turnos',   'Gestion de turnos sobre la disponibilidad de agentes',    3),
  ('entradas', 'Entradas', 'Gestion de entradas a eventos en espacios fisicos',       3)
ON CONFLICT (modulo_codigo) DO NOTHING;

COMMIT;
