-- Migración 136 — Encuestas: todas las ramas en los cuatro circuitos.
-- Textos aprobados por César el 2026-11-03 (PLAN_MULTI_MUNICIPIO_F4_F5.md → «Encuestas: textos aprobados»).
-- Turnos no tenía preguntas para los neutrales; trámites y entradas no tenían ninguna rama, así que el
-- insatisfecho no podía pedir contacto. Los cuatro circuitos usan los MISMOS VALORES de respuesta que
-- reclamos para que los resultados se integren; solo cambia el texto visible.
--
-- Solo datos. Agrega lo que falta y no toca lo ya respondido: las respuestas apuntan al id de la pregunta,
-- y el único UPDATE corre el sí/no de turnos del orden 3 al 4 (las ramas van después de «tiempo de espera»).
-- Reclamos no cambia: es la referencia.
-- Corre sobre el modelo y San Andrés (el de direccion_base), como se aprobó: en prod son los únicos con
-- plantillas, y el alta copia del modelo, así que los municipios nuevos ya nacen completos. Los municipios de
-- prueba de local no se tocan (algunos smokes les dejan plantillas recortadas a propósito).
-- Re-aplicable. Falla si el resultado no da.

DO $$
DECLARE
  v_pl     RECORD;
  v_q      RECORD;
  v_o      RECORD;
  v_id_q   INTEGER;
  v_preg   INTEGER;
  v_opc    INTEGER;
