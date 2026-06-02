-- Migración 76 — Alta pública de vecinos: credencial de verificación de email para EMPRESAS.
--
-- Contexto: el autoregistro público (URL pública por municipio, slug validado mono-tenant)
-- permite que un vecino se dé de alta como ciudadano y, opcionalmente, dé de alta una empresa
-- vinculada a él. El ciudadano ya tiene `ciudadano_credencial` (mig 53) con password + token de
-- activación. La empresa NO necesita login con password por ahora: solo verificar su email.
--
-- Esta tabla es el espejo mínimo para esa verificación. Si en el futuro la empresa necesita
-- login propio, se le agrega `password_hash` y queda lista.
--
-- Las marcas "verificado" reusan columnas existentes:
--   - empresas.email_chk (BOOL, ya existe) = email verificado.
--   - ciudadanos.email_chk + ciudadanos.estado_validacion='verificado' (ya existen, mig 52).
--
-- Idempotente. Aplicar en local Y prod (§24).

CREATE TABLE IF NOT EXISTS empresa_credencial (
    id_empresa_credencial   SERIAL PRIMARY KEY,
    id_empresa              INTEGER NOT NULL UNIQUE
                              REFERENCES empresas(id_empresa) ON DELETE CASCADE,

    -- Verificación de email (token UUID opaco, no enumerable)
    token_verificacion          UUID,
    token_verificacion_expira   TIMESTAMPTZ,
    verificado                  BOOLEAN NOT NULL DEFAULT FALSE,
    verificado_en               TIMESTAMPTZ,

    -- Anti-abuso de reenvíos (cooldown)
    fecha_ultimo_email_verificacion TIMESTAMPTZ,

    -- Campos estándar §10
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

-- Índice parcial sobre el token cuando NOT NULL (espeja ciudadano_credencial)
CREATE INDEX IF NOT EXISTS idx_empresa_credencial_token_verificacion
    ON empresa_credencial (token_verificacion)
    WHERE token_verificacion IS NOT NULL;
