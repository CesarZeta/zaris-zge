-- Migracion 81 - Modulo Emergencias, Fase 1: estructura organizacional
-- Crea las subareas "Policía Municipal" y "Defensa Civil" bajo el area
-- "Secretaria de Seguridad" ACTIVA de cada entorno.
--
-- Contexto (verificado 2026-06-10): el area existe DUPLICADA en ambos entornos
-- (id 8 sin tilde / id 28 con tilde) con drift invertido de `activo`
-- (prod: activa la 28; local: activa la 8). Por eso el area padre se resuelve
-- por nombre NORMALIZADO (sin tildes) + activo=TRUE, nunca por id hardcodeado.
-- Las duplicadas inactivas NO se tocan en esta migracion.
--
-- Idempotente: la existencia de la subarea tambien se chequea por nombre
-- normalizado (matchea con o sin tilde).

SET client_encoding = 'UTF8';

INSERT INTO subarea (nombre, descripcion, id_area, activo, id_municipio)
SELECT 'Policía Municipal',
       'Subárea de la Secretaría de Seguridad — atención de eventos de emergencia (módulo Emergencias, taxonomía RESO-2022-166 MinSeg PBA)',
       a.id_area, TRUE, NULL
FROM area a
WHERE translate(lower(a.nombre), 'áéíóú', 'aeiou') = 'secretaria de seguridad'
  AND a.activo
  AND NOT EXISTS (
      SELECT 1 FROM subarea s
      WHERE translate(lower(s.nombre), 'áéíóú', 'aeiou') = 'policia municipal'
  )
ORDER BY a.id_area
LIMIT 1;

INSERT INTO subarea (nombre, descripcion, id_area, activo, id_municipio)
SELECT 'Defensa Civil',
       'Subárea de la Secretaría de Seguridad — atención de eventos de emergencia civil (módulo Emergencias, taxonomía propia)',
       a.id_area, TRUE, NULL
FROM area a
WHERE translate(lower(a.nombre), 'áéíóú', 'aeiou') = 'secretaria de seguridad'
  AND a.activo
  AND NOT EXISTS (
      SELECT 1 FROM subarea s
      WHERE translate(lower(s.nombre), 'áéíóú', 'aeiou') = 'defensa civil'
  )
ORDER BY a.id_area
LIMIT 1;

-- Verificacion: debe devolver 2 filas con el mismo id_area
SELECT s.id_subarea, s.nombre, s.id_area, a.nombre AS area_nombre, s.activo
FROM subarea s JOIN area a ON a.id_area = s.id_area
WHERE translate(lower(s.nombre), 'áéíóú', 'aeiou') IN ('policia municipal', 'defensa civil');
