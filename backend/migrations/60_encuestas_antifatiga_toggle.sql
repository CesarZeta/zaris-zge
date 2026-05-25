-- Migración 60 — Toggle de tratamiento anti-fatiga de encuestas
--
-- Pedido 2026-05-25: además del toggle global 'encuestas_activas', exponer un
-- segundo flag booleano para activar/desactivar la regla anti-fatiga (no reenviar
-- encuesta al mismo ciudadano de la misma subárea dentro de los 30 días).
--
-- Hasta ahora la regla estaba hardcodeada (siempre activa). Con esta clave en
-- 'false' el backend (encuestas_service.antifatiga_esta_activo) saltea el chequeo
-- y permite reenviar. Default 'true' = comportamiento histórico.
--
-- Reusa la tabla key/value existente. Editable desde Maestros -> Configuración
-- general, al lado de 'encuestas_activas'. Idempotente por la UNIQUE en clave.

INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
VALUES (
    'encuestas_antifatiga_activo',
    'true',
    'boolean',
    'Habilita el tratamiento anti-fatiga de encuestas: si está en true, no se reenvía una encuesta al mismo ciudadano de la misma subárea dentro de los 30 días. false desactiva esa restricción (se podrá encuestar siempre que se cierre un reclamo).',
    TRUE
)
ON CONFLICT (clave) DO NOTHING;
