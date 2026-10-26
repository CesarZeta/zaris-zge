-- Migración 129b — IT-01, lote de limpieza (borrado).
-- Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, «Lote de limpieza».
--
-- LLEVA DROP: el MCP (apply_migration) la rechaza. En prod la corre César en el SQL Editor de
-- Supabase; en local, por psql. Va DESPUÉS de la 129 y del deploy del código que deja de usar
-- lo que se borra (modelos sin los únicos viejos ni el id_municipio de las tablas globales).
-- Re-aplicable (todo con IF EXISTS). Una sola transacción: si algo falla, no cambia nada.

BEGIN;

-- 1. Únicos globales viejos: los reemplazan los únicos por municipio de la 125c (uqmun_*) y,
--    para el username de los super administradores, el de la 129. Constraint e índice por las
--    dudas: en local alguno quedó como índice suelto o no existe.
ALTER TABLE ciudadanos DROP CONSTRAINT IF EXISTS uq_ciudadano_doc;
DROP INDEX IF EXISTS uq_ciudadano_doc;
ALTER TABLE ciudadanos DROP CONSTRAINT IF EXISTS uq_ciudadano_cuil;
DROP INDEX IF EXISTS uq_ciudadano_cuil;
ALTER TABLE empresas DROP CONSTRAINT IF EXISTS uq_empresa_cuit;
DROP INDEX IF EXISTS uq_empresa_cuit;
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_username_key;
DROP INDEX IF EXISTS usuarios_username_key;
ALTER TABLE reclamos DROP CONSTRAINT IF EXISTS reclamos_nro_reclamo_key;
DROP INDEX IF EXISTS reclamos_nro_reclamo_key;
ALTER TABLE ordenes_trabajo DROP CONSTRAINT IF EXISTS ordenes_trabajo_nro_ot_key;
DROP INDEX IF EXISTS ordenes_trabajo_nro_ot_key;
ALTER TABLE emergencia_evento DROP CONSTRAINT IF EXISTS emergencia_evento_numero_operativo_key;
DROP INDEX IF EXISTS emergencia_evento_numero_operativo_key;
ALTER TABLE activos DROP CONSTRAINT IF EXISTS activos_codigo_unico_key;
DROP INDEX IF EXISTS activos_codigo_unico_key;
ALTER TABLE agenda_feriado DROP CONSTRAINT IF EXISTS agenda_feriado_fecha_key;
DROP INDEX IF EXISTS agenda_feriado_fecha_key;
ALTER TABLE emergencia_canal_ingreso DROP CONSTRAINT IF EXISTS emergencia_canal_ingreso_codigo_key;
DROP INDEX IF EXISTS emergencia_canal_ingreso_codigo_key;
ALTER TABLE emergencia_prioridad DROP CONSTRAINT IF EXISTS emergencia_prioridad_codigo_key;
DROP INDEX IF EXISTS emergencia_prioridad_codigo_key;
ALTER TABLE emergencia_organismo_derivacion DROP CONSTRAINT IF EXISTS emergencia_organismo_derivacion_codigo_key;
DROP INDEX IF EXISTS emergencia_organismo_derivacion_codigo_key;
ALTER TABLE configuracion_general DROP CONSTRAINT IF EXISTS configuracion_general_clave_key;
DROP INDEX IF EXISTS configuracion_general_clave_key;

-- 2. Tablas legado (municipio_tabla_clase): el catálogo viejo de reclamos (hoy area/subarea/
--    tipo_reclamo), el numerador anual de Emergencias (hoy numerador_municipio, 125c) y
--    equipo_usuarios (solo en local; hoy equipo_agentes). Sin CASCADE: si algo más dependiera
--    de ellas, la transacción falla entera.
DROP TABLE IF EXISTS reclamos_tipo;
DROP TABLE IF EXISTS reclamos_subarea;
DROP TABLE IF EXISTS reclamos_area;
DROP TABLE IF EXISTS emergencia_numerador;
DROP TABLE IF EXISTS equipo_usuarios;
DELETE FROM municipio_tabla_clase WHERE clase = 'legado';

-- 3. id_municipio de las tablas globales: sin uso desde F1 (son de todos los municipios). Se van
--    con la columna su FK a municipios y sus índices.
ALTER TABLE actividades DROP COLUMN IF EXISTS id_municipio;
ALTER TABLE emergencia_estado DROP COLUMN IF EXISTS id_municipio;
ALTER TABLE estado_evento DROP COLUMN IF EXISTS id_municipio;
ALTER TABLE estado_ot DROP COLUMN IF EXISTS id_municipio;
ALTER TABLE estado_reclamo DROP COLUMN IF EXISTS id_municipio;
ALTER TABLE estado_reserva DROP COLUMN IF EXISTS id_municipio;
ALTER TABLE modulos DROP COLUMN IF EXISTS id_municipio;
ALTER TABLE nacionalidades DROP COLUMN IF EXISTS id_municipio;
ALTER TABLE tipo_representacion DROP COLUMN IF EXISTS id_municipio;
ALTER TABLE tipo_usuario DROP COLUMN IF EXISTS id_municipio;

COMMIT;

-- Verificación: las tres columnas tienen que dar 0.
SELECT
  (SELECT count(*) FROM pg_class WHERE relname IN ('uq_ciudadano_doc', 'uq_ciudadano_cuil',
      'uq_empresa_cuit', 'usuarios_username_key', 'reclamos_nro_reclamo_key', 'ordenes_trabajo_nro_ot_key',
      'emergencia_evento_numero_operativo_key', 'activos_codigo_unico_key', 'agenda_feriado_fecha_key',
      'emergencia_canal_ingreso_codigo_key', 'emergencia_prioridad_codigo_key',
      'emergencia_organismo_derivacion_codigo_key', 'configuracion_general_clave_key')) AS unicos_viejos,
  (SELECT count(*) FROM pg_class WHERE relkind = 'r' AND relname IN ('reclamos_tipo', 'reclamos_subarea',
      'reclamos_area', 'emergencia_numerador', 'equipo_usuarios')) AS tablas_legado,
  (SELECT count(*) FROM information_schema.columns c JOIN municipio_tabla_clase m ON m.tabla = c.table_name
    WHERE c.table_schema = 'public' AND c.column_name = 'id_municipio' AND m.clase = 'global'
      AND c.table_name <> 'municipios') AS globales_con_id_municipio;
