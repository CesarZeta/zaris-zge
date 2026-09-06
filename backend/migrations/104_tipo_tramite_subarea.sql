-- ============================================================================
-- 104: Gestion responsable del tipo de tramite — tipo_tramite.id_subarea.
--      Ordenamiento pedido por Cesar (2026-09-06) para el smoke de datos de la
--      demo: "todo lo relacionado con tramites tiene que estar asociado a algo
--      asi como la Secretaria de Gobierno, esa seria el area, despues la
--      subarea tendra que estar relacionada con el tramite".
--
-- Problema que resuelve: hasta ahora la relacion tipo de tramite -> subarea
-- existia SOLO dentro del circuito (destinatario inicial + destino_automatico_jsonb
-- + quien_puede_jsonb de las transiciones). Servia para operar, pero no se podia
-- agrupar la bandeja por gestion, filtrar por area, ni cortar el BI por
-- secretaria sin recorrer el FSM tipo por tipo.
--
-- La columna es la GESTION RESPONSABLE del tipo (quien lo tramita), NO el
-- destinatario del expediente: el destinatario sigue siendo polimorfico y vive
-- en `tramite` (id_subarea_actual / id_equipo_actual / id_agente_actual). No
-- cambia el FSM ni el scoping de §3 (que lee agentes.id_subarea).
--
-- NULL permitido a proposito: un tipo en borrador puede no tener gestion
-- asignada todavia. El backfill de abajo cubre los 15 tipos activos.
--
-- Decision de agrupacion (Cesar, 2026-09-06): las 7 subareas del circuito de
-- tramites cuelgan TODAS del area Gobierno — el expediente es de Gobierno
-- aunque el tema sea de otra secretaria. El area 1 se renombra a
-- "Secretaria de Gobierno" por consistencia con las otras cinco.
--
-- Idempotente (IF NOT EXISTS / WHERE id_subarea IS NULL).
-- ============================================================================

ALTER TABLE tipo_tramite
    ADD COLUMN IF NOT EXISTS id_subarea INTEGER
        REFERENCES subarea(id_subarea) ON DELETE SET NULL;

COMMENT ON COLUMN tipo_tramite.id_subarea IS
    'Gestion responsable del tipo (mig 104). El area se deriva por JOIN subarea->area (§27, nunca un id_area propio).';

CREATE INDEX IF NOT EXISTS ix_tipo_tramite_subarea ON tipo_tramite(id_subarea);

-- --------------------------------------------------------------------------
-- Consistencia de nomenclatura: el area 1 era "Gobierno" a secas mientras las
-- otras cinco son "Secretaria de ...".
-- --------------------------------------------------------------------------
-- Solo toca el area que se llama EXACTAMENTE "Gobierno" (prod). En local el
-- area de gobierno activa es "Secretaria de Gobierno y Legal Tecnica" y no se
-- renombra: el WHERE no matchea. Nunca por id (los ids difieren, §24).
UPDATE area
   SET nombre = 'Secretaría de Gobierno', fecha_modificacion = NOW()
 WHERE LOWER(TRIM(nombre)) = 'gobierno';

-- --------------------------------------------------------------------------
-- Las 7 subareas del circuito quedan bajo Secretaria de Gobierno (decision de
-- agrupacion). En prod ya estaban ahi; esto lo vuelve explicito e idempotente.
-- --------------------------------------------------------------------------
-- El area destino se RESUELVE POR NOMBRE, nunca por id: en prod es 1
-- ("Gobierno" -> "Secretaria de Gobierno"), en local es 15 ("Secretaria de
-- Gobierno y Legal Tecnica"). Hardcodear 1 mandaba las subareas a "Salud" en
-- local (§24, cazado el 2026-09-06 aplicando local primero).
UPDATE subarea
   SET id_area = (SELECT id_area FROM area
                   WHERE LOWER(nombre) LIKE '%gobierno%' AND activo
                   ORDER BY id_area LIMIT 1),
       fecha_modificacion = NOW()
 WHERE LOWER(nombre) IN ('mesa de entradas', 'habilitaciones comerciales',
                         'bromatologia e inspecciones', 'obras particulares',
                         'asesoria legal y tecnica', 'recursos humanos',
                         'espacios verdes')
   AND EXISTS (SELECT 1 FROM area WHERE LOWER(nombre) LIKE '%gobierno%' AND activo)
   AND id_area IS DISTINCT FROM (SELECT id_area FROM area
                                  WHERE LOWER(nombre) LIKE '%gobierno%' AND activo
                                  ORDER BY id_area LIMIT 1);

-- --------------------------------------------------------------------------
-- Backfill: gestion responsable de cada tipo, resuelta por el nombre de la
-- subarea (los ids difieren entre local y prod, §24). Solo pisa NULLs.
--   poda-arbol, solicitud-arbolado          -> Espacios Verdes
--   licencia-ordinaria                      -> Recursos Humanos
--   habilitacion-comercial, cambio-domicilio-comercial,
--   transferencia-habilitacion              -> Habilitaciones Comerciales
--   inspeccion-bromatologica                -> Bromatologia e Inspecciones
--   cartel-publicitario, aviso-obra,
--   permiso-espacio-publico,
--   inscripcion-profesional                 -> Obras Particulares
--   recurso-administrativo                  -> Asesoria Legal y Tecnica
--   pedido-informe, exencion-tasas,
--   permiso-demo-e2e                        -> Mesa de Entradas
-- (aviso-obra corrige un desvio real: sus expedientes iban a Habilitaciones.)
-- --------------------------------------------------------------------------
WITH mapa(codigo, subarea_nombre) AS (VALUES
    ('poda-arbol',                 'espacios verdes'),
    ('solicitud-arbolado',         'espacios verdes'),
    ('licencia-ordinaria',         'recursos humanos'),
    ('habilitacion-comercial',     'habilitaciones comerciales'),
    ('cambio-domicilio-comercial', 'habilitaciones comerciales'),
    ('transferencia-habilitacion', 'habilitaciones comerciales'),
    ('inspeccion-bromatologica',   'bromatologia e inspecciones'),
    ('cartel-publicitario',        'obras particulares'),
    ('aviso-obra',                 'obras particulares'),
    ('permiso-espacio-publico',    'obras particulares'),
    ('inscripcion-profesional',    'obras particulares'),
    ('recurso-administrativo',     'asesoria legal y tecnica'),
    ('pedido-informe',             'mesa de entradas'),
    ('exencion-tasas',             'mesa de entradas'),
    ('permiso-demo-e2e',           'mesa de entradas')
)
UPDATE tipo_tramite tt
   SET id_subarea = s.id_subarea, fecha_modificacion = NOW()
  FROM mapa m
  JOIN subarea s ON LOWER(s.nombre) = m.subarea_nombre AND s.activo
 WHERE tt.codigo = m.codigo
   AND tt.id_subarea IS NULL;
