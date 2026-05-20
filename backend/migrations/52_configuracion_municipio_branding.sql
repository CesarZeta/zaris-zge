-- Migracion 52: configuracion_general extendida con branding del municipio.
-- Agrega 3 claves nuevas al maestro key-value existente: descripcion + 2 colores.
-- La carga real se hace desde el panel admin ZARIS (no en esta etapa).
-- Idempotente: INSERT ON CONFLICT DO NOTHING.

BEGIN;

INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
VALUES
    ('municipio_descripcion', '', 'string',
     'Texto corto que aparece en la pantalla de login de la PWA App Vecinos. Ej: "Servicio oficial de atencion al vecino".',
     TRUE),
    ('municipio_color_primary', '', 'string',
     'Color primario del municipio en formato hex (#RRGGBB). Aplica a botones y enfasis en la PWA App Vecinos.',
     TRUE),
    ('municipio_color_accent', '', 'string',
     'Color de acento del municipio en formato hex (#RRGGBB), opcional. Aplica a badges y links en la PWA App Vecinos.',
     TRUE)
ON CONFLICT (clave) DO NOTHING;

COMMIT;
