-- Migracion 51: notificaciones in-app (modulo transversal, primer uso: Tramites)
-- Aplicada en local 2026-05-18.
-- Idempotente: CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS.

BEGIN;

CREATE TABLE IF NOT EXISTS notificacion (
    id_notificacion       SERIAL PRIMARY KEY,
    id_usuario            INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    tipo                  VARCHAR(50) NOT NULL,           -- 'tramite_bandeja_nuevo', futuros: 'tramite_firma_solicitada', etc.
    titulo                VARCHAR(200) NOT NULL,
    mensaje               TEXT,
    url_destino           VARCHAR(500),                   -- ej: '#/tramites/POD-LPL-2026-0009'
    -- referencia opcional al recurso disparador (polimorfica, sin FK fisica)
    recurso_tipo          VARCHAR(50),                    -- 'tramite', 'reclamo', etc.
    recurso_id            INTEGER,
    -- estado
    leida                 BOOLEAN NOT NULL DEFAULT FALSE,
    leida_en              TIMESTAMPTZ,
    -- canal email (mock por ahora)
    enviada_mail          BOOLEAN NOT NULL DEFAULT FALSE,
    enviada_mail_en       TIMESTAMPTZ,
    -- estandar §10
    activo                BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio          INTEGER,
    id_subarea            INTEGER,
    fecha_alta            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta       INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

-- Indice para la query principal: "mis no-leidas, mas recientes primero"
CREATE INDEX IF NOT EXISTS idx_notificacion_usuario_leida_fecha
    ON notificacion (id_usuario, leida, fecha_alta DESC)
    WHERE activo = TRUE;

-- Indice para resolver navegacion (raras, no critico)
CREATE INDEX IF NOT EXISTS idx_notificacion_recurso
    ON notificacion (recurso_tipo, recurso_id)
    WHERE activo = TRUE;

COMMIT;
