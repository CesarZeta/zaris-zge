-- Migración 128 — IT-01 F3b: acción `segundo_factor` en el registro del super administrador.
-- Plan: PLAN_MULTI_MUNICIPIO_F3B.md, Tarea 1. Spec: PLAN_MULTI_MUNICIPIO_F3B_DISENO.md §4.6.
--
-- LLEVA DROP: el MCP (apply_migration) la rechaza. En prod la corre César en el SQL Editor de
-- Supabase; en local, por psql. El resto de F3b va en la 128b (sin DROP, por MCP).
-- Solo amplía el CHECK: compatible con el código viejo. Re-aplicable.

BEGIN;

ALTER TABLE super_admin_acceso DROP CONSTRAINT IF EXISTS ck_super_admin_acceso_accion;
ALTER TABLE super_admin_acceso ADD CONSTRAINT ck_super_admin_acceso_accion CHECK (accion IN
    ('login', 'seleccion', 'request', 'historia_clinica', 'config_global',
     'municipio_editar', 'catalogo_global', 'segundo_factor'));

COMMIT;
