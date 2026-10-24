-- Migración 125b — IT-01 F1: clasificación de tablas y backfill de id_municipio (solo datos)
-- Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, Tarea 1. Requiere la 125.
--
-- Todo lo existente es del municipio 1 (San Andrés en prod), incluidos los usuarios con 377
-- (municipio inexistente, venía del DEFAULT 377 de usuarios.id_municipio). Re-aplicable y sin DROP.
-- El backfill apaga y vuelve a prender los triggers de UPDATE de cada tabla: los de solo-agregar
-- (emergencia_log, historia_clinica_acceso) lanzan una excepción ante cualquier UPDATE, y los de
-- fecha de modificación cambiarían datos que el backfill no debe tocar.

-- 1. Aserción: si aparece un municipio distinto de 1 o 377, la migración no sabe a quién asignarlo.
DO $$
DECLARE
    r RECORD;
    v_n BIGINT;
BEGIN
    FOR r IN
        SELECT c.table_name
          FROM information_schema.columns c
          JOIN information_schema.tables t
            ON t.table_schema = c.table_schema AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE'
         WHERE c.table_schema = 'public' AND c.column_name = 'id_municipio'
           AND c.table_name NOT LIKE '\_backup%'
           AND c.table_name NOT IN ('municipios', 'numerador_municipio')
    LOOP
        EXECUTE format('SELECT count(*) FROM %I WHERE id_municipio IS NOT NULL AND id_municipio NOT IN (1, 377)',
                       r.table_name) INTO v_n;
        IF v_n > 0 THEN
            RAISE EXCEPTION 'Mig 125b: % filas de % con un municipio distinto de 1/377', v_n, r.table_name;
        END IF;
    END LOOP;
END $$;

