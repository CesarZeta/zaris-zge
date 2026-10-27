-- Migración 130b — IT-01 F4+F5: estado del municipio, países, módulos por municipio, áreas
-- fijas, grupos de vaciado, invitaciones y tareas asíncronas.
-- Plan: PLAN_MULTI_MUNICIPIO_F4_F5.md, Tarea 4. Spec: PLAN_MULTI_MUNICIPIO_F4_F5_DISENO.md §4.
-- Requiere la 130. Los datos (y los CHECK que dependen de ellos) van en la 130c.
--
-- Sin DROP (va por MCP). Re-aplicable. Compatible con el código viejo: `activo` sigue existiendo y
-- el trigger de estado traduce un cambio de `activo` hecho por código viejo a su estado.

-- 1. Países (global): cómo se llama cada nivel y si se pueden dar de alta municipios.
CREATE TABLE IF NOT EXISTS paises (
    codigo_pais             CHAR(2)      PRIMARY KEY,
    nombre                  VARCHAR(80)  NOT NULL,
    etiqueta_nivel_1        VARCHAR(40)  NOT NULL,
    etiqueta_nivel_2        VARCHAR(40)  NOT NULL,
    zona_horaria            VARCHAR(64)  NOT NULL,
    habilitado_para_alta    BOOLEAN      NOT NULL DEFAULT FALSE,
    activo                  BOOLEAN      NOT NULL DEFAULT TRUE,
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL
);
COMMENT ON TABLE paises IS 'Catálogo global de países (IT-01 F4): etiquetas de nivel y habilitación para el alta.';
ALTER TABLE paises ENABLE ROW LEVEL SECURITY;

