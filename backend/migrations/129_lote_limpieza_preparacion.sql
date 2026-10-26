-- Migración 129 — IT-01, lote de limpieza (preparación).
-- Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, «Lote de limpieza». El borrado va en la 129b.
--
-- Sin DROP (va por MCP). Re-aplicable. Compatible con el código viejo y el nuevo.
--
-- El único por municipio (uqmun_usuarios_username) no compara las cuentas sin municipio (NULL
-- es distinto de NULL): hasta hoy el username de los super administradores lo cuidaba el índice
-- global viejo usuarios_username_key, que borra la 129b. Este lo reemplaza para esas cuentas.

CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_username_sin_municipio
    ON usuarios (username) WHERE id_municipio IS NULL;
