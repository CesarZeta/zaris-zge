-- Migración 134 — IT-01: gestiones guardadas dentro de los JSON de las transiciones de trámites
-- que cruzaban de municipio.
-- Cazado en la prueba de cierre de F4+F5 (2026-11-02): «Derivar a Espacios Verdes» en el Municipio
-- de Prueba (6) falló con fkm_tramite_id_subarea_actual_fkey porque destino_automatico_jsonb apuntaba
-- a la gestión de San Andrés. El clonador copia los JSON tal cual (solo reapunta columnas) y
-- contar_cruces no los mira: el modelo (5) y el 6 tenían 6 destinos automáticos y 7 «quién puede»
-- con gestiones de San Andrés. Acá se reapuntan, POR NOMBRE, a la gestión del propio municipio.
-- El arreglo del clonador y de contar_cruces va en código.
--
-- Solo datos. Re-aplicable: sin cruces no hace nada. Falla entera si un cruce no tiene exactamente
-- una gestión equivalente en su municipio, o si al final queda alguno.
-- Backup en prod: _backup_cruces_transicion_2026_11_02.

DO $$
DECLARE
    v_sin_unica INTEGER;
BEGIN
    WITH refs AS (
        SELECT x.id_municipio, (x.destino_automatico_jsonb->>'id')::int AS id_ref
          FROM tipo_tramite_transicion x
         WHERE x.destino_automatico_jsonb->>'tipo' = 'subarea'
        UNION ALL
        SELECT x.id_municipio, s.v::int
          FROM tipo_tramite_transicion x,
               jsonb_array_elements_text(COALESCE(x.quien_puede_jsonb->'subareas', '[]'::jsonb)) s(v)
    )
    SELECT count(*) INTO v_sin_unica
      FROM refs r JOIN subarea ajena ON ajena.id_subarea = r.id_ref
     WHERE ajena.id_municipio <> r.id_municipio
       AND (SELECT count(*) FROM subarea propia
             WHERE propia.id_municipio = r.id_municipio AND lower(propia.nombre) = lower(ajena.nombre)) <> 1;
    IF v_sin_unica > 0 THEN
        RAISE EXCEPTION 'Mig 134: % referencias sin una única gestión equivalente en su municipio', v_sin_unica;
    END IF;
END $$;

UPDATE tipo_tramite_transicion x
   SET destino_automatico_jsonb = jsonb_set(
           jsonb_set(x.destino_automatico_jsonb, '{id}', to_jsonb(propia.id_subarea)),
           '{nombre}', to_jsonb(propia.nombre)),
       fecha_modificacion = NOW()
  FROM subarea ajena, subarea propia
 WHERE x.destino_automatico_jsonb->>'tipo' = 'subarea'
   AND ajena.id_subarea = (x.destino_automatico_jsonb->>'id')::int
   AND ajena.id_municipio <> x.id_municipio
   AND propia.id_municipio = x.id_municipio
   AND lower(propia.nombre) = lower(ajena.nombre);

UPDATE tipo_tramite_transicion x
   SET quien_puede_jsonb = jsonb_set(x.quien_puede_jsonb, '{subareas}', (
           SELECT jsonb_agg(COALESCE(
                      (SELECT to_jsonb(propia.id_subarea)
                         FROM subarea ajena
                         JOIN subarea propia ON propia.id_municipio = x.id_municipio
                                            AND lower(propia.nombre) = lower(ajena.nombre)
                        WHERE ajena.id_subarea = e.v::int AND ajena.id_municipio <> x.id_municipio),
                      to_jsonb(e.v::int)) ORDER BY e.ord)
             FROM jsonb_array_elements_text(x.quien_puede_jsonb->'subareas') WITH ORDINALITY e(v, ord))),
       fecha_modificacion = NOW()
 WHERE EXISTS (SELECT 1
                 FROM jsonb_array_elements_text(COALESCE(x.quien_puede_jsonb->'subareas', '[]'::jsonb)) s(v)
                 JOIN subarea ajena ON ajena.id_subarea = s.v::int
                WHERE ajena.id_municipio <> x.id_municipio);

DO $$
DECLARE
    v_quedan INTEGER;
BEGIN
    WITH refs AS (
        SELECT x.id_municipio, x.destino_automatico_jsonb->>'tipo' AS tipo,
               (x.destino_automatico_jsonb->>'id')::int AS id_ref
          FROM tipo_tramite_transicion x
         WHERE x.destino_automatico_jsonb ? 'id'
        UNION ALL
        SELECT x.id_municipio, 'subarea', s.v::int
          FROM tipo_tramite_transicion x,
               jsonb_array_elements_text(COALESCE(x.quien_puede_jsonb->'subareas', '[]'::jsonb)) s(v)
        UNION ALL
        SELECT x.id_municipio, 'equipo', s.v::int
          FROM tipo_tramite_transicion x,
               jsonb_array_elements_text(COALESCE(x.quien_puede_jsonb->'equipos', '[]'::jsonb)) s(v)
        UNION ALL
        SELECT x.id_municipio, 'agente', s.v::int
          FROM tipo_tramite_transicion x,
               jsonb_array_elements_text(COALESCE(x.quien_puede_jsonb->'agentes', '[]'::jsonb)) s(v)
    )
    SELECT count(*) INTO v_quedan
      FROM refs r
     WHERE (r.tipo = 'subarea' AND (SELECT id_municipio FROM subarea WHERE id_subarea = r.id_ref) <> r.id_municipio)
        OR (r.tipo = 'equipo'  AND (SELECT id_municipio FROM equipos WHERE id_equipo  = r.id_ref) <> r.id_municipio)
        OR (r.tipo = 'agente'  AND (SELECT id_municipio FROM agentes WHERE id_agente  = r.id_ref) <> r.id_municipio);
    IF v_quedan > 0 THEN
        RAISE EXCEPTION 'Mig 134: quedan % referencias a otro municipio', v_quedan;
    END IF;
END $$;