-- 2. Clasificación (PLAN_MULTI_MUNICIPIO_F1_F2.md, «Clasificación de tablas»).
INSERT INTO municipio_tabla_clase (tabla, clase, nota) VALUES
    -- global
    ('actividades', 'global', NULL), ('nacionalidades', 'global', NULL),
    ('tipo_representacion', 'global', NULL), ('tipos_representacion', 'global', NULL),
    ('tipos_activo', 'global', NULL), ('provincias', 'global', 'con codigo_pais'),
    ('partidos', 'global', NULL), ('localidades', 'global', NULL),
    ('estado_reclamo', 'global', NULL), ('estado_ot', 'global', NULL),
    ('estado_evento', 'global', NULL), ('estado_reserva', 'global', NULL),
    ('emergencia_estado', 'global', NULL), ('tipo_usuario', 'global', NULL),
    ('modulos', 'global', 'la habilitación por municipio llega en F4 (municipio_modulo)'),
    ('municipios', 'global', NULL), ('tipo_documento', 'global', NULL),
    ('municipio_tabla_clase', 'global', NULL),
    -- catálogo del municipio (se copia del municipio modelo en F4)
    ('area', 'catalogo', NULL), ('subarea', 'catalogo', NULL), ('cargos', 'catalogo', NULL),
    ('tipo_reclamo', 'catalogo', NULL), ('tipo_prestacion', 'catalogo', NULL),
    ('tipo_tramite', 'catalogo', NULL), ('tipo_tramite_version', 'catalogo', NULL),
    ('tipo_tramite_campo', 'catalogo', NULL), ('tipo_tramite_estado', 'catalogo', NULL),
    ('tipo_tramite_transicion', 'catalogo', NULL), ('tipo_tramite_documento_requerido', 'catalogo', NULL),
    ('tipo_tramite_aprobacion_requerida', 'catalogo', NULL),
    ('emergencia_tipo', 'catalogo', NULL), ('emergencia_subtipo', 'catalogo', NULL),
    ('emergencia_organismo_derivacion', 'catalogo', NULL), ('emergencia_canal_ingreso', 'catalogo', NULL),
    ('emergencia_prioridad', 'catalogo', NULL), ('servicios', 'catalogo', NULL),
    ('lugares_atencion', 'catalogo', NULL), ('espacios_agenda', 'catalogo', NULL),
    ('agenda_clase', 'catalogo', NULL), ('agenda_feriado', 'catalogo', 'los nacionales se copian en cada alta'),
    ('encuesta_plantilla', 'catalogo', NULL), ('encuesta_pregunta', 'catalogo', NULL),
    ('encuesta_opcion', 'catalogo', NULL), ('equipos', 'catalogo', NULL),
    -- operativo
    ('agentes', 'operativo', NULL), ('usuarios', 'operativo', 'el super administrador (F3) tendrá NULL'),
    ('usuario_modulos', 'operativo', NULL), ('usuario_login_log', 'operativo', NULL),
    ('usuario_push_subscription', 'operativo', NULL), ('ciudadanos', 'operativo', NULL),
    ('ciudadano_credencial', 'operativo', NULL), ('ciudadano_canal_preferido', 'operativo', NULL),
    ('ciudadano_push_subscription', 'operativo', NULL), ('ciudadano_aviso', 'operativo', NULL),
    ('ciudadano_empresa', 'operativo', NULL), ('empresas', 'operativo', NULL),
    ('empresa_credencial', 'operativo', NULL), ('activos', 'operativo', NULL),
    ('reclamos', 'operativo', NULL), ('reclamo_historial', 'operativo', NULL),
    ('reclamo_adjuntos', 'operativo', NULL), ('ordenes_trabajo', 'operativo', NULL),
    ('ot_adjuntos', 'operativo', NULL), ('emergencia_evento', 'operativo', NULL),
    ('emergencia_log', 'operativo', 'solo agregar'), ('emergencia_contacto_eventual', 'operativo', NULL),
    ('emergencia_atencion', 'operativo', NULL), ('turnos', 'operativo', NULL),
    ('turno_atencion', 'operativo', NULL), ('turno_llamado', 'operativo', NULL),
    ('historia_clinica_acceso', 'operativo', 'solo agregar'), ('eventos', 'operativo', NULL),
    ('evento_reservas', 'operativo', NULL), ('evento_encargados', 'operativo', NULL),
    ('ocupaciones', 'operativo', NULL), ('espacio_agentes', 'operativo', NULL),
    ('disponibilidad_recurso', 'operativo', NULL), ('agente_novedad', 'operativo', NULL),
    ('ausencias_agente', 'operativo', NULL), ('conflictos_log', 'operativo', NULL),
    ('agenda_audit_log', 'operativo', NULL), ('equipo_agentes', 'operativo', NULL),
    ('tramite', 'operativo', NULL), ('tramite_movimiento', 'operativo', NULL),
    ('tramite_documento', 'operativo', NULL), ('tramite_firma', 'operativo', NULL),
    ('tramite_relacion', 'operativo', NULL), ('tramite_aprobacion', 'operativo', NULL),
    ('tipo_tramite_numerador', 'operativo', NULL), ('encuesta_envio', 'operativo', NULL),
    ('encuesta_respuesta', 'operativo', NULL), ('encuesta_respuesta_detalle', 'operativo', NULL),
    ('notificacion', 'operativo', NULL), ('numerador_municipio', 'operativo', NULL),
    -- mixta
    ('configuracion_general', 'mixta', 'NULL = parámetro global; la fila del municipio lo sobrescribe'),
    -- legado (sin uso; se borran en el lote de limpieza)
    ('reclamos_area', 'legado', 'sin referencias en backend/app'),
    ('reclamos_subarea', 'legado', 'sin referencias en backend/app'),
    ('reclamos_tipo', 'legado', 'sin referencias en backend/app'),
    ('emergencia_numerador', 'legado', 'reemplazada por numerador_municipio (mig 125c)'),
    ('equipo_usuarios', 'legado', 'solo existe en local; reemplazada por equipo_agentes')
ON CONFLICT (tabla) DO UPDATE
    SET clase = EXCLUDED.clase, nota = EXCLUDED.nota, fecha_modificacion = NOW();

-- 3. Municipios: el 1 atiende las direcciones sin prefijo; el 2 es una prueba sin datos (baja lógica).
UPDATE municipios
   SET subdominio = 'sanandres', direccion_base = TRUE, codigo_pais = 'AR', fecha_modificacion = NOW()
 WHERE id_municipio = 1
   AND (subdominio IS DISTINCT FROM 'sanandres' OR NOT direccion_base OR codigo_pais IS DISTINCT FROM 'AR');
UPDATE municipios
   SET codigo_pais = CASE WHEN pais ILIKE 'venezuela%' THEN 'VE' ELSE 'AR' END, fecha_modificacion = NOW()
 WHERE codigo_pais IS NULL;
