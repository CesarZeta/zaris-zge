-- Migración 130c — IT-01 F4+F5: datos de F4 (países, estado y provincia de cada municipio, áreas
-- fijas, módulos por municipio, grupos de vaciado) y los CHECK que dependen de esos datos.
-- Plan: PLAN_MULTI_MUNICIPIO_F4_F5.md, Tarea 4. Requiere la 130b.
--
-- Sin DROP (va por MCP). Re-aplicable. Falla (y no deja nada) si no encuentra las 6 áreas fijas o
-- si queda un municipio operable sin provincia o una tabla no global sin grupo.

-- 1. Países. AR habilitado para el alta; VE cargado pero no habilitado (próxima etapa, F5b).
INSERT INTO paises (codigo_pais, nombre, etiqueta_nivel_1, etiqueta_nivel_2, zona_horaria, habilitado_para_alta)
VALUES ('AR', 'Argentina', 'Provincia', 'Partido', 'America/Argentina/Buenos_Aires', TRUE),
       ('VE', 'Venezuela', 'Estado', 'Municipio', 'America/Caracas', FALSE)
ON CONFLICT (codigo_pais) DO NOTHING;

-- 2. Estado: los inactivos pasan a baja (recuerdan el estado anterior); el municipio de las
--    direcciones sin prefijo es el demo.
UPDATE municipios SET estado = 'baja' WHERE NOT activo AND estado <> 'baja';
UPDATE municipios SET estado = 'demo' WHERE direccion_base AND estado <> 'demo';

-- 3. Provincia del catálogo a partir del texto libre (mismo país, nombre sin distinguir mayúsculas).
UPDATE municipios m
   SET id_provincia = p.id_provincia
  FROM provincias p
 WHERE m.id_provincia IS NULL AND p.codigo_pais = m.codigo_pais
   AND lower(btrim(p.nombre)) = lower(btrim(m.provincia));

DO $$
DECLARE
    v_sin text;
BEGIN
    SELECT string_agg(id_municipio || ' ' || nombre, ', ') INTO v_sin
      FROM municipios WHERE id_provincia IS NULL AND estado NOT IN ('baja', 'modelo');
    IF v_sin IS NOT NULL THEN
        RAISE EXCEPTION 'Municipios operables sin provincia del catálogo: %', v_sin;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_municipios_provincia') THEN
        ALTER TABLE municipios ADD CONSTRAINT ck_municipios_provincia CHECK
            (id_provincia IS NOT NULL OR estado IN ('baja', 'modelo'));
    END IF;
END $$;

-- 4. Las 6 áreas fijas del municipio base, por nombre. Se compara sin tildes ni mayúsculas y por
--    prefijo, porque los nombres de local difieren de prod («Secretaria de Gobierno y Legal Tecnica»);
--    cada nombre tiene que encontrar exactamente un área activa.
DO $$
DECLARE
    v_nombre text;
    v_ids    int[];
BEGIN
    FOREACH v_nombre IN ARRAY ARRAY[
        'secretaria de gobierno', 'secretaria de planeamiento y obras publicas', 'secretaria de salud',
        'secretaria de seguridad', 'secretaria de servicios publicos', 'subsecretaria de transito']
    LOOP
        SELECT array_agg(a.id_area) INTO v_ids
          FROM area a JOIN municipios m USING (id_municipio)
         WHERE m.direccion_base AND a.activo
           AND lower(translate(btrim(a.nombre), 'ÁÉÍÓÚáéíóú', 'AEIOUaeiou')) LIKE v_nombre || '%';
        IF coalesce(array_length(v_ids, 1), 0) <> 1 THEN
            RAISE EXCEPTION 'Área fija «%»: % coincidencias activas en el municipio base (se espera 1)',
                v_nombre, coalesce(array_length(v_ids, 1), 0);
        END IF;
        UPDATE area SET es_sistema = TRUE WHERE id_area = v_ids[1] AND NOT es_sistema;
    END LOOP;
END $$;

-- 5. Módulos de cada municipio que no está de baja: todos los activos, habilitados, con el nivel
--    del catálogo (San Andrés sigue igual que hoy).
INSERT INTO municipio_modulo (id_municipio, modulo_codigo, habilitado, min_nivel_acceso)
SELECT m.id_municipio, mo.modulo_codigo, TRUE, mo.min_nivel_acceso
  FROM municipios m CROSS JOIN modulos mo
 WHERE m.estado <> 'baja' AND mo.activo
ON CONFLICT (id_municipio, modulo_codigo) DO NOTHING;

