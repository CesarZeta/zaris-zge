-- Migración 139 — Trámites del vecino, fase 1 backend: el vecino como actor de los trámites y
-- los pedidos al iniciador. Spec: docs/superpowers/specs/2026-11-21-tramites-vecino-design.md.
--
-- Qué hace:
--   1. tramite.id_agente_iniciador, tramite_movimiento.id_agente y tramite_documento.id_agente_subio
--      pasan a admitir NULL (el actor puede ser el vecino).
--   2. tramite_movimiento.id_ciudadano_actor y tramite_documento.id_ciudadano_subio (FK simple y
--      compuesta a ciudadanos) + CHECK de un solo actor por fila; tramite_documento.id_tramite_pedido.
--      Toda referencia nueva lleva su FK simple y su FK compuesta por municipio (§10).
--   3. tipo_tramite.ofrecer_al_vecino y tipo_tramite.exige_identidad_validada (ambas FALSE).
--   4. Tablas nuevas ciudadano_identidad_validacion y tramite_pedido_iniciador, clasificadas en
--      municipio_tabla_clase, con RLS y su política barrera_municipio (la 138 ya corrió), y permisos
--      explícitos de zaris_app sobre la tabla y su secuencia.
--   5. Se amplían los CHECK tramite_movimiento_tipo_check y ck_ciudadano_aviso_tipo.
--
-- Lleva DROP CONSTRAINT / DROP NOT NULL: en prod la corre César en el SQL Editor de Supabase
-- (el permiso del MCP rechaza los DROP); en local, con asyncpg `driver_connection.execute`.
-- Re-aplicable. Los datos van en la 139b.

-- 1. El actor ya no es siempre un agente.
ALTER TABLE tramite            ALTER COLUMN id_agente_iniciador DROP NOT NULL;
ALTER TABLE tramite_movimiento ALTER COLUMN id_agente           DROP NOT NULL;
ALTER TABLE tramite_documento  ALTER COLUMN id_agente_subio     DROP NOT NULL;

-- 2. El vecino como actor.
ALTER TABLE tramite_movimiento ADD COLUMN IF NOT EXISTS id_ciudadano_actor INTEGER;
ALTER TABLE tramite_documento  ADD COLUMN IF NOT EXISTS id_ciudadano_subio INTEGER;
ALTER TABLE tramite_documento  ADD COLUMN IF NOT EXISTS id_tramite_pedido  INTEGER;

-- 3. Qué tipos se ofrecen al vecino y cuáles exigen identidad validada en el municipio.
ALTER TABLE tipo_tramite ADD COLUMN IF NOT EXISTS ofrecer_al_vecino          BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE tipo_tramite ADD COLUMN IF NOT EXISTS exige_identidad_validada   BOOLEAN NOT NULL DEFAULT FALSE;

-- 4a. Validación de identidad del vecino en ventanilla.
CREATE TABLE IF NOT EXISTS ciudadano_identidad_validacion (
    id_ciudadano_identidad_validacion SERIAL       PRIMARY KEY,
    id_ciudadano            INTEGER      NOT NULL,
    id_agente               INTEGER      NOT NULL,
    fecha                   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    documento_presentado    VARCHAR(40)  NOT NULL,
    observacion             TEXT,
    motivo_revocacion       TEXT,
    id_agente_revoca        INTEGER,
    fecha_revocacion        TIMESTAMPTZ,
    activo                  BOOLEAN      NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER      NOT NULL REFERENCES municipios (id_municipio),
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL
);
COMMENT ON TABLE ciudadano_identidad_validacion IS
    'Validación presencial de la identidad de un vecino en el municipio (trámites del vecino). Una activa por persona.';
CREATE UNIQUE INDEX IF NOT EXISTS uq_ciudadano_identidad_validacion_mun_id
    ON ciudadano_identidad_validacion (id_municipio, id_ciudadano_identidad_validacion);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ciudadano_identidad_activa
    ON ciudadano_identidad_validacion (id_ciudadano) WHERE activo;

-- 4b. Pedidos del agente al iniciador de un trámite.
CREATE TABLE IF NOT EXISTS tramite_pedido_iniciador (
    id_tramite_pedido       SERIAL       PRIMARY KEY,
    id_tramite              INTEGER      NOT NULL,
    texto                   TEXT         NOT NULL,
    pide_archivo            BOOLEAN      NOT NULL DEFAULT FALSE,
    estado                  VARCHAR(12)  NOT NULL DEFAULT 'abierto',
    id_agente_pide          INTEGER,
    fecha_pedido            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    respuesta_texto         TEXT,
    fecha_respuesta         TIMESTAMPTZ,
    id_agente_cancela       INTEGER,
    motivo_cancelacion      TEXT,
    respuesta_vista_en      TIMESTAMPTZ,
    aviso_nivel             SMALLINT     NOT NULL DEFAULT 0,
    aviso_en                TIMESTAMPTZ,
    activo                  BOOLEAN      NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER      NOT NULL REFERENCES municipios (id_municipio),
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_tramite_pedido_estado CHECK (estado IN ('abierto', 'respondido', 'cancelado'))
);
COMMENT ON TABLE tramite_pedido_iniciador IS
    'Pedido de un agente al iniciador (vecino) de un trámite: texto, si pide archivo, respuesta y avisos.';
