-- Migración 145 — Catálogo de emergencias del vecino (PLAN_CATALOGO_EMERGENCIAS_VECINO.md, aprobado por
-- César el 2026-11-24).
--
-- Qué hace:
--   1. emergencia_grupo_vecino y emergencia_opcion_vecino: lo que el vecino ve y elige (grupo → opción);
--      cada opción apunta a un tipo (y, si corresponde, subtipo) del COM. Catálogo por municipio: se
--      copia en el alta y se edita en Maestros.
--   2. emergencia_evento.clasificacion_vecino: el texto de la opción elegida al reportar. Es lo que ve
--      el vecino en «Mis emergencias», aunque el COM reclasifique el evento.
--
-- Sin DROP: se aplica por MCP. Re-aplicable. Va ANTES del código. Los datos, en la 145b.

CREATE TABLE IF NOT EXISTS emergencia_grupo_vecino (
    id_emergencia_grupo_vecino SERIAL PRIMARY KEY,
    codigo                  VARCHAR(60)  NOT NULL,
    nombre                  VARCHAR(80)  NOT NULL,
    icono                   VARCHAR(30)  NOT NULL DEFAULT 'otra',
    orden                   INTEGER      NOT NULL DEFAULT 0,
    activo                  BOOLEAN      NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER      NOT NULL REFERENCES municipios(id_municipio),
    id_subarea              INTEGER      REFERENCES subarea(id_subarea),
    fecha_alta              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER      REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER      REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_emergencia_grupo_vecino_icono CHECK (icono IN (
        'salud', 'fuego', 'gas', 'arbol', 'derrumbe', 'agua', 'personas', 'animales', 'seguridad', 'otra')),
    CONSTRAINT uqmun_emergencia_grupo_vecino_codigo UNIQUE (id_municipio, codigo),
    CONSTRAINT uqm_emergencia_grupo_vecino UNIQUE (id_municipio, id_emergencia_grupo_vecino),
    CONSTRAINT fkm_emergencia_grupo_vecino_subarea FOREIGN KEY (id_municipio, id_subarea)
        REFERENCES subarea (id_municipio, id_subarea)
);

-- Único que sostiene «el subtipo es de ese tipo» (FK compuesta de la opción).
CREATE UNIQUE INDEX IF NOT EXISTS uqt_emergencia_subtipo_tipo ON emergencia_subtipo (id_tipo, id_emergencia_subtipo);

CREATE TABLE IF NOT EXISTS emergencia_opcion_vecino (
    id_emergencia_opcion_vecino SERIAL PRIMARY KEY,
    codigo                  VARCHAR(60)  NOT NULL,
    nombre                  VARCHAR(100) NOT NULL,
    -- Sin grupo: no aparece en la lista; solo se usa desde su botón SOS.
    id_grupo                INTEGER      REFERENCES emergencia_grupo_vecino(id_emergencia_grupo_vecino),
    id_tipo                 INTEGER      NOT NULL REFERENCES emergencia_tipo(id_emergencia_tipo),
    id_subtipo              INTEGER      REFERENCES emergencia_subtipo(id_emergencia_subtipo),
    boton_sos               VARCHAR(20),
    descripcion_obligatoria BOOLEAN      NOT NULL DEFAULT FALSE,
    -- Texto que ve el vecino al elegirla (por ejemplo, los teléfonos que defina el municipio).
    texto_ayuda             VARCHAR(300),
    orden                   INTEGER      NOT NULL DEFAULT 0,
    activo                  BOOLEAN      NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER      NOT NULL REFERENCES municipios(id_municipio),
    id_subarea              INTEGER      REFERENCES subarea(id_subarea),
    fecha_alta              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER      REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER      REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_emergencia_opcion_vecino_boton CHECK (boton_sos IN (
        'seguridad', 'incendio', 'asistencia', 'accidente', 'tormenta')),
    CONSTRAINT ck_emergencia_opcion_vecino_donde CHECK (id_grupo IS NOT NULL OR boton_sos IS NOT NULL),
    CONSTRAINT uqmun_emergencia_opcion_vecino_codigo UNIQUE (id_municipio, codigo),
    CONSTRAINT uqm_emergencia_opcion_vecino UNIQUE (id_municipio, id_emergencia_opcion_vecino),
    CONSTRAINT fkm_emergencia_opcion_vecino_grupo FOREIGN KEY (id_municipio, id_grupo)
        REFERENCES emergencia_grupo_vecino (id_municipio, id_emergencia_grupo_vecino),
    CONSTRAINT fkm_emergencia_opcion_vecino_tipo FOREIGN KEY (id_municipio, id_tipo)
        REFERENCES emergencia_tipo (id_municipio, id_emergencia_tipo),
    CONSTRAINT fkm_emergencia_opcion_vecino_subtipo FOREIGN KEY (id_municipio, id_subtipo)
        REFERENCES emergencia_subtipo (id_municipio, id_emergencia_subtipo),
    CONSTRAINT fkt_emergencia_opcion_vecino_subtipo FOREIGN KEY (id_tipo, id_subtipo)
        REFERENCES emergencia_subtipo (id_tipo, id_emergencia_subtipo),
    CONSTRAINT fkm_emergencia_opcion_vecino_subarea FOREIGN KEY (id_municipio, id_subarea)
        REFERENCES subarea (id_municipio, id_subarea)
);
-- Un botón SOS, una opción vigente.
CREATE UNIQUE INDEX IF NOT EXISTS uq_emergencia_opcion_vecino_boton
    ON emergencia_opcion_vecino (id_municipio, boton_sos) WHERE activo AND boton_sos IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_emergencia_opcion_vecino_grupo ON emergencia_opcion_vecino (id_grupo);

ALTER TABLE emergencia_evento ADD COLUMN IF NOT EXISTS clasificacion_vecino VARCHAR(100);
COMMENT ON COLUMN emergencia_evento.clasificacion_vecino IS
    'Opción que eligió el vecino al reportar (texto del momento). NULL en los eventos que no vienen del catálogo del vecino.';

INSERT INTO municipio_tabla_clase (tabla, clase, grupo) VALUES
    ('emergencia_grupo_vecino', 'catalogo', 'maestros'),
    ('emergencia_opcion_vecino', 'catalogo', 'maestros')
ON CONFLICT (tabla) DO NOTHING;

DO $$
DECLARE
    t text;
    barrera CONSTANT text := 'id_municipio = (SELECT NULLIF(current_setting(''app.id_municipio'', true), '''')::int)';
BEGIN
    FOREACH t IN ARRAY ARRAY['emergencia_grupo_vecino', 'emergencia_opcion_vecino'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO zaris_app', t);
        EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO zaris_app', pg_get_serial_sequence(t, 'id_' || t));
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = t
                          AND policyname = 'barrera_municipio') THEN
            EXECUTE format('CREATE POLICY barrera_municipio ON public.%I FOR ALL TO zaris_app '
                           'USING (%s) WITH CHECK (%s)', t, barrera, barrera);
        END IF;
    END LOOP;
END $$;