-- 6. Grupo de vaciado de cada tabla no global (spec §4.7). Lo que borra un grupo arrastra, por las
--    FK compuestas, lo que lo referencia; `configuracion` no se vacía nunca.
UPDATE municipio_tabla_clase t SET grupo = g.grupo, fecha_modificacion = NOW()
  FROM (VALUES
    -- configuracion
    ('configuracion_general', 'configuracion'), ('numerador_municipio', 'configuracion'),
    ('super_admin_acceso', 'configuracion'), ('municipio_modulo', 'configuracion'),
    ('municipio_tarea', 'configuracion'),
    -- maestros (catálogos del municipio)
    ('agenda_clase', 'maestros'), ('agenda_feriado', 'maestros'), ('area', 'maestros'),
    ('cargos', 'maestros'), ('emergencia_canal_ingreso', 'maestros'),
    ('emergencia_organismo_derivacion', 'maestros'), ('emergencia_prioridad', 'maestros'),
    ('emergencia_subtipo', 'maestros'), ('emergencia_tipo', 'maestros'), ('encuesta_opcion', 'maestros'),
    ('encuesta_plantilla', 'maestros'), ('encuesta_pregunta', 'maestros'), ('equipos', 'maestros'),
    ('espacios_agenda', 'maestros'), ('lugares_atencion', 'maestros'), ('servicios', 'maestros'),
    ('subarea', 'maestros'), ('tipo_prestacion', 'maestros'), ('tipo_reclamo', 'maestros'),
    ('tipo_tramite', 'maestros'), ('tipo_tramite_aprobacion_requerida', 'maestros'),
    ('tipo_tramite_campo', 'maestros'), ('tipo_tramite_documento_requerido', 'maestros'),
    ('tipo_tramite_estado', 'maestros'), ('tipo_tramite_transicion', 'maestros'),
    ('tipo_tramite_version', 'maestros'), ('tipo_tramite_numerador', 'maestros'),
    ('activos', 'maestros'), ('disponibilidad_recurso', 'maestros'),
    -- contactos (BUC y cuentas de la app del vecino)
    ('ciudadanos', 'contactos'), ('empresas', 'contactos'), ('ciudadano_empresa', 'contactos'),
    ('ciudadano_credencial', 'contactos'), ('ciudadano_canal_preferido', 'contactos'),
    ('ciudadano_push_subscription', 'contactos'), ('empresa_credencial', 'contactos'),
    -- usuarios (cuentas internas y agentes)
    ('usuarios', 'usuarios'), ('usuario_modulos', 'usuarios'), ('usuario_login_log', 'usuarios'),
    ('usuario_push_subscription', 'usuarios'), ('usuario_segundo_factor', 'usuarios'),
    ('usuario_codigo_emergencia', 'usuarios'), ('usuario_segundo_factor_evento', 'usuarios'),
    ('usuario_invitacion', 'usuarios'), ('agentes', 'usuarios'), ('equipo_agentes', 'usuarios'),
    ('espacio_agentes', 'usuarios'),
    -- operativo
    ('agenda_audit_log', 'operativo'), ('agente_novedad', 'operativo'), ('ausencias_agente', 'operativo'),
    ('ciudadano_aviso', 'operativo'), ('conflictos_log', 'operativo'), ('emergencia_atencion', 'operativo'),
    ('emergencia_contacto_eventual', 'operativo'), ('emergencia_evento', 'operativo'),
    ('emergencia_log', 'operativo'), ('encuesta_envio', 'operativo'), ('encuesta_respuesta', 'operativo'),
    ('encuesta_respuesta_detalle', 'operativo'), ('evento_encargados', 'operativo'),
    ('evento_reservas', 'operativo'), ('eventos', 'operativo'), ('historia_clinica_acceso', 'operativo'),
    ('notificacion', 'operativo'), ('ocupaciones', 'operativo'), ('ordenes_trabajo', 'operativo'),
    ('ot_adjuntos', 'operativo'), ('reclamo_adjuntos', 'operativo'), ('reclamo_historial', 'operativo'),
    ('reclamos', 'operativo'), ('tramite', 'operativo'), ('tramite_aprobacion', 'operativo'),
    ('tramite_documento', 'operativo'), ('tramite_firma', 'operativo'), ('tramite_movimiento', 'operativo'),
    ('tramite_relacion', 'operativo'), ('turno_atencion', 'operativo'), ('turno_llamado', 'operativo'),
    ('turnos', 'operativo')
  ) AS g (tabla, grupo)
 WHERE t.tabla = g.tabla AND t.clase <> 'global' AND t.grupo IS DISTINCT FROM g.grupo;

-- Falla si una tabla no global quedó sin grupo (la lista de arriba tiene que cubrirlas todas).
ALTER TABLE municipio_tabla_clase VALIDATE CONSTRAINT ck_municipio_tabla_clase_grupo_requerido;

-- 7. Defaults de catálogos globales por municipio (guía de arranque R9/R10): nacionalidad del país del
--    municipio y tipo de representación «Representante Legal», resueltos por nombre. No pisa un valor
--    ya cargado.
INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
SELECT 'id_nacionalidad_defecto', COALESCE((SELECT n.id::text FROM nacionalidades n JOIN paises p ON p.codigo_pais = m.codigo_pais
                                              WHERE n.pais ILIKE p.nombre ORDER BY n.id LIMIT 1), ''),
       'integer', 'Nacionalidad por defecto de las fichas que se crean sin ese dato', TRUE, m.id_municipio
  FROM municipios m WHERE m.estado <> 'baja'
ON CONFLICT (id_municipio, clave) DO NOTHING;
INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
SELECT 'id_tipo_representacion_defecto',
       COALESCE((SELECT id::text FROM tipo_representacion WHERE tipo = 'Representante Legal' ORDER BY id LIMIT 1), ''),
       'integer', 'Tipo de representación por defecto al vincular una empresa', TRUE, m.id_municipio
  FROM municipios m WHERE m.estado <> 'baja'
ON CONFLICT (id_municipio, clave) DO NOTHING;
