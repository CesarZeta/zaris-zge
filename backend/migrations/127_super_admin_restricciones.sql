-- Migración 127 — IT-01 F3: lugar para el super administrador (nivel 0, sin municipio)
-- Plan: PLAN_MULTI_MUNICIPIO_F3.md, Tarea 1. Spec: PLAN_MULTI_MUNICIPIO.md §4.
--
-- LLEVA DROP: el MCP (apply_migration) la rechaza. En prod la corre César en el SQL Editor de
-- Supabase; en local, por psql. El resto de F3 va en la 127b (sin DROP, por MCP).
-- Solo relaja restricciones: compatible con el código viejo (todas las cuentas de hoy tienen
-- nivel 1-5 y municipio). Re-aplicable.
--
-- Después de esta migración NO se vuelve a aplicar la 125c: le pondría NOT NULL a
-- usuarios.id_municipio y fallaría con el super administrador cargado.

BEGIN;

-- 1. Nivel 0 = super administrador.
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_nivel_acceso_check;
ALTER TABLE usuarios ADD CONSTRAINT usuarios_nivel_acceso_check CHECK (nivel_acceso BETWEEN 0 AND 5);

-- 2. El super administrador no tiene municipio, y es el único que puede no tenerlo.
ALTER TABLE usuarios ALTER COLUMN id_municipio DROP NOT NULL;
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS ck_usuarios_municipio_nivel;
ALTER TABLE usuarios ADD CONSTRAINT ck_usuarios_municipio_nivel
    CHECK ((nivel_acceso = 0) = (id_municipio IS NULL));

-- 3. Módulos exclusivos del super administrador: min_nivel_acceso = 0.
ALTER TABLE modulos DROP CONSTRAINT IF EXISTS modulos_min_nivel_acceso_check;
ALTER TABLE modulos ADD CONSTRAINT modulos_min_nivel_acceso_check CHECK (min_nivel_acceso BETWEEN 0 AND 5);

COMMIT;
