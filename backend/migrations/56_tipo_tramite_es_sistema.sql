-- Migracion 56: marcar tipos de tramite preconstruidos (seed) vs custom (creados por usuario)
--
-- tipo_tramite.es_sistema = TRUE  -> tipo precargado por seed_tramites.py (no editable como "custom")
-- tipo_tramite.es_sistema = FALSE -> tipo creado desde el editor admin por un usuario ("custom")
--
-- Permite que la pantalla "Tipos de tramite" muestre una leyenda Sistema/Custom.
-- Idempotente.

ALTER TABLE tipo_tramite
  ADD COLUMN IF NOT EXISTS es_sistema BOOLEAN NOT NULL DEFAULT FALSE;

-- Backfill: los 9 tipos del seed original (codigos conocidos) quedan como sistema.
-- Se identifican por codigo, no por id (los ids difieren entre entornos — regla §24).
UPDATE tipo_tramite
   SET es_sistema = TRUE
 WHERE codigo IN (
   'poda-arbol',
   'pedido-informe',
   'licencia-ordinaria',
   'habilitacion-comercial',
   'cambio-domicilio-comercial',
   'transferencia-habilitacion',
   'inspeccion-bromatologica',
   'cartel-publicitario',
   'recurso-administrativo'
 );