-- 2. Estado del municipio, provincia, tope de cuentas.
ALTER TABLE municipios
    ADD COLUMN IF NOT EXISTS estado               VARCHAR(20) NOT NULL DEFAULT 'puesta_en_marcha',
    ADD COLUMN IF NOT EXISTS fue_produccion       BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS estado_antes_baja    VARCHAR(20),
    ADD COLUMN IF NOT EXISTS max_usuarios_activos INTEGER,
    ADD COLUMN IF NOT EXISTS id_provincia         INTEGER REFERENCES provincias (id_provincia),
    ADD COLUMN IF NOT EXISTS id_partido           INTEGER REFERENCES partidos (id_partido);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_municipios_estado') THEN
        ALTER TABLE municipios ADD CONSTRAINT ck_municipios_estado CHECK
            (estado IN ('puesta_en_marcha', 'produccion', 'demo', 'modelo', 'baja'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_municipios_estado_antes_baja') THEN
        ALTER TABLE municipios ADD CONSTRAINT ck_municipios_estado_antes_baja CHECK
            (estado_antes_baja IS NULL OR estado_antes_baja IN ('puesta_en_marcha', 'produccion', 'demo', 'modelo'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_municipios_max_usuarios') THEN
        ALTER TABLE municipios ADD CONSTRAINT ck_municipios_max_usuarios CHECK
            (max_usuarios_activos IS NULL OR max_usuarios_activos > 0);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_municipio_modelo ON municipios ((true)) WHERE estado = 'modelo';

-- `activo` se deriva del estado; `fue_produccion` no vuelve a false; la baja recuerda el estado
-- anterior para reactivar. Código viejo que cambia solo `activo`: false = baja, true = reactivar.
CREATE OR REPLACE FUNCTION municipios_estado_sync()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.estado IS NOT DISTINCT FROM OLD.estado
       AND NEW.activo IS DISTINCT FROM OLD.activo THEN
        IF NOT NEW.activo THEN
            NEW.estado := 'baja';
        ELSIF OLD.estado = 'baja' THEN
            NEW.estado := COALESCE(OLD.estado_antes_baja, 'puesta_en_marcha');
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.estado = 'baja' AND OLD.estado <> 'baja' THEN
        NEW.estado_antes_baja := OLD.estado;
    ELSIF NEW.estado <> 'baja' THEN
        NEW.estado_antes_baja := NULL;
    END IF;
    NEW.activo := NEW.estado <> 'baja';
    IF NEW.estado = 'produccion' OR (TG_OP = 'UPDATE' AND OLD.fue_produccion) THEN
        NEW.fue_produccion := TRUE;
    END IF;
    RETURN NEW;
END;
$$;
CREATE OR REPLACE TRIGGER municipios_estado_sync BEFORE INSERT OR UPDATE ON municipios
    FOR EACH ROW EXECUTE FUNCTION municipios_estado_sync();

-- La provincia tiene que ser del país del municipio, y el partido de esa provincia.
CREATE OR REPLACE FUNCTION municipios_provincia_pais()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.id_provincia IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM provincias WHERE id_provincia = NEW.id_provincia AND codigo_pais = NEW.codigo_pais) THEN
        RAISE EXCEPTION 'La provincia no es del país del municipio' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.id_partido IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM partidos WHERE id_partido = NEW.id_partido AND id_provincia = NEW.id_provincia) THEN
        RAISE EXCEPTION 'El partido no es de la provincia del municipio' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE OR REPLACE TRIGGER municipios_provincia_pais BEFORE INSERT OR UPDATE ON municipios
    FOR EACH ROW EXECUTE FUNCTION municipios_provincia_pais();

-- 3. Módulos por municipio (catálogo). `modulos` sigue global y es el valor por defecto del alta.
CREATE TABLE IF NOT EXISTS municipio_modulo (
    id_municipio_modulo     SERIAL       PRIMARY KEY,
    modulo_codigo           VARCHAR(50)  NOT NULL REFERENCES modulos (modulo_codigo) ON UPDATE CASCADE,
    habilitado              BOOLEAN      NOT NULL,
    min_nivel_acceso        SMALLINT     NOT NULL CONSTRAINT ck_municipio_modulo_nivel
                                         CHECK (min_nivel_acceso BETWEEN 0 AND 5),
    activo                  BOOLEAN      NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER      NOT NULL REFERENCES municipios (id_municipio),
    id_subarea              INTEGER,
    fecha_alta              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL,
    CONSTRAINT uqmun_municipio_modulo UNIQUE (id_municipio, modulo_codigo)
);
COMMENT ON TABLE municipio_modulo IS 'Módulos habilitados y nivel mínimo por municipio (IT-01 F4). Habilitar: solo el super.';
ALTER TABLE municipio_modulo ENABLE ROW LEVEL SECURITY;

-- 4. Áreas fijas del sistema: se renombran, no se dan de baja ni se borran.
ALTER TABLE area ADD COLUMN IF NOT EXISTS es_sistema BOOLEAN NOT NULL DEFAULT FALSE;

CREATE OR REPLACE FUNCTION area_sistema_no_baja()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.es_sistema AND (TG_OP = 'DELETE' OR NOT NEW.activo OR NOT NEW.es_sistema) THEN
        RAISE EXCEPTION 'Es un área fija del sistema: se puede renombrar, no dar de baja.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;
CREATE OR REPLACE TRIGGER area_sistema_no_baja BEFORE UPDATE OR DELETE ON area
    FOR EACH ROW EXECUTE FUNCTION area_sistema_no_baja();

-- 5. Grupo de vaciado de cada tabla no global (se carga y se valida en la 130c).
ALTER TABLE municipio_tabla_clase ADD COLUMN IF NOT EXISTS grupo VARCHAR(20);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_municipio_tabla_clase_grupo') THEN
        ALTER TABLE municipio_tabla_clase ADD CONSTRAINT ck_municipio_tabla_clase_grupo CHECK
            (grupo IS NULL OR grupo IN ('operativo', 'contactos', 'maestros', 'usuarios', 'configuracion'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_municipio_tabla_clase_grupo_requerido') THEN
        ALTER TABLE municipio_tabla_clase ADD CONSTRAINT ck_municipio_tabla_clase_grupo_requerido CHECK
            (clase = 'global' OR grupo IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- 6. Invitaciones (primer administrador de un municipio, super administradores): el token se
--    guarda hasheado, vale 72 h y una sola vez.
CREATE TABLE IF NOT EXISTS usuario_invitacion (
    id_invitacion   BIGSERIAL    PRIMARY KEY,
    id_usuario      INTEGER      NOT NULL REFERENCES usuarios (id_usuario) ON DELETE CASCADE,
    id_municipio    INTEGER      REFERENCES municipios (id_municipio),
    token_hash      TEXT         NOT NULL UNIQUE,
    vence_en        TIMESTAMPTZ  NOT NULL,
    usada_en        TIMESTAMPTZ,
    id_usuario_alta INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL,
    activo          BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_alta      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE usuario_invitacion IS 'Invitaciones a elegir la clave (IT-01 F4). id_municipio NULL = super administrador.';
CREATE INDEX IF NOT EXISTS ix_usuario_invitacion_usuario ON usuario_invitacion (id_usuario);
ALTER TABLE usuario_invitacion ENABLE ROW LEVEL SECURITY;

-- 7. Tareas asíncronas del super (alta, exportación, vaciado) y retención de las exportaciones.
CREATE TABLE IF NOT EXISTS municipio_tarea (
    id_tarea           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    id_municipio       INTEGER      REFERENCES municipios (id_municipio),
    tipo               VARCHAR(20)  NOT NULL CONSTRAINT ck_municipio_tarea_tipo
                                    CHECK (tipo IN ('alta', 'exportacion', 'vaciado')),
    estado             VARCHAR(20)  NOT NULL DEFAULT 'pendiente' CONSTRAINT ck_municipio_tarea_estado
                                    CHECK (estado IN ('pendiente', 'corriendo', 'ok', 'error')),
    detalle            JSONB,
    archivo            VARCHAR(300),
    vence_en           TIMESTAMPTZ,
    id_usuario_alta    INTEGER      REFERENCES usuarios (id_usuario) ON DELETE SET NULL,
    fecha_alta         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_modificacion TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE municipio_tarea IS 'Estado de las tareas asíncronas del super (IT-01 F4) y vencimiento de exportaciones.';
CREATE INDEX IF NOT EXISTS ix_municipio_tarea_mun ON municipio_tarea (id_municipio, tipo, fecha_alta DESC);
ALTER TABLE municipio_tarea ENABLE ROW LEVEL SECURITY;

-- 8. Clasificación de las tablas nuevas.
INSERT INTO municipio_tabla_clase (tabla, clase, grupo, nota) VALUES
    ('paises', 'global', NULL, 'catálogo de países; lo edita solo el super'),
    ('municipio_modulo', 'catalogo', 'configuracion', 'no se vacía'),
    ('usuario_invitacion', 'mixta', 'usuarios', 'NULL = invitación de un super administrador'),
    ('municipio_tarea', 'mixta', 'configuracion', 'no se vacía: guarda el resguardo previo al vaciado')
ON CONFLICT (tabla) DO UPDATE
    SET clase = EXCLUDED.clase, grupo = EXCLUDED.grupo, nota = EXCLUDED.nota, fecha_modificacion = NOW();
