-- Migración 142 — Canal «app de agentes» en reclamos.
-- Definición de César (2026-11-23): el canal (origen) es la interfaz por la que se registra la
-- transacción (call center, app del vecino, portal del vecino, app de agentes). El relevamiento es
-- un TIPO de transacción, no un canal: se carga desde la app de agentes y ese es su canal.
--
-- Qué hace: ck_reclamos_canal admite 'app_agentes' (los demás valores no cambian).
--
-- Lleva DROP CONSTRAINT: en prod la corre César en el SQL Editor de Supabase (el permiso del MCP
-- rechaza los DROP); en local, con asyncpg `driver_connection.execute`. Re-aplicable. Va ANTES del
-- código: sin ella, el alta de un relevamiento falla. Sin datos que tocar (no hay relevamientos en prod).

ALTER TABLE reclamos DROP CONSTRAINT IF EXISTS ck_reclamos_canal;
ALTER TABLE reclamos ADD CONSTRAINT ck_reclamos_canal CHECK (
    canal_origen IS NULL OR canal_origen IN
    ('web', 'whatsapp', 'telefono', 'presencial', 'oficio', 'app_movil', 'app_agentes', 'otro')
);

-- Los relevamientos ya cargados (solo en local: en prod no hay) toman su canal.
UPDATE reclamos SET canal_origen = 'app_agentes' WHERE es_relevamiento AND canal_origen = 'oficio';
