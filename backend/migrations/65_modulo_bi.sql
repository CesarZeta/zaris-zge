-- Migración 65: registrar el módulo 'bi' (Análisis de datos) en el catálogo `modulos`.
--
-- El módulo React de BI (web-app/src/modules/bi/) consume los endpoints de
-- agregación /api/v1/bi/* (router con guard JWT). Para que aparezca en el sidebar
-- (filtrado por data-modulo, §30) hace falta la fila en `modulos`: sin ella,
-- modulos_permitidos nunca incluye 'bi' y el item se oculta para todos, incluso
-- admin. Ver §12 + memoria feedback_modulo_react_necesita_fila_en_modulos.
--
-- min_nivel_acceso=2 (Supervisor/Admin): es analítica de gestión, mismo criterio
-- que Encuestas. La UI gatea igual con WrapNivel.
--
-- Idempotente: ON CONFLICT DO NOTHING sobre la PK (modulo_codigo).

INSERT INTO modulos (modulo_codigo, nombre, descripcion, min_nivel_acceso, activo, id_municipio)
VALUES ('bi', 'Datos', 'Análisis de datos operativo y ejecutivo sobre los reclamos del municipio', 2, TRUE, 1)
ON CONFLICT (modulo_codigo) DO NOTHING;
