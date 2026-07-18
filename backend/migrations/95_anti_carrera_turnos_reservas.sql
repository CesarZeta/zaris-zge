-- ============================================================================
-- 95: Anti-carrera (TOCTOU) en turnos y reservas de eventos.
--     Auditoria de seguridad 2026-07, hallazgos [14][15][37][39] (2a ronda).
--
-- Los handlers validan solape/cupo/duplicado con check-then-insert sin lock:
-- dos requests concurrentes pasan ambos el check e insertan. Estos indices
-- UNIQUE parciales son la red de contencion en DB; el cierre completo lo dan
-- los locks agregados en el backend (advisory lock por recurso+fecha en las
-- altas de turnos, SELECT ... FOR UPDATE del evento antes del cupo) y el
-- manejo de IntegrityError -> 409 en todos los sitios de escritura.
--
-- Verificado en prod y local antes de redactar (2026-07-18):
--   * turnos: 0 duplicados por slot y 0 solapamientos (excluyendo cancelados).
--   * evento_reservas: los unicos pares (evento, ciudadano) repetidos incluyen
--     una reserva 'cancelada' -> quedan FUERA del predicado parcial. Sin
--     limpieza de datos necesaria.
--
-- Idempotente (IF NOT EXISTS). Tablas ya existentes: sin cambios de RLS.
-- ============================================================================

-- 1) Un solo turno vigente por slot exacto de AGENTE. Los cancelados salen del
--    predicado (cancelar libera el slot y permite re-reservar). Los cumplidos
--    siguen bloqueando su slot historico (coherente con la ocupacion espejo,
--    que solo se soft-deletea al cancelar).
CREATE UNIQUE INDEX IF NOT EXISTS uq_turnos_slot_agente
    ON turnos (id_agente, fecha, hora_inicio)
    WHERE id_agente IS NOT NULL AND activo = TRUE AND estado <> 'cancelado';

-- 2) Idem para slot de ESPACIO (recurso polimorfico XOR, ck_turnos_recurso).
CREATE UNIQUE INDEX IF NOT EXISTS uq_turnos_slot_espacio
    ON turnos (id_espacio, fecha, hora_inicio)
    WHERE id_espacio IS NOT NULL AND activo = TRUE AND estado <> 'cancelado';

-- 3) Maximo UNA reserva no-cancelada por (evento, ciudadano) — regla de
--    producto confirmada por Cesar 2026-07-18 (aplica tambien al backoffice;
--    las vias publicas ya la validaban en el handler).
--    El predicado de un indice parcial no admite JOIN al catalogo
--    estado_reserva: se resuelve el id de 'cancelada' aca y se falla explicito
--    si falta el seed (en local y prod es 3, pero no se hardcodea).
DO $$
DECLARE
    v_cancelada integer;
BEGIN
    SELECT id_estado_reserva INTO v_cancelada
      FROM estado_reserva
     WHERE codigo = 'cancelada';
    IF v_cancelada IS NULL THEN
        RAISE EXCEPTION 'mig 95: falta seed de estado_reserva codigo=''cancelada''';
    END IF;
    EXECUTE format(
        'CREATE UNIQUE INDEX IF NOT EXISTS uq_evento_reservas_ciudadano_vigente '
        'ON evento_reservas (id_evento, id_ciudadano) '
        'WHERE activo = TRUE AND id_estado_reserva <> %s',
        v_cancelada
    );
END $$;
