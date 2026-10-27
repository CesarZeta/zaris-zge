-- Migración 130 — IT-01 F4+F5: acciones nuevas en el registro del super administrador.
-- Plan: PLAN_MULTI_MUNICIPIO_F4_F5.md, Tarea 4. Spec: PLAN_MULTI_MUNICIPIO_F4_F5_DISENO.md.
--
-- LLEVA DROP: el MCP (apply_migration) la rechaza. En prod la corre César en el SQL Editor de
-- Supabase; en local, por psql. El resto de F4 va en la 130b y la 130c (sin DROP, por MCP).
-- Solo amplía el CHECK: compatible con el código viejo. Re-aplicable.

BEGIN;

ALTER TABLE super_admin_acceso DROP CONSTRAINT IF EXISTS ck_super_admin_acceso_accion;
ALTER TABLE super_admin_acceso ADD CONSTRAINT ck_super_admin_acceso_accion CHECK (accion IN
    ('login', 'seleccion', 'request', 'historia_clinica', 'config_global',
     'municipio_editar', 'catalogo_global', 'segundo_factor',
     'municipio_alta', 'municipio_estado', 'municipio_modulos', 'exportacion', 'vaciado',
     'super_alta', 'super_baja'));

COMMIT;
