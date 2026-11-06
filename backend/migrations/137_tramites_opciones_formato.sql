-- Migración 137 — Trámites: opciones de los campos de selección al formato que espera el validador.
-- Cazado en la prueba de cierre de F4+F5 (2026-11-02): seis campos guardaban {"opciones": ["nativa", …]}
-- y validar_campos_contra_tipo rechaza cualquier valor en esa forma («'no_se' no es una opcion valida»).
-- Cinco son obligatorios: habilitación comercial, cartel, recurso administrativo e inspección bromatológica
-- no se podían iniciar desde la pantalla (los trámites que existen los creó el generador demo).
--
-- Solo datos, en todos los municipios. Pasa a [{"valor": …, "etiqueta": …}], que es lo que produce el
-- builder. Los valores NO cambian: los trámites ya cargados los siguen teniendo en datos_jsonb. La etiqueta
-- es el mismo valor con mayúscula y tildes; un valor que no está en esta lista falla la migración.
-- Re-aplicable: sin filas en el formato viejo no hace nada.

DO $$
DECLARE
  v_sin_etiqueta TEXT;
  v_quedan       INTEGER;
BEGIN
  CREATE TEMP TABLE _m137_etiqueta (valor TEXT PRIMARY KEY, etiqueta TEXT NOT NULL) ON COMMIT DROP;

  INSERT INTO _m137_etiqueta VALUES
    ('gastronomico', 'Gastronómico'), ('comercial', 'Comercial'), ('industrial', 'Industrial'),
    ('servicios', 'Servicios'), ('otro', 'Otro'),
    ('frontal', 'Frontal'), ('marquesina', 'Marquesina'), ('saliente', 'Saliente'), ('luminoso', 'Luminoso'),
    ('resolucion', 'Resolución'), ('disposicion', 'Disposición'), ('decreto', 'Decreto'), ('multa', 'Multa'),
    ('panaderia', 'Panadería'), ('carniceria', 'Carnicería'), ('verduleria', 'Verdulería'),
    ('nativa', 'Nativa'), ('exotica', 'Exótica'), ('no_se', 'No sé');

  SELECT string_agg(DISTINCT e.v, ', ') INTO v_sin_etiqueta
    FROM tipo_tramite_campo c,
         jsonb_array_elements_text(c.opciones_jsonb->'opciones') e(v)
   WHERE jsonb_typeof(c.opciones_jsonb) = 'object'
     AND jsonb_typeof(c.opciones_jsonb->'opciones') = 'array'
     AND NOT EXISTS (SELECT 1 FROM _m137_etiqueta t WHERE t.valor = e.v);
  IF v_sin_etiqueta IS NOT NULL THEN
    RAISE EXCEPTION 'Migración 137: valores sin etiqueta: %', v_sin_etiqueta;
  END IF;

  UPDATE tipo_tramite_campo c
     SET opciones_jsonb = (
           SELECT COALESCE(jsonb_agg(jsonb_build_object('valor', e.v, 'etiqueta', t.etiqueta) ORDER BY e.ord), '[]'::jsonb)
             FROM jsonb_array_elements_text(c.opciones_jsonb->'opciones') WITH ORDINALITY e(v, ord)
             JOIN _m137_etiqueta t ON t.valor = e.v),
         fecha_modificacion = NOW()
   WHERE jsonb_typeof(c.opciones_jsonb) = 'object'
     AND jsonb_typeof(c.opciones_jsonb->'opciones') = 'array';

  SELECT count(*) INTO v_quedan
    FROM tipo_tramite_campo
   WHERE opciones_jsonb IS NOT NULL
     AND jsonb_typeof(opciones_jsonb) NOT IN ('array', 'null');
  IF v_quedan > 0 THEN
    RAISE EXCEPTION 'Migración 137: quedan % campos con un formato que el validador no entiende', v_quedan;
  END IF;
END $$;
