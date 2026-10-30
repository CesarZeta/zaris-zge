-- Migración 133 — IT-01: referencias de catálogo que cruzaban de municipio
-- Cazado en la prueba de cierre de F4+F5 (2026-10-30). En prod nunca existieron las FK de
-- tipo_reclamo.id_subarea ni de subarea.id_area (en local sí: drift viejo). El clonador de municipios
-- reapunta solo las columnas con FK, así que el modelo (5) y el Municipio de Prueba (6) quedaron con
-- sus gestiones colgando de las secretarías de San Andrés y sus tipos de reclamo de las gestiones de
-- San Andrés. Acá se reapuntan, POR NOMBRE, a las filas del propio municipio; la 133b agrega las FK.
--
-- Solo datos. Re-aplicable: sin cruces no hace nada. Falla entera si un cruce no tiene exactamente
-- una fila equivalente en su municipio, o si al final queda alguno.
-- Backup en prod: _backup_cruces_subarea_2026_10_30 y _backup_cruces_tipo_reclamo_2026_10_30.

DO $$
DECLARE
    v_sin_unica INTEGER;
BEGIN
    SELECT count(*) INTO v_sin_unica
      FROM subarea s JOIN area ajena ON ajena.id_area = s.id_area
     WHERE ajena.id_municipio <> s.id_municipio
       AND (SELECT count(*) FROM area propia
             WHERE propia.id_municipio = s.id_municipio AND lower(propia.nombre) = lower(ajena.nombre)) <> 1;
    IF v_sin_unica > 0 THEN
        RAISE EXCEPTION 'Mig 133: % gestiones sin una única secretaría equivalente en su municipio', v_sin_unica;
    END IF;

    SELECT count(*) INTO v_sin_unica
      FROM tipo_reclamo t JOIN subarea ajena ON ajena.id_subarea = t.id_subarea
     WHERE ajena.id_municipio <> t.id_municipio
       AND (SELECT count(*) FROM subarea propia
             WHERE propia.id_municipio = t.id_municipio AND lower(propia.nombre) = lower(ajena.nombre)) <> 1;
    IF v_sin_unica > 0 THEN
        RAISE EXCEPTION 'Mig 133: % tipos de reclamo sin una única gestión equivalente en su municipio', v_sin_unica;
    END IF;
END $$;

UPDATE subarea s
   SET id_area = propia.id_area, fecha_modificacion = NOW()
  FROM area ajena, area propia
 WHERE ajena.id_area = s.id_area
   AND ajena.id_municipio <> s.id_municipio
   AND propia.id_municipio = s.id_municipio
   AND lower(propia.nombre) = lower(ajena.nombre);

UPDATE tipo_reclamo t
   SET id_subarea = propia.id_subarea, fecha_modificacion = NOW()
  FROM subarea ajena, subarea propia
 WHERE ajena.id_subarea = t.id_subarea
   AND ajena.id_municipio <> t.id_municipio
   AND propia.id_municipio = t.id_municipio
   AND lower(propia.nombre) = lower(ajena.nombre);

DO $$
DECLARE
    v_quedan INTEGER;
BEGIN
    SELECT (SELECT count(*) FROM subarea s JOIN area a ON a.id_area = s.id_area
             WHERE a.id_municipio <> s.id_municipio)
         + (SELECT count(*) FROM tipo_reclamo t JOIN subarea s ON s.id_subarea = t.id_subarea
             WHERE s.id_municipio <> t.id_municipio)
      INTO v_quedan;
    IF v_quedan > 0 THEN
        RAISE EXCEPTION 'Mig 133: quedan % referencias a otro municipio', v_quedan;
    END IF;
END $$;
