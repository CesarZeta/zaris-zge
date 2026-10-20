-- Migracion 113 — Modulo «Agentes de mi gestion» para el supervisor (2026-10-20)
--
-- Decision de Cesar (cuestionario 2026-10-20): el supervisor completa el perfil
-- laboral de los agentes de SU gestion (cargo, legajo, horario y equipos) en
-- Maestros → Agentes. Maestros sigue siendo del administrador (admin_tablas,
-- min_nivel 1); este codigo es el permiso alternativo que muestra el item del
-- sidebar al nivel 2 (data-modulo-fallback, §30) y la pantalla queda acotada a
-- Agentes de su subarea (frontend/admin_tablas.html + admin_tablas.py imponen lo
-- mismo). Solo datos: idempotente, activo explicito (§21).

INSERT INTO modulos (modulo_codigo, nombre, descripcion, min_nivel_acceso, activo)
VALUES ('agentes_gestion', 'Agentes de mi gestión',
        'Perfil laboral (cargo, legajo, horario y equipos) de los agentes de la gestión del supervisor, en Maestros → Agentes.',
        2, TRUE)
ON CONFLICT (modulo_codigo) DO NOTHING;
