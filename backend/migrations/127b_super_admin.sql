-- Migración 127b — IT-01 F3: registro de accesos del super administrador, módulo Municipios y
-- renovación de claves global. Plan: PLAN_MULTI_MUNICIPIO_F3.md, Tarea 1. Requiere la 127.
--
-- Sin DROP (va por MCP). Re-aplicable. Compatible con el código viejo: la tabla nueva no la
-- usa nadie todavía, el módulo `municipios` (min 0) no lo ve ningún nivel 1-5, y
-- leer_config cae en la fila global de password_renovacion_dias.

-- 1. Registro de accesos del super administrador (append-only). Un registro, como
--    historia_clinica_acceso y usuario_login_log: sin los campos estándar de §10.
CREATE TABLE IF NOT EXISTS super_admin_acceso (
    id_super_admin_acceso BIGSERIAL PRIMARY KEY,
    id_usuario            INTEGER       NOT NULL REFERENCES usuarios (id_usuario),
    id_municipio          INTEGER       REFERENCES municipios (id_municipio),
    accion                VARCHAR(30)   NOT NULL,
    metodo                VARCHAR(10),
    ruta                  VARCHAR(300),
    detalle               TEXT,
    ip                    VARCHAR(64),
    user_agent            VARCHAR(1000),
    fecha_hora            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_super_admin_acceso_accion CHECK (accion IN
        ('login', 'seleccion', 'request', 'historia_clinica', 'config_global',
         'municipio_editar', 'catalogo_global'))
);
COMMENT ON TABLE super_admin_acceso IS
    'Cada acceso del super administrador (IT-01 F3). id_municipio NULL = acción global. Append-only.';
CREATE INDEX IF NOT EXISTS ix_super_admin_acceso_mun_fecha ON super_admin_acceso (id_municipio, fecha_hora DESC);
ALTER TABLE super_admin_acceso ENABLE ROW LEVEL SECURITY;

-- Por sentencia (no por fila): frena también un DELETE o un TRUNCATE sobre la tabla vacía.
CREATE OR REPLACE FUNCTION super_admin_acceso_no_mutate()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'super_admin_acceso es append-only';
END;
$$;
CREATE OR REPLACE TRIGGER super_admin_acceso_no_update BEFORE UPDATE ON super_admin_acceso
    FOR EACH STATEMENT EXECUTE FUNCTION super_admin_acceso_no_mutate();
CREATE OR REPLACE TRIGGER super_admin_acceso_no_delete BEFORE DELETE ON super_admin_acceso
    FOR EACH STATEMENT EXECUTE FUNCTION super_admin_acceso_no_mutate();
CREATE OR REPLACE TRIGGER super_admin_acceso_no_truncate BEFORE TRUNCATE ON super_admin_acceso
    FOR EACH STATEMENT EXECUTE FUNCTION super_admin_acceso_no_mutate();

INSERT INTO municipio_tabla_clase (tabla, clase, nota) VALUES
    ('super_admin_acceso', 'mixta', 'NULL = acción global del super administrador; append-only; no se vacía (F4)')
ON CONFLICT (tabla) DO UPDATE
    SET clase = EXCLUDED.clase, nota = EXCLUDED.nota, fecha_modificacion = NOW();

-- 2. Módulo exclusivo del super administrador (min_nivel_acceso 0, permitido por la 127).
INSERT INTO modulos (modulo_codigo, nombre, descripcion, min_nivel_acceso, activo)
VALUES ('municipios', 'Municipios', 'Edición de los municipios (solo el super administrador)', 0, TRUE)
ON CONFLICT (modulo_codigo) DO NOTHING;

-- 3. La renovación de claves es un parámetro de seguridad global (spec §4): ningún municipio
--    lo sobrescribe. Pasa la fila del municipio 1 a global, si todavía no hay una global.
UPDATE configuracion_general
   SET id_municipio = NULL, fecha_modificacion = NOW()
 WHERE clave = 'password_renovacion_dias' AND id_municipio = 1
   AND NOT EXISTS (SELECT 1 FROM configuracion_general g
                    WHERE g.clave = 'password_renovacion_dias' AND g.id_municipio IS NULL);