UPDATE municipios SET activo = FALSE, fecha_modificacion = NOW() WHERE id_municipio = 2 AND activo;

-- 4. Tipos de documento de Argentina (los que valida hoy el backend).
INSERT INTO tipo_documento (codigo_pais, codigo, nombre, aplica_a) VALUES
    ('AR', 'DNI', 'Documento Nacional de Identidad', 'persona'),
    ('AR', 'PASAPORTE', 'Pasaporte', 'persona'),
    ('AR', 'CUIL', 'Código Único de Identificación Laboral', 'persona'),
    ('AR', 'CUIT', 'Clave Única de Identificación Tributaria', 'empresa')
ON CONFLICT (codigo_pais, codigo) DO NOTHING;

-- 5. Backfill: toda fila de una tabla catalogo/operativo pasa al municipio 1.
DO $$
DECLARE
    r RECORD;
    tg RECORD;
    v_triggers TEXT[];
BEGIN
    FOR r IN
        SELECT m.tabla
          FROM municipio_tabla_clase m
         WHERE m.clase IN ('catalogo', 'operativo')
           AND to_regclass('public.' || quote_ident(m.tabla)) IS NOT NULL
         ORDER BY m.tabla
    LOOP
        -- Triggers de UPDATE habilitados de la tabla (tgtype bit 16 = UPDATE).
        SELECT coalesce(array_agg(t.tgname::text), '{}') INTO v_triggers
          FROM pg_trigger t
         WHERE t.tgrelid = ('public.' || quote_ident(r.tabla))::regclass
           AND NOT t.tgisinternal AND t.tgenabled = 'O' AND (t.tgtype & 16) <> 0;
        FOR tg IN SELECT unnest(v_triggers) AS nombre LOOP
            EXECUTE format('ALTER TABLE %I DISABLE TRIGGER %I', r.tabla, tg.nombre);
        END LOOP;

        EXECUTE format('UPDATE %I SET id_municipio = 1 WHERE id_municipio IS DISTINCT FROM 1', r.tabla);

        FOR tg IN SELECT unnest(v_triggers) AS nombre LOOP
            EXECUTE format('ALTER TABLE %I ENABLE TRIGGER %I', r.tabla, tg.nombre);
        END LOOP;
    END LOOP;
END $$;

-- 6. Configuración: las claves VAPID son globales (una sola app para todos); el resto, del municipio 1.
--    password_renovacion_dias queda en el municipio 1 hasta F3 (si fuera global, nadie podría editarla).
UPDATE configuracion_general SET id_municipio = 1
 WHERE id_municipio IS NULL AND clave NOT LIKE 'vapid\_%';

-- 7. Numeradores del municipio 1: siguen desde el último número emitido de cada año.
INSERT INTO numerador_municipio (id_municipio, entidad, anio, ultimo_numero)
SELECT 1, 'reclamo', substring(nro_reclamo FROM 5 FOR 4)::int, max(substring(nro_reclamo FROM 10)::int)
  FROM reclamos
 WHERE nro_reclamo ~ '^REC-[0-9]{4}-[0-9]+$'
 GROUP BY 3
ON CONFLICT (id_municipio, entidad, anio) DO UPDATE
    SET ultimo_numero = GREATEST(numerador_municipio.ultimo_numero, EXCLUDED.ultimo_numero);

INSERT INTO numerador_municipio (id_municipio, entidad, anio, ultimo_numero)
SELECT 1, 'ot', substring(nro_ot FROM 4 FOR 4)::int, max(substring(nro_ot FROM 9)::int)
  FROM ordenes_trabajo
 WHERE nro_ot ~ '^OT-[0-9]{4}-[0-9]+$'
 GROUP BY 3
ON CONFLICT (id_municipio, entidad, anio) DO UPDATE
    SET ultimo_numero = GREATEST(numerador_municipio.ultimo_numero, EXCLUDED.ultimo_numero);

INSERT INTO numerador_municipio (id_municipio, entidad, anio, ultimo_numero)
SELECT 1, 'emergencia', anio, ultimo_numero
  FROM emergencia_numerador
ON CONFLICT (id_municipio, entidad, anio) DO UPDATE
    SET ultimo_numero = GREATEST(numerador_municipio.ultimo_numero, EXCLUDED.ultimo_numero);
