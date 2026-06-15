-- Migracion 91: override de disponibilidad para equipos sin agentes.
--
-- Decision de modelo (sesion 2026-06-15): la disponibilidad de un equipo de
-- trabajo es la UNION de los horarios de sus agentes activos (no el horario
-- propio del equipo). Por lo tanto un equipo SIN agentes no tiene disponibilidad
-- y no se le puede asignar OT con horario.
--
-- Esta clave habilita un OVERRIDE global: si es 'true', un equipo sin agentes
-- usa su propio horario cargado en disponibilidad_recurso (tipo_recurso='equipo')
-- en lugar de quedar sin disponibilidad. Default 'false' (comportamiento por
-- agentes). Aplica tanto en la grilla de Agenda (services/agenda.py) como en el
-- planificador de OT (_slots_libres_recurso).
--
-- Editable desde Config -> Sistema (S41).
--
-- tipo='boolean'. Idempotente (ON CONFLICT DO NOTHING).
-- DRIFT prod vs local (S24/S41): prod tiene columna `tipo` NOT NULL, local no.

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
            ('equipos_sin_agentes_usan_horario_propio', 'false', 'boolean',
             'Si es true, un equipo de trabajo SIN agentes usa su propio horario cargado para mostrarse disponible en la agenda y recibir OT. Si es false (recomendado), la disponibilidad de un equipo es siempre la union de los horarios de sus agentes, y un equipo sin agentes no tiene disponibilidad.',
             TRUE)
        ON CONFLICT (clave) DO NOTHING;
    ELSE
        INSERT INTO configuracion_general (clave, valor, descripcion, activo)
        VALUES
            ('equipos_sin_agentes_usan_horario_propio', 'false',
             'Si es true, un equipo de trabajo SIN agentes usa su propio horario cargado para mostrarse disponible en la agenda y recibir OT. Si es false (recomendado), la disponibilidad de un equipo es siempre la union de los horarios de sus agentes, y un equipo sin agentes no tiene disponibilidad.',
             TRUE)
        ON CONFLICT (clave) DO NOTHING;
    END IF;
END $$;
