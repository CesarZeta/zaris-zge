-- Migracion 115 — Baja de la gestion «Emergencia Climatica» (2026-10-21)
--
-- Decision de Cesar (2026-10-21): la subarea venia de la planilla del sistema
-- anterior (area de servicio 7794) y juntaba arboles, postes, luminarias y
-- pluviales caidos por temporal. Los arboles y las ramas van a Arbolado y el
-- resto a la gestion que ya atiende algo parecido; la subarea se da de baja.
-- Las personas cargadas ahi pasan a Arbolado.
--
-- Solo datos. Todo se resuelve POR NOMBRE (los ids difieren entre local y prod,
-- §21) y es idempotente: tras la primera corrida no quedan tipos en la subarea.
-- Backup previo en prod: _backup_emergencia_climatica_2026_10_21.

-- 1) Tipos de reclamo → gestion destino.
UPDATE tipo_reclamo tr
   SET id_subarea = dest.id_subarea, fecha_modificacion = NOW()
  FROM (VALUES
        ('Árbol/tocón/rama caído/quebrado',          'Arbolado'),
        ('Árbol/tocón/rama caído afecta vehículo',   'Arbolado'),
        ('Árbol/tocón/rama caída afecta inmueble',   'Arbolado'),
        ('Árbol/tocón/rama con peligro de caída',    'Arbolado'),
        ('Recolección ramas/montículos',             'Arbolado'),
        ('Anegamiento',                              'Obras Municipales - Pluviales'),
        ('Pozo/hundimiento en calle',                'Obras Municipales - Pluviales'),
        ('Pozo/hundimiento en vereda',               'Obras Municipales - Pluviales'),
        ('Tapa tormenta/rota/desplazada/faltante',   'Obras Municipales - Pluviales'),
        ('Luminaria/semáforo caído',                 'Alumbrado Público'),
        ('Luminaria/semáforo caído afecta inmueble', 'Alumbrado Público'),
        ('Luminaria/semáforo caído afecta vehículo', 'Alumbrado Público'),
        ('Luminaria/semáforo con peligro de caída',  'Alumbrado Público'),
        ('Cartel/poste caído',                       'Mant. general'),
        ('Cartel/poste caído afecta inmueble',       'Mant. general'),
        ('Cartel/poste caído afecta vehículo',       'Mant. general'),
        ('Cartel/poste con peligro de caída',        'Mant. general'),
        ('Objeto en tendido eléctrico',              'Mant. general'),
        ('Instalación eléctrica expuesta',           'Luminaria - interno'),
        ('Caída de mampostería',                     'Obras Particulares'),
        ('Punto seguro afectado',                    'Relevamiento Punto Seguro'),
        ('Cámara de seguridad afectada',             'Relevamiento Punto Seguro')
       ) AS m(tipo, destino)
  JOIN subarea dest ON dest.nombre = m.destino AND dest.activo = TRUE
  JOIN subarea ec   ON ec.nombre = 'Emergencia Climática'
 WHERE tr.nombre = m.tipo AND tr.id_subarea = ec.id_subarea;

-- 2) El area del reclamo se deriva de la subarea del tipo (§18): los reclamos
--    de tipos que cambiaron de Secretaria la acompanan.
UPDATE reclamos r
   SET id_area = s.id_area, fecha_modificacion = NOW()
  FROM tipo_reclamo tr
  JOIN subarea s ON s.id_subarea = tr.id_subarea
 WHERE r.id_tipo_reclamo = tr.id_tipo_reclamo
   AND tr.nombre IN ('Anegamiento', 'Pozo/hundimiento en calle', 'Pozo/hundimiento en vereda',
                     'Tapa tormenta/rota/desplazada/faltante', 'Caída de mampostería',
                     'Punto seguro afectado', 'Cámara de seguridad afectada')
   AND r.id_area IS DISTINCT FROM s.id_area;

-- 3) Personas de la gestion → Arbolado. El agente es la fuente del scope (§3);
--    su usuario se alinea al agente (lo usa el cierre directo sin OT).
--    OJO: NO mover «los usuarios con id_subarea = Emergencia Climatica»: en prod
--    habia 2 usuarios con esa subarea cargada por error (sus agentes estaban en
--    otras gestiones; sus ids de usuario coincidian con los ids de agente de las
--    personas de la gestion). Se alinean a su propio agente.
WITH movidos AS (
    UPDATE agentes a
       SET id_subarea = arb.id_subarea, fecha_modificacion = NOW()
      FROM subarea ec, subarea arb
     WHERE ec.nombre = 'Emergencia Climática' AND arb.nombre = 'Arbolado' AND arb.activo = TRUE
       AND a.id_subarea = ec.id_subarea
    RETURNING a.id_usuario, a.id_subarea
)
UPDATE usuarios u
   SET id_subarea = m.id_subarea, fecha_modif = NOW()
  FROM movidos m
 WHERE u.id_usuario = m.id_usuario;

UPDATE usuarios u
   SET id_subarea = a.id_subarea, fecha_modif = NOW()
  FROM agentes a, subarea ec
 WHERE ec.nombre = 'Emergencia Climática'
   AND u.id_subarea = ec.id_subarea
   AND a.id_usuario = u.id_usuario AND a.activo = TRUE;

-- 4) Baja logica de la subarea (solo si ya no le queda ningun tipo activo).
UPDATE subarea s
   SET activo = FALSE, fecha_modificacion = NOW()
 WHERE s.nombre = 'Emergencia Climática' AND s.activo = TRUE
   AND NOT EXISTS (SELECT 1 FROM tipo_reclamo t WHERE t.id_subarea = s.id_subarea AND t.activo = TRUE);
