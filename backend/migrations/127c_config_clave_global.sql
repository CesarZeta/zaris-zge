-- Migración 127c — IT-01 F3, pasada de arreglos de la revisión final (I1): una clave global de
-- configuracion_general no se pisa desde un municipio.
--
-- Una clave global (id_municipio NULL, como password_renovacion_dias desde la 127b) vale para
-- todos los municipios, y leer_config prioriza la fila del municipio: si un administrador creara
-- en su municipio una fila con la misma clave, la anularía en silencio. La API lo rechaza con
-- 422 (admin_tablas.py); este trigger es la segunda barrera, para cualquier otra vía.
-- Hoy además lo frena el UNIQUE (clave) viejo, que el lote de limpieza borra antes de F4.
--
-- Sin DROP (va por MCP). Re-aplicable. Requiere la 127b: es compatible con su UPDATE, que pasa
-- la fila del municipio a global (id_municipio NULL no se controla).

CREATE OR REPLACE FUNCTION configuracion_general_clave_global()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.id_municipio IS NOT NULL AND EXISTS (
        SELECT 1 FROM configuracion_general g
         WHERE g.clave = NEW.clave AND g.id_municipio IS NULL
    ) THEN
        RAISE EXCEPTION 'La clave % es un parámetro global de todos los municipios: no se crea por municipio',
            NEW.clave USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER configuracion_general_clave_global
    BEFORE INSERT OR UPDATE OF clave, id_municipio ON configuracion_general
    FOR EACH ROW EXECUTE FUNCTION configuracion_general_clave_global();
