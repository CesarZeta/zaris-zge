-- Migración 135 — IT-01: las plantillas de encuestas no se vacían.
-- Cazado en la prueba de cierre de F4+F5 (2026-11-03): vaciar Maestros borraba encuesta_plantilla,
-- encuesta_pregunta y encuesta_opcion, que no se pueden crear desde la aplicación (solo las copia el
-- alta): el municipio se quedaba sin encuestas para siempre. Decisión de César: siempre queda el
-- modelo, y cada municipio lo cambiará si quiere (editor pendiente de diseño).
-- Pasan al grupo configuracion, que el vaciado no toca nunca (services/municipios/vaciado.py).
--
-- Solo datos. Re-aplicable. Falla si alguna de las tres tablas no está clasificada.

DO $$
DECLARE
  v_clasificadas INT;
BEGIN
  UPDATE municipio_tabla_clase
     SET grupo = 'configuracion'
   WHERE tabla IN ('encuesta_plantilla', 'encuesta_pregunta', 'encuesta_opcion');

  SELECT count(*) INTO v_clasificadas
    FROM municipio_tabla_clase
   WHERE tabla IN ('encuesta_plantilla', 'encuesta_pregunta', 'encuesta_opcion')
     AND grupo = 'configuracion';

  IF v_clasificadas <> 3 THEN
    RAISE EXCEPTION 'Migración 135: se esperaban 3 tablas en configuracion y hay %', v_clasificadas;
  END IF;
END $$;