CREATE UNIQUE INDEX IF NOT EXISTS uq_tramite_pedido_mun_id
    ON tramite_pedido_iniciador (id_municipio, id_tramite_pedido);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tramite_pedido_abierto
    ON tramite_pedido_iniciador (id_tramite) WHERE estado = 'abierto' AND activo;
-- Índices de las referencias: los pedidos de un trámite (todos los estados) y los documentos de la
-- respuesta a un pedido (también los usa la FK al borrar o cambiar un pedido).
CREATE INDEX IF NOT EXISTS idx_tramite_pedido_iniciador_id_tramite
    ON tramite_pedido_iniciador (id_tramite);
CREATE INDEX IF NOT EXISTS idx_tramite_documento_id_tramite_pedido
    ON tramite_documento (id_tramite_pedido);

-- 5. FK simples y compuestas (id_municipio, col) de cada referencia nueva (§10), y CHECK de un solo
--    actor. La simple se crea solo si la columna no tiene ninguna FK de una columna (como la 133b).
DO $$
DECLARE
    f RECORD;
BEGIN
    FOR f IN SELECT * FROM (VALUES
        ('ciudadano_identidad_validacion', 'ciudadano_identidad_validacion_id_ciudadano_fkey',
         'id_ciudadano',       'ciudadanos',               'id_ciudadano'),
        ('ciudadano_identidad_validacion', 'ciudadano_identidad_validacion_id_agente_fkey',
         'id_agente',          'agentes',                  'id_agente'),
        ('ciudadano_identidad_validacion', 'ciudadano_identidad_validacion_id_agente_revoca_fkey',
         'id_agente_revoca',   'agentes',                  'id_agente'),
        ('tramite_pedido_iniciador',       'tramite_pedido_iniciador_id_tramite_fkey',
         'id_tramite',         'tramite',                  'id_tramite'),
        ('tramite_pedido_iniciador',       'tramite_pedido_iniciador_id_agente_pide_fkey',
         'id_agente_pide',     'agentes',                  'id_agente'),
        ('tramite_pedido_iniciador',       'tramite_pedido_iniciador_id_agente_cancela_fkey',
         'id_agente_cancela',  'agentes',                  'id_agente'),
        ('tramite_movimiento',             'tramite_movimiento_id_ciudadano_actor_fkey',
         'id_ciudadano_actor', 'ciudadanos',               'id_ciudadano'),
        ('tramite_documento',              'tramite_documento_id_ciudadano_subio_fkey',
         'id_ciudadano_subio', 'ciudadanos',               'id_ciudadano'),
        ('tramite_documento',              'tramite_documento_id_tramite_pedido_fkey',
         'id_tramite_pedido',  'tramite_pedido_iniciador', 'id_tramite_pedido')
    ) AS v(tabla, nombre, col, destino, col_destino)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint c
             WHERE c.conrelid = ('public.' || f.tabla)::regclass AND c.contype = 'f'
               AND c.conkey = ARRAY[(SELECT attnum FROM pg_attribute
                                      WHERE attrelid = ('public.' || f.tabla)::regclass AND attname = f.col)]) THEN
            EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES %I (%I)',
                           f.tabla, f.nombre, f.col, f.destino, f.col_destino);
        END IF;
    END LOOP;

    FOR f IN SELECT * FROM (VALUES
        ('ciudadano_identidad_validacion', 'fkm_ciudadano_identidad_validacion_id_ciudadano_fkey',
         'id_ciudadano',      'ciudadanos',                'id_ciudadano'),
        ('ciudadano_identidad_validacion', 'fkm_ciudadano_identidad_validacion_id_agente_fkey',
         'id_agente',         'agentes',                   'id_agente'),
        ('ciudadano_identidad_validacion', 'fkm_ciudadano_identidad_validacion_id_agente_revoca_fkey',
         'id_agente_revoca',  'agentes',                   'id_agente'),
        ('tramite_pedido_iniciador',       'fkm_tramite_pedido_iniciador_id_tramite_fkey',
         'id_tramite',        'tramite',                   'id_tramite'),
        ('tramite_pedido_iniciador',       'fkm_tramite_pedido_iniciador_id_agente_pide_fkey',
         'id_agente_pide',    'agentes',                   'id_agente'),
        ('tramite_pedido_iniciador',       'fkm_tramite_pedido_iniciador_id_agente_cancela_fkey',
         'id_agente_cancela', 'agentes',                   'id_agente'),
        ('tramite_movimiento',             'fkm_tramite_movimiento_id_ciudadano_actor_fkey',
         'id_ciudadano_actor', 'ciudadanos',               'id_ciudadano'),
        ('tramite_documento',              'fkm_tramite_documento_id_ciudadano_subio_fkey',
         'id_ciudadano_subio', 'ciudadanos',               'id_ciudadano'),
        ('tramite_documento',              'fkm_tramite_documento_id_tramite_pedido_fkey',
         'id_tramite_pedido', 'tramite_pedido_iniciador',  'id_tramite_pedido')
    ) AS v(tabla, nombre, col, destino, col_destino)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = f.nombre) THEN
            EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (id_municipio, %I) '
                           'REFERENCES %I (id_municipio, %I)',
                           f.tabla, f.nombre, f.col, f.destino, f.col_destino);
        END IF;
    END LOOP;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_tramite_movimiento_un_actor') THEN
        ALTER TABLE tramite_movimiento ADD CONSTRAINT ck_tramite_movimiento_un_actor
            CHECK (NOT (id_agente IS NOT NULL AND id_ciudadano_actor IS NOT NULL));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_tramite_documento_un_actor') THEN
        ALTER TABLE tramite_documento ADD CONSTRAINT ck_tramite_documento_un_actor
            CHECK (NOT (id_agente_subio IS NOT NULL AND id_ciudadano_subio IS NOT NULL));
    END IF;
