-- ============================================================================
-- 99: Bandeja de avisos del vecino (App Vecinos) — tabla ciudadano_aviso.
--     Pendiente del traspaso 2026-07-16 (zaris-vecinos/ESTADO.md): la PWA ya
--     tiene la pantalla /alertas pero el backend solo mandaba push, que es
--     efimero y solo llega a quien tiene una suscripcion activa. Esta tabla
--     persiste cada aviso al ciudadano para que GET /api/v1/publico/avisos lo
--     liste, con leido / no leido.
--
-- Origen de los avisos: los MISMOS hooks post-commit que hoy disparan el push
-- (services/push.py::notificar_estado_reclamo / notificar_estado_emergencia,
-- invocados desde reclamos.py, ordenes_trabajo.py y emergencias.py). El aviso
-- se persiste ANTES del push, haya o no suscripcion. `tipo='municipio'` queda
-- reservado para avisos manuales del municipio (sin emisor todavia).
--
-- id_usuario_alta / id_usuario_modificacion quedan NULL: el vecino no es
-- `usuarios` (scope publico, §38). Estandar §10 completo. RLS habilitada sin
-- politicas (deny-all; el backend conecta como postgres y la bypassea, §21).
-- Idempotente (IF NOT EXISTS).
-- ============================================================================

CREATE TABLE IF NOT EXISTS ciudadano_aviso (
    id_ciudadano_aviso      SERIAL PRIMARY KEY,
    id_ciudadano            INTEGER NOT NULL REFERENCES ciudadanos(id_ciudadano) ON DELETE CASCADE,
    tipo                    VARCHAR(40)  NOT NULL,
    titulo                  VARCHAR(200) NOT NULL,
    mensaje                 TEXT,
    -- Ruta RELATIVA dentro de la PWA (misma convencion que el payload del push).
    url_destino             VARCHAR(300),
    recurso_tipo            VARCHAR(30),
    recurso_id              INTEGER,
    leido                   BOOLEAN NOT NULL DEFAULT FALSE,
    leido_en                TIMESTAMPTZ,
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_ciudadano_aviso_tipo
        CHECK (tipo IN ('reclamo_estado', 'emergencia_estado', 'municipio'))
);

-- Bandeja: los N mas recientes del ciudadano.
CREATE INDEX IF NOT EXISTS idx_ciudadano_aviso_bandeja
    ON ciudadano_aviso (id_ciudadano, fecha_alta DESC)
    WHERE activo = TRUE;

-- Badge de no leidos (COUNT por ciudadano sobre un set chico).
CREATE INDEX IF NOT EXISTS idx_ciudadano_aviso_no_leidos
    ON ciudadano_aviso (id_ciudadano)
    WHERE activo = TRUE AND leido = FALSE;

ALTER TABLE ciudadano_aviso ENABLE ROW LEVEL SECURITY;
