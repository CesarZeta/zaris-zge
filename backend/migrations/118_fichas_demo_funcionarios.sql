-- Migracion 118 — Ficha en la BUC para cada funcionario que no la tiene (2026-10-21)
--
-- Decision de Cesar (2026-10-21): todo funcionario existe primero como persona en
-- la BUC (circuito de cuentas desde la ficha, mig 110). En la demo, 91 de las 93
-- personas con usuario + agente no tenian ficha y ninguna coincidia por email o
-- DNI con una existente: se les crea una ficha DEMO con los datos que hay (nombre,
-- apellido, email de la cuenta, telefono del agente si tiene) y el resto ficticio:
--   - DNI en el rango reservado 99.000.000 + id_agente (marca de origen: ningun
--     DNI real de la BUC esta en ese rango; verificado en prod y local).
--   - CUIL valido (digito verificador) con prefijo 23/24.
--   - sexo 'OTROS' (el agente no tiene el dato y no se deduce del nombre).
--   - fecha de nacimiento ficticia, nacionalidad Argentina.
-- Despues se vincula usuarios.id_ciudadano y el agente toma los datos de la ficha
-- (la ficha es la unica fuente, services/cuenta_zaris.py). Sin credencial de App
-- Vecinos ni mails: es un alta por datos, no por la API.
--
-- Solo datos e idempotente (solo toca personas sin ficha). Backup en prod:
-- _backup_fichas_funcionarios_2026_10_21.

CREATE OR REPLACE FUNCTION pg_temp.cuil_demo(dni TEXT) RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    pref TEXT;
    base TEXT;
    pesos INT[] := ARRAY[5,4,3,2,7,6,5,4,3,2];
    s INT; r INT; i INT;
BEGIN
    FOREACH pref IN ARRAY ARRAY['23','24'] LOOP
        base := pref || dni;
        s := 0;
        FOR i IN 1..10 LOOP
            s := s + substr(base, i, 1)::INT * pesos[i];
        END LOOP;
        r := 11 - (s % 11);
        IF r = 11 THEN r := 0; END IF;
        IF r <> 10 THEN RETURN base || r::TEXT; END IF;
    END LOOP;
    RETURN NULL;
END $$;

WITH sin_ficha AS (
    SELECT a.id_agente, a.nombre, a.apellido, a.telefono, u.id_usuario, u.email,
           (99000000 + a.id_agente)::TEXT AS dni
    FROM agentes a
    JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo = TRUE
    WHERE a.activo = TRUE AND u.id_ciudadano IS NULL
      AND u.email IS NOT NULL AND u.email <> ''
      AND NOT EXISTS (SELECT 1 FROM ciudadanos c WHERE LOWER(c.email) = LOWER(u.email))
),
nuevas AS (
    -- ren_chk/email_chk/emp_chk explícitos: en local son NOT NULL SIN default (drift §24).
    INSERT INTO ciudadanos (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac,
                            id_nacionalidad, telefono, email, es_funcionario, ficha_completa,
                            estado_validacion, activo, ren_chk, email_chk, emp_chk)
    SELECT 'DNI', s.dni, pg_temp.cuil_demo(s.dni),
           COALESCE(NULLIF(TRIM(s.nombre), ''), 'Sin nombre'),
           COALESCE(NULLIF(TRIM(s.apellido), ''), 'Sin apellido'),
           'OTROS',
           DATE '1975-01-01' + ((s.id_agente * 211) % 9000),
           (SELECT id FROM nacionalidades WHERE pais ILIKE 'Argentina' ORDER BY id LIMIT 1),
           COALESCE(NULLIF(regexp_replace(COALESCE(s.telefono, ''), '[^0-9]', '', 'g'), ''),
                    '115' || lpad(s.id_agente::TEXT, 7, '0')),
           LOWER(s.email), TRUE, TRUE, 'verificado', TRUE, FALSE, FALSE, FALSE
    FROM sin_ficha s
    WHERE NOT EXISTS (SELECT 1 FROM ciudadanos c WHERE c.doc_tipo = 'DNI' AND c.doc_nro = s.dni)
    RETURNING id_ciudadano, doc_nro
)
UPDATE usuarios u
   SET id_ciudadano = n.id_ciudadano, fecha_modif = NOW()
  FROM nuevas n
  JOIN agentes a ON (99000000 + a.id_agente)::TEXT = n.doc_nro
 WHERE u.id_usuario = a.id_usuario AND u.id_ciudadano IS NULL;

-- El agente toma los datos de su ficha (misma regla que sincronizar_agente_desde_ficha).
UPDATE agentes a
   SET nombre = c.nombre, apellido = c.apellido, dni = c.doc_nro, cuil = c.cuil,
       email = c.email, telefono = c.telefono, fecha_modificacion = NOW()
  FROM usuarios u
  JOIN ciudadanos c ON c.id_ciudadano = u.id_ciudadano
 WHERE u.id_usuario = a.id_usuario AND a.activo = TRUE
   AND c.doc_nro ~ '^99[0-9]{6}$'
   AND (a.dni IS DISTINCT FROM c.doc_nro OR a.cuil IS DISTINCT FROM c.cuil
        OR a.email IS DISTINCT FROM c.email OR a.telefono IS DISTINCT FROM c.telefono);
