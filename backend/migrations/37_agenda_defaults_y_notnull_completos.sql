-- =============================================================================
-- Migracion 37 — Agenda — Sincronizar defaults + NOT NULL faltantes en prod
-- =============================================================================
-- Contexto: las migs 30-34 se aplicaron en prod durante el E2E del 2026-05-12,
-- pero quedaron 2 grupos de drift respecto a local:
--   1) ALTER COLUMN ... SET DEFAULT faltante en ~10 columnas (mig 36 ya parcho
--      `activo`; falta id_municipio, resuelto, defaults de eventos, etc.).
--   2) NOT NULL faltante en columnas con DEFAULT NOW() (fecha_alta, fecha_modif
--      de las catalogo/transaccionales).
--
-- Verificado 2026-05-12: en prod los conteos de NULL son 0 en todas las
-- columnas afectadas, los SET NOT NULL son seguros sin backfill previo.
--
-- Idempotente: ALTER COLUMN SET DEFAULT y SET NOT NULL son no-ops si ya estan.
-- =============================================================================

BEGIN;

-- 1) DEFAULTs faltantes -----------------------------------------------------

-- id_municipio = 1 (municipio demo)
ALTER TABLE agenda_audit_log   ALTER COLUMN id_municipio SET DEFAULT 1;
ALTER TABLE conflictos_log     ALTER COLUMN id_municipio SET DEFAULT 1;
ALTER TABLE estado_evento      ALTER COLUMN id_municipio SET DEFAULT 1;
ALTER TABLE estado_reserva     ALTER COLUMN id_municipio SET DEFAULT 1;
ALTER TABLE evento_encargados  ALTER COLUMN id_municipio SET DEFAULT 1;
ALTER TABLE evento_reservas    ALTER COLUMN id_municipio SET DEFAULT 1;
ALTER TABLE eventos            ALTER COLUMN id_municipio SET DEFAULT 1;
ALTER TABLE ocupaciones        ALTER COLUMN id_municipio SET DEFAULT 1;

-- conflictos_log.resuelto = false
ALTER TABLE conflictos_log     ALTER COLUMN resuelto SET DEFAULT FALSE;

-- eventos: defaults de columnas operativas
ALTER TABLE eventos ALTER COLUMN capacidad_ciudadanos SET DEFAULT 1;
ALTER TABLE eventos ALTER COLUMN cantidad_encargados  SET DEFAULT 0;
ALTER TABLE eventos ALTER COLUMN tipo_qr              SET DEFAULT 'ninguno';
ALTER TABLE eventos ALTER COLUMN admite_autoservicio  SET DEFAULT FALSE;

-- 2) NOT NULL en timestamps con DEFAULT NOW() -------------------------------

ALTER TABLE agenda_audit_log   ALTER COLUMN fecha             SET NOT NULL;
ALTER TABLE agenda_audit_log   ALTER COLUMN fecha_alta        SET NOT NULL;

ALTER TABLE conflictos_log     ALTER COLUMN fecha_deteccion   SET NOT NULL;
ALTER TABLE conflictos_log     ALTER COLUMN fecha_alta        SET NOT NULL;
ALTER TABLE conflictos_log     ALTER COLUMN resuelto          SET NOT NULL;

ALTER TABLE estado_evento      ALTER COLUMN fecha_alta         SET NOT NULL;
ALTER TABLE estado_evento      ALTER COLUMN fecha_modificacion SET NOT NULL;

ALTER TABLE estado_reserva     ALTER COLUMN fecha_alta         SET NOT NULL;
ALTER TABLE estado_reserva     ALTER COLUMN fecha_modificacion SET NOT NULL;

ALTER TABLE evento_encargados  ALTER COLUMN fecha_alta         SET NOT NULL;
ALTER TABLE evento_encargados  ALTER COLUMN fecha_modificacion SET NOT NULL;

ALTER TABLE evento_reservas    ALTER COLUMN fecha_alta         SET NOT NULL;
ALTER TABLE evento_reservas    ALTER COLUMN fecha_modificacion SET NOT NULL;

ALTER TABLE eventos            ALTER COLUMN fecha_alta         SET NOT NULL;
ALTER TABLE eventos            ALTER COLUMN fecha_modificacion SET NOT NULL;

ALTER TABLE municipios         ALTER COLUMN fecha_alta         SET NOT NULL;
ALTER TABLE municipios         ALTER COLUMN fecha_modificacion SET NOT NULL;

ALTER TABLE ocupaciones        ALTER COLUMN fecha_alta         SET NOT NULL;
ALTER TABLE ocupaciones        ALTER COLUMN fecha_modificacion SET NOT NULL;

COMMIT;
