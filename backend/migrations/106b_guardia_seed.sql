-- ============================================================================
-- 106b: Seed de la Guardia (proyecto ATENCION, F4). Separado del DDL (106)
--       porque apply_migration es atomico y un INSERT que falla revertiria
--       tambien los CREATE (§21).
--
-- Decision de Cesar (2026-09-06): "la Guardia debe estar en el area de Salud,
-- de Emergencias" => subarea "Emergencias" bajo el area ACTIVA "Secretaria de
-- Salud" + espacio "Guardia" en esa subarea + clave de config que lo senala.
--
-- Todo se resuelve POR NOMBRE normalizado (translate de tildes), nunca por id:
-- el area de Salud es la 57 en prod y la 56 en local (§24, drift de ids).
-- Idempotente: cada INSERT chequea NOT EXISTS; la clave hace UPSERT.
-- ============================================================================

-- 1. Subarea "Emergencias" bajo Secretaria de Salud --------------------------
INSERT INTO subarea (nombre, descripcion, id_area, activo, id_municipio)
SELECT 'Emergencias',
       'Guardia de emergencias de Salud: recibe las derivaciones del COM (proyecto Atencion F4, mig 106).',
       a.id_area, TRUE, 1
  FROM area a
 WHERE a.activo = TRUE
   AND translate(lower(a.nombre), 'áéíóú', 'aeiou') = 'secretaria de salud'
   AND NOT EXISTS (
       SELECT 1 FROM subarea s
        WHERE s.id_area = a.id_area
          AND translate(lower(s.nombre), 'áéíóú', 'aeiou') = 'emergencias'
   )
 ORDER BY a.id_area
 LIMIT 1;

-- 2. Espacio "Guardia" en esa subarea ----------------------------------------
-- atendido = TRUE: cuando se vinculen los medicos de guardia (Agenda -> Espacios
-- -> Agentes) la mesa muestra sus columnas. Prefijo GUA por si algun dia la
-- Guardia tambien llama por numero (colero, mig 105).
INSERT INTO espacios_agenda (nombre, descripcion, atendido, id_subarea, prefijo_colero, id_municipio)
SELECT 'Guardia',
       'Guardia de emergencias. Atiende las derivaciones del COM sin turno (mig 106).',
       TRUE, s.id_subarea, 'GUA', 1
  FROM subarea s
  JOIN area a ON a.id_area = s.id_area
 WHERE a.activo = TRUE AND s.activo = TRUE
   AND translate(lower(a.nombre), 'áéíóú', 'aeiou') = 'secretaria de salud'
   AND translate(lower(s.nombre), 'áéíóú', 'aeiou') = 'emergencias'
   AND NOT EXISTS (
       SELECT 1 FROM espacios_agenda e
        WHERE e.activo = TRUE AND lower(e.nombre) = 'guardia'
   )
 ORDER BY s.id_subarea
 LIMIT 1;

-- 3. Clave de config: que espacio actua como Guardia --------------------------
-- activo y tipo EXPLICITOS: en prod son NOT NULL sin default (§21).
INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
SELECT 'id_espacio_guardia', e.id_espacio::text, 'integer',
       'Ubicacion (espacios_agenda.id_espacio) que actua como Guardia de emergencias: recibe las derivaciones del COM (mig 106).',
       TRUE
  FROM espacios_agenda e
 WHERE e.activo = TRUE AND lower(e.nombre) = 'guardia'
 ORDER BY e.id_espacio
 LIMIT 1
ON CONFLICT (clave) DO UPDATE
   SET valor = EXCLUDED.valor, activo = TRUE, fecha_modificacion = NOW();