END $$;

-- 6. CHECK ampliados (se conservan todos los valores vigentes).
ALTER TABLE tramite_movimiento DROP CONSTRAINT IF EXISTS tramite_movimiento_tipo_check;
ALTER TABLE tramite_movimiento ADD CONSTRAINT tramite_movimiento_tipo_check CHECK (tipo IN (
    'creacion', 'numeracion', 'pase', 'toma', 'liberacion', 'cambio_estado', 'transicion', 'adjunto',
    'firma_solicitada', 'firma_realizada', 'firma_rechazada', 'comentario', 'relacion', 'desistido',
    'reapertura', 'aprobacion', 'resultado', 'archivado_inactividad', 'purga_binario', 'aviso_iniciador',
    'pedido_iniciador', 'respuesta_iniciador', 'pedido_cancelado'));

ALTER TABLE ciudadano_aviso DROP CONSTRAINT IF EXISTS ck_ciudadano_aviso_tipo;
ALTER TABLE ciudadano_aviso ADD CONSTRAINT ck_ciudadano_aviso_tipo CHECK (tipo IN (
    'reclamo_estado', 'emergencia_estado', 'municipio', 'tramite_estado', 'tramite_pendiente',
    'tramite_pedido'));

-- 7. Clasificación, RLS y segunda barrera de las tablas nuevas (patrón de la 138).
INSERT INTO municipio_tabla_clase (tabla, clase, grupo, nota) VALUES
    ('ciudadano_identidad_validacion', 'operativo', 'contactos',
     'Validación presencial de identidad del vecino (trámites del vecino, mig 139).'),
    ('tramite_pedido_iniciador', 'operativo', 'operativo',
     'Pedidos del agente al iniciador de un trámite (trámites del vecino, mig 139).')
ON CONFLICT (tabla) DO UPDATE SET clase = EXCLUDED.clase, grupo = EXCLUDED.grupo, nota = EXCLUDED.nota;

DO $$
DECLARE
    t text;
    barrera CONSTANT text :=
        'id_municipio = (SELECT NULLIF(current_setting(''app.id_municipio'', true), '''')::int)';
BEGIN
    FOREACH t IN ARRAY ARRAY['ciudadano_identidad_validacion', 'tramite_pedido_iniciador'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zaris_app') THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO zaris_app', t);
            -- La secuencia del SERIAL, explícita: los privilegios por defecto de la 138 solo cubren
            -- lo que crea el rol postgres, y sin USAGE el INSERT como zaris_app falla en nextval.
            EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO zaris_app',
                           pg_get_serial_sequence('public.' || t, 'id_' || CASE t
                               WHEN 'ciudadano_identidad_validacion' THEN 'ciudadano_identidad_validacion'
                               ELSE 'tramite_pedido' END));
        END IF;
        EXECUTE format('DROP POLICY IF EXISTS barrera_municipio ON public.%I', t);
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zaris_app') THEN
            EXECUTE format('CREATE POLICY barrera_municipio ON public.%I FOR ALL TO zaris_app '
                           'USING (%s) WITH CHECK (%s)', t, barrera, barrera);
        END IF;
    END LOOP;
END $$;
