-- ============================================================================
-- 107b: Historia clinica (proyecto ATENCION, F5) — clave de config id_area_salud.
--       Seed separado del DDL de la 107 (§21: apply_migration es atomico).
--       Todo se resuelve POR NOMBRE normalizado (translate de tildes), nunca por
--       id: el area de Salud es la 57 en prod y la 56 en local (§24, drift de ids).
--       Solo cuenta el area ACTIVA "Secretaria de Salud": las homonimas INACTIVAS
--       (1 "Salud", 7, 33) quedan afuera a proposito. El guard de
--       GET /turnos/atenciones/historia autoriza a nivel 1 y a los agentes cuya
--       subarea activa cuelga de esta area (agentes.id_subarea, regla 1:1 §39).
-- Idempotente: UPSERT por clave (UNIQUE configuracion_general_clave_key).
-- ============================================================================

-- 1. Clave de config: que area es la gestion Salud -----------------------------
-- activo y tipo EXPLICITOS: en prod son NOT NULL sin default (§21).
INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
SELECT 'id_area_salud', a.id_area::text, 'integer',
       'Area (area.id_area) que actua como gestion Salud: habilita la historia clinica a sus agentes activos (niveles 2-4) ademas de nivel 1 (mig 107b, F5).',
       TRUE
  FROM area a
 WHERE a.activo = TRUE
   AND translate(lower(a.nombre), 'áéíóú', 'aeiou') = 'secretaria de salud'
 ORDER BY a.id_area
 LIMIT 1
-- Re-aplicar NO pisa un valor que el admin haya cambiado desde Config -> Sistema:
-- solo garantiza que la clave exista y este activa.
ON CONFLICT (clave) DO UPDATE
   SET activo = TRUE, fecha_modificacion = NOW();
