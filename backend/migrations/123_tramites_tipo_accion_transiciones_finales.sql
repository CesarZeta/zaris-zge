-- Migracion 123 — Resultado del tramite al cerrarse (2026-10-23, decision de Cesar). Solo datos.
--
-- La regla de la mig 101 sella tramite.resultado solo si la transicion que llega
-- a un estado FINAL es tipo_accion 'aprobar' o 'rechazar'. En prod las 28
-- transiciones finales de los 15 tipos publicados decian 'avanzar', asi que
-- ningun cierre desde la pantalla avisaba al vecino "terminó: APROBADO/RECHAZADO"
-- ni disparaba la encuesta. Aca se etiquetan 25 segun su sentido. En los
-- circuitos que deciden en un estado intermedio y despues "Archivan", lo que se
-- etiqueta es el Archivar segun de donde sale (Aprobada -> Archivado = aprobar).
--
-- Quedan 'avanzar' a proposito (fase 2, circuito nuevo en borrador): Aviso de
-- Obra (una sola transicion para aprobar y rechazar) y "Dictar resolucion" del
-- Recurso administrativo (puede hacer lugar o no). Pedido de informe (interno):
-- Archivar = aprobar ("cumplido").
--
-- Resuelto por codigo de tipo y de estado (los ids difieren entre entornos), en
-- TODAS las versiones del tipo (los tramites en curso de una version vieja
-- tambien cierran con resultado). Los tipos que no existen en un entorno se
-- saltean solos. Es metadata de la transicion, no estructura: no cambia el
-- circuito. Respaldo de los valores previos en _backup_tramite_tipo_accion_2026_10_23.
-- Idempotente.

CREATE TABLE IF NOT EXISTS _backup_tramite_tipo_accion_2026_10_23 (
    id_tipo_tramite_transicion INTEGER PRIMARY KEY,
    tipo_accion                VARCHAR(20),
    fecha_modificacion         TIMESTAMPTZ,
    respaldado_en              TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE _backup_tramite_tipo_accion_2026_10_23 ENABLE ROW LEVEL SECURITY;

WITH mapa (tipo, origen, destino, accion) AS (
    VALUES
    ('poda-arbol',                 'aprobada',           'archivado',          'aprobar'),
    ('poda-arbol',                 'rechazada',          'archivado',          'rechazar'),
    ('cambio-domicilio-comercial', 'aprobada',           'archivado',          'aprobar'),
    ('cambio-domicilio-comercial', 'en_revision',        'rechazada',          'rechazar'),
    ('cambio-domicilio-comercial', 'rechazada',          'archivado',          'rechazar'),
    ('transferencia-habilitacion', 'aprobada',           'archivado',          'aprobar'),
    ('transferencia-habilitacion', 'validando_anterior', 'rechazada',          'rechazar'),
    ('transferencia-habilitacion', 'validando_nuevo',    'rechazada',          'rechazar'),
    ('habilitacion-comercial',     'aprobada',           'emitida',            'aprobar'),
    ('habilitacion-comercial',     'inspeccion',         'rechazada',          'rechazar'),
    ('inspeccion-bromatologica',   'realizada',          'aprobada',           'aprobar'),
    ('inspeccion-bromatologica',   'realizada',          'rechazada',          'rechazar'),
    ('exencion-tasas',             'en_evaluacion',      'aprobada',           'aprobar'),
    ('exencion-tasas',             'en_evaluacion',      'rechazada',          'rechazar'),
    ('permiso-espacio-publico',    'en_revision',        'otorgado',           'aprobar'),
    ('permiso-espacio-publico',    'en_revision',        'denegado',           'rechazar'),
    ('cartel-publicitario',        'pago_pendiente',     'instalado',          'aprobar'),
    ('cartel-publicitario',        'revision_tecnica',   'rechazado',          'rechazar'),
    ('inscripcion-profesional',    'aprobado',           'archivado',          'aprobar'),
    ('licencia-ordinaria',         'aprobada_rrhh',      'notificada',         'aprobar'),
    ('licencia-ordinaria',         'solicitada',         'rechazada',          'rechazar'),
    ('licencia-ordinaria',         'aprobada_jefe',      'rechazada',          'rechazar'),
    ('recurso-administrativo',     'presentado',         'inadmisible',        'rechazar'),
    ('permiso-demo-e2e',           'aprobado',           'archivado',          'aprobar'),
    ('pedido-informe',             'respondido',         'archivado',          'aprobar')
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
