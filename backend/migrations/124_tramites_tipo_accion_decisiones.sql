-- Migracion 124 — Decisiones intermedias de los tramites con aprobar/rechazar (2026-10-23,
-- decision de Cesar: colorear los botones del agente segun la accion). Solo datos.
--
-- La 123 etiqueto las transiciones que CIERRAN. En varios circuitos la decision ocurre un
-- paso antes ("Aprobar" -> Aprobada, y despues "Archivar"), asi que el boton verde era
-- "Archivar". Aca se etiquetan esas decisiones. No cambia el resultado: solo la transicion
-- que llega a un estado final lo sella (mig 101). Quedan 'avanzar' los pasos de tramite
-- ("Derivar a...", "Titular anterior OK", "Pedir subsanacion"): 'derivar' cambia el
-- comportamiento con visados bloqueantes y no se toca aca.
--
-- Por codigo de tipo y de estado, en todas las versiones del tipo. Respaldo en la misma
-- tabla de la 123 (_backup_tramite_tipo_accion_2026_10_23). Idempotente.

CREATE TABLE IF NOT EXISTS _backup_tramite_tipo_accion_2026_10_23 (
    id_tipo_tramite_transicion INTEGER PRIMARY KEY,
    tipo_accion                VARCHAR(20),
    fecha_modificacion         TIMESTAMPTZ,
    respaldado_en              TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE _backup_tramite_tipo_accion_2026_10_23 ENABLE ROW LEVEL SECURITY;

WITH mapa (tipo, origen, destino, accion) AS (
    VALUES
    ('poda-arbol',                 'en_evaluacion',    'aprobada',       'aprobar'),
    ('poda-arbol',                 'en_evaluacion',    'rechazada',      'rechazar'),
    ('cambio-domicilio-comercial', 'en_revision',      'aprobada',       'aprobar'),
    ('cartel-publicitario',        'revision_tecnica', 'pago_pendiente', 'aprobar'),
    ('habilitacion-comercial',     'inspeccion',       'aprobada',       'aprobar'),
    ('licencia-ordinaria',         'solicitada',       'aprobada_jefe',  'aprobar'),
    ('licencia-ordinaria',         'aprobada_jefe',    'aprobada_rrhh',  'aprobar'),
    ('transferencia-habilitacion', 'validando_nuevo',  'aprobada',       'aprobar')
),
objetivo AS (
    SELECT tr.id_tipo_tramite_transicion, tr.tipo_accion, tr.fecha_modificacion, m.accion
      FROM mapa m
      JOIN tipo_tramite tt          ON tt.codigo = m.tipo
      JOIN tipo_tramite_version v   ON v.id_tipo_tramite = tt.id_tipo_tramite
      JOIN tipo_tramite_transicion tr ON tr.id_tipo_tramite_version = v.id_tipo_tramite_version
      JOIN tipo_tramite_estado eo   ON eo.id_tipo_tramite_estado = tr.id_estado_origen  AND eo.codigo = m.origen
      JOIN tipo_tramite_estado ed   ON ed.id_tipo_tramite_estado = tr.id_estado_destino AND ed.codigo = m.destino
     WHERE tr.tipo_accion IS DISTINCT FROM m.accion
),
respaldo AS (
    INSERT INTO _backup_tramite_tipo_accion_2026_10_23 (id_tipo_tramite_transicion, tipo_accion, fecha_modificacion)
    SELECT id_tipo_tramite_transicion, tipo_accion, fecha_modificacion FROM objetivo
    ON CONFLICT (id_tipo_tramite_transicion) DO NOTHING
)
UPDATE tipo_tramite_transicion tr
   SET tipo_accion = o.accion, fecha_modificacion = NOW()
  FROM objetivo o
 WHERE tr.id_tipo_tramite_transicion = o.id_tipo_tramite_transicion;
