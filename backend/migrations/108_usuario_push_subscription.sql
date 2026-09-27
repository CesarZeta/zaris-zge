-- ============================================================================
-- Migración 108 — Web Push para USUARIOS INTERNOS (App de agentes `zaris-agentes`)
-- 2026-09-26
--
-- Espejo de `ciudadano_push_subscription` (mig 53) pero clavado a `usuarios`:
-- un agente que instala la app en su celular registra la suscripción del
-- navegador y el backend le manda push cuando le asignan una OT
-- (services/push.py::notificar_ot_asignada). Claves VAPID: las mismas que
-- la App Vecinos (env vars o configuracion_general.vapid_*).
--
-- No hay "canal preferido": la suscripción activa ES el toggle (unsubscribe
-- la apaga). Sin toggles de negocio por ahora.
-- ============================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS usuario_push_subscription (
    id_usuario_push_subscription SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,

    endpoint TEXT NOT NULL,
    p256dh TEXT NOT NULL,
    auth_secret TEXT NOT NULL,
    user_agent TEXT NULL,

    -- Estándar §10
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio INTEGER NULL,
    id_subarea INTEGER NULL,
    fecha_alta TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta INTEGER NULL REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER NULL REFERENCES usuarios(id_usuario) ON DELETE SET NULL,

    -- Re-suscribirse desde el mismo navegador reactiva y refresca las claves.
    UNIQUE (id_usuario, endpoint)
);

CREATE INDEX IF NOT EXISTS idx_usuario_push_subscription_usuario_activo
    ON usuario_push_subscription (id_usuario)
    WHERE activo = TRUE;

-- Sin políticas = deny-all para roles no dueños (§21/§26). El backend conecta
-- como dueño y bypassea RLS.
ALTER TABLE usuario_push_subscription ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE usuario_push_subscription IS
    'Suscripciones Web Push de usuarios internos (App de agentes). Mig 108, 2026-09-26.';

COMMIT;
