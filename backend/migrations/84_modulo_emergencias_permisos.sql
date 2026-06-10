-- Migracion 84: fila 'emergencias' en el catalogo de permisos `modulos` (SS30).
-- Sin esta fila, el item del sidebar con data-modulo="emergencias" queda
-- oculto para TODOS (incluido admin) — caso Encuestas mig 61.
-- min_nivel_acceso=3 (operador+): espeja el guard nivel<=3 del backend Fase 3.
-- Idempotente.

INSERT INTO modulos (modulo_codigo, nombre, descripcion, min_nivel_acceso, activo, id_municipio)
VALUES ('emergencias', 'Emergencias',
        'Modulo COM: recepcion de llamados, tablero del dispatcher y eventos de emergencia',
        3, TRUE, 1)
ON CONFLICT (modulo_codigo) DO UPDATE
SET nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    min_nivel_acceso = EXCLUDED.min_nivel_acceso,
    activo = TRUE,
    fecha_modificacion = NOW();