BEGIN
  CREATE TEMP TABLE _m136_pregunta (
    tipo_plantilla TEXT, rama TEXT, tipo TEXT, orden INT, texto TEXT, grupo TEXT
  ) ON COMMIT DROP;

  INSERT INTO _m136_pregunta VALUES
    ('turnos',   'satisfechos',   'multiple', 3, '¿Qué aspecto destacarías de la atención recibida?',      'positivas'),
    ('turnos',   'neutrales',     'multiple', 3, '¿Qué faltó para que tu experiencia fuera mejor?',        'neutra'),
    ('turnos',   'neutrales',     'multiple', 4, '¿La atención fue lo que esperabas?',                     'expectativa'),
    ('turnos',   'insatisfechos', 'multiple', 3, '¿Cuál fue el principal problema?',                       'negativas'),

    ('tramites', 'satisfechos',   'multiple', 2, '¿Qué aspecto destacarías de la gestión?',                'positivas'),
    ('tramites', 'satisfechos',   'si_no',    3, '¿Recomendarías hacer este trámite por este canal?',      NULL),
    ('tramites', 'neutrales',     'multiple', 2, '¿Qué faltó para que tu experiencia fuera mejor?',        'neutra'),
    ('tramites', 'neutrales',     'multiple', 3, '¿El resultado del trámite fue lo que esperabas?',        'expectativa'),
    ('tramites', 'insatisfechos', 'multiple', 2, '¿Cuál fue el principal problema?',                       'negativas'),
    ('tramites', 'insatisfechos', 'si_no',    3, '¿Querés que un responsable del municipio te contacte?',  NULL),

    ('entradas', 'satisfechos',   'multiple', 2, '¿Qué aspecto destacarías del evento?',                   'positivas'),
    ('entradas', 'satisfechos',   'si_no',    3, '¿Recomendarías estos eventos a otros vecinos?',          NULL),
    ('entradas', 'neutrales',     'multiple', 2, '¿Qué faltó para que tu experiencia fuera mejor?',        'neutra'),
    ('entradas', 'neutrales',     'multiple', 3, '¿El evento fue lo que esperabas?',                       'expectativa'),
    ('entradas', 'insatisfechos', 'multiple', 2, '¿Cuál fue el principal problema?',                       'negativas'),
    ('entradas', 'insatisfechos', 'si_no',    3, '¿Querés que un responsable del municipio te contacte?',  NULL);

  -- Opciones: mismos valores y mismo orden que reclamos. Las que cambian de texto, por circuito.
  CREATE TEMP TABLE _m136_opcion (
    grupo TEXT, orden INT, valor TEXT, turnos TEXT, tramites TEXT, entradas TEXT
  ) ON COMMIT DROP;

  INSERT INTO _m136_opcion VALUES
    ('positivas',   1, 'rapidez',             'Rapidez',                    'Rapidez',                    'Rapidez'),
    ('positivas',   2, 'claridad',            'Claridad en la información', 'Claridad en la información', 'Claridad en la información'),
    ('positivas',   3, 'trato',               'Trato del personal',         'Trato del personal',         'Trato del personal'),
    ('positivas',   4, 'calidad',             'Calidad de la atención',     'Calidad de la gestión',      'Calidad del evento'),
    ('positivas',   5, 'otro',                'Otro',                       'Otro',                       'Otro'),

    ('neutra',      1, 'mas_rapidez',         'Más rapidez',                'Más rapidez',                'Más rapidez'),
    ('neutra',      2, 'mas_informacion',     'Más información',            'Más información',            'Más información'),
    ('neutra',      3, 'mejor_comunicacion',  'Mejor comunicación',         'Mejor comunicación',         'Mejor comunicación'),
    ('neutra',      4, 'mejor_solucion',      'Mejor respuesta',            'Mejor resolución',           'Mejor organización'),
    ('neutra',      5, 'otro',                'Otro',                       'Otro',                       'Otro'),

    ('expectativa', 1, 'si',                  'Sí',                         'Sí',                         'Sí'),
    ('expectativa', 2, 'parcialmente',        'Parcialmente',               'Parcialmente',               'Parcialmente'),
    ('expectativa', 3, 'no',                  'No',                         'No',                         'No'),

    ('negativas',   1, 'demora',              'Demora excesiva',            'Demora excesiva',            'Demora en el ingreso'),
    ('negativas',   2, 'no_resuelto',         'No resolvieron mi consulta', 'No resolvieron mi trámite',  'No fue lo que se anunció'),
    ('negativas',   3, 'mala_comunicacion',   'Mala comunicación',          'Mala comunicación',          'Mala comunicación'),
    ('negativas',   4, 'mal_trato',           'Mal trato',                  'Mal trato',                  'Mal trato'),
    ('negativas',   5, 'solucion_incorrecta', 'Respuesta incorrecta',       'Resolución incorrecta',      'Mala organización'),
    ('negativas',   6, 'otro',                'Otro',                       'Otro',                       'Otro');

  -- Turnos: el sí/no pasa después de la múltiple nueva de su rama.
  UPDATE encuesta_pregunta q
     SET orden = 4, fecha_modificacion = NOW()
    FROM encuesta_plantilla p
    JOIN municipios m ON m.id_municipio = p.id_municipio
   WHERE p.id_encuesta_plantilla = q.id_plantilla
     AND (m.direccion_base OR m.estado = 'modelo')
     AND p.tipo = 'turnos'
     AND q.tipo = 'si_no'
     AND q.rama IN ('satisfechos', 'insatisfechos')
     AND q.orden = 3;

  FOR v_pl IN
    SELECT p.id_encuesta_plantilla, p.tipo, p.id_municipio
      FROM encuesta_plantilla p
      JOIN municipios m ON m.id_municipio = p.id_municipio
     WHERE (m.direccion_base OR m.estado = 'modelo')
       AND p.tipo IN ('turnos', 'tramites', 'entradas')
  LOOP
    FOR v_q IN SELECT * FROM _m136_pregunta WHERE tipo_plantilla = v_pl.tipo LOOP
      SELECT id_encuesta_pregunta INTO v_id_q
        FROM encuesta_pregunta
       WHERE id_plantilla = v_pl.id_encuesta_plantilla
         AND rama = v_q.rama AND texto = v_q.texto
       LIMIT 1;

      IF v_id_q IS NULL THEN
        INSERT INTO encuesta_pregunta (id_plantilla, texto, tipo, orden, rama, obligatoria, activo, id_municipio)
        VALUES (v_pl.id_encuesta_plantilla, v_q.texto, v_q.tipo, v_q.orden, v_q.rama, TRUE, TRUE, v_pl.id_municipio)
        RETURNING id_encuesta_pregunta INTO v_id_q;
      END IF;

      IF v_q.grupo IS NOT NULL THEN
        FOR v_o IN SELECT * FROM _m136_opcion WHERE grupo = v_q.grupo ORDER BY orden LOOP
          IF NOT EXISTS (SELECT 1 FROM encuesta_opcion WHERE id_pregunta = v_id_q AND valor = v_o.valor) THEN
            INSERT INTO encuesta_opcion (id_pregunta, texto, valor, orden, activo, id_municipio)
            VALUES (
              v_id_q,
              CASE v_pl.tipo WHEN 'turnos' THEN v_o.turnos WHEN 'tramites' THEN v_o.tramites ELSE v_o.entradas END,
              v_o.valor, v_o.orden, TRUE, v_pl.id_municipio
            );
          END IF;
        END LOOP;
      END IF;
    END LOOP;

    -- Verificación por plantilla: turnos suma «tiempo de espera» (9), los otros dos 8; opciones, las 19 de reclamos.
    SELECT count(*) INTO v_preg
      FROM encuesta_pregunta
     WHERE id_plantilla = v_pl.id_encuesta_plantilla AND activo = TRUE;
    SELECT count(*) INTO v_opc
      FROM encuesta_opcion o
      JOIN encuesta_pregunta q ON q.id_encuesta_pregunta = o.id_pregunta
     WHERE q.id_plantilla = v_pl.id_encuesta_plantilla AND o.activo = TRUE;

    IF v_preg <> (CASE v_pl.tipo WHEN 'turnos' THEN 9 ELSE 8 END) OR v_opc <> 19 THEN
      RAISE EXCEPTION 'Migración 136: plantilla % (%) quedó con % preguntas y % opciones',
        v_pl.id_encuesta_plantilla, v_pl.tipo, v_preg, v_opc;
    END IF;
  END LOOP;
END $$;
