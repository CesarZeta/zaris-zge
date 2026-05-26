-- Migración 61: registrar el módulo 'encuestas' en el catálogo `modulos`.
--
-- El módulo React de resultados de encuestas (web-app/src/modules/encuestas/)
-- consume los dashboards admin que ya existían (CLAUDE.md §42). Para que aparezca
-- en el sidebar (filtrado por data-modulo, §30) hace falta la fila en `modulos`:
-- sin ella, modulos_permitidos nunca incluye 'encuestas' y el item se oculta
-- para todos, incluso admin.
--
-- min_nivel_acceso=2 (Supervisor/Admin): los dashboards exigen _require_supervisor
-- (nivel <= 2) en el backend; la UI gatea igual. No tiene sentido exponerlo a
-- operadores/consultores (verían 403).
--
-- Idempotente: ON CONFLICT DO NOTHING sobre la PK (modulo_codigo).

INSERT INTO modulos (modulo_codigo, nombre, descripcion, min_nivel_acceso, activo, id_municipio)
VALUES ('encuestas', 'Encuestas', 'Resultados de encuestas de satisfacción (CSAT) al cerrar reclamos', 2, TRUE, 1)
ON CONFLICT (modulo_codigo) DO NOTHING;
