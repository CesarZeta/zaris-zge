-- IT-01 F6.2 — usuario de conexión con barrera, SOLO PARA LOCAL (zaris_dev).
-- En prod lo crea César en el SQL Editor de Supabase con su propia clave (F6.3).
-- La clave de desarrollo NO va en este archivo: se pasa al ejecutarlo y se guarda en backend/.env.local
-- (APP_DB_USER=zaris_app, APP_DB_PASSWORD=<la misma>). Ver PLAN_MULTI_MUNICIPIO_F6_2.md, Task 1.
--
--   psql -h 127.0.0.1 -U postgres -d zaris_dev -v clave=<clave_dev> -f tools/crear_usuario_zaris_app_local.sql
--
-- Sin permiso para saltear RLS, sin ser dueño de nada: los permisos y las políticas los da la migración 138.
SELECT format('CREATE ROLE zaris_app LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE', :'clave')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zaris_app')
\gexec
