-- Migracion 109 — Toda prestacion de ATENCION de la gestion Salud registra historia (2026-10-10)
--
-- Cierra el residuo del plan ATENCION §4 ("canal lateral turnos.observaciones"):
-- una prestacion de Salud con registra_atencion = FALSE (prod: "Atencion medica -
-- Clinica general") hacia que lo anotado al cumplir el turno fuera a
-- turnos.observaciones, visible para cualquiera con alcance al turno y para el
-- vecino en su app. Con la marca, va a turno_atencion (guard de historia clinica).
-- Desde el mismo commit, crear/editar prestacion fuerza la marca en Salud
-- (turnos.py::_registra_atencion_efectivo) y cumplir rechaza observaciones.
--
-- Solo datos, idempotente. "Salud" = area de la clave id_area_salud (mig 107b),
-- con el mismo CASE anti-basura que historia_clinica.area_salud. Gestion de la
-- prestacion = su id_subarea, o la subarea de su ubicacion si no la declara.

UPDATE tipo_prestacion tp
   SET registra_atencion = TRUE,
       fecha_modificacion = NOW()
  FROM configuracion_general cg
  JOIN area a
    ON a.id_area = CASE WHEN TRIM(cg.valor) ~ '^[0-9]{1,9}$' THEN TRIM(cg.valor)::int END
 WHERE cg.clave = 'id_area_salud' AND cg.activo = TRUE AND a.activo = TRUE
   AND tp.clase = 'atencion'
   AND COALESCE(tp.registra_atencion, FALSE) = FALSE
   AND (SELECT s.id_area FROM subarea s
         WHERE s.id_subarea = COALESCE(tp.id_subarea,
                 (SELECT e.id_subarea FROM espacios_agenda e WHERE e.id_espacio = tp.id_espacio_ubicacion))
       ) = a.id_area;
