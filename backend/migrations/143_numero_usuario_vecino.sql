-- Migración 143 — número de usuario del vecino (PLAN_REGISTRO_PREVIO.md §6, F3)
--
-- Lo asigna el sistema cuando el vecino genera su usuario (elige la contraseña). Seis dígitos,
-- correlativo por municipio desde 100001: no se confunde con un DNI (7 u 8 dígitos), así el
-- ingreso acepta cualquiera de los dos. Las cuentas pendientes lo reciben al activarse
-- (services/cuenta_vecino.py::asignar_numero_usuario: lock + máximo + 1; no usa
-- numerador_municipio porque su CHECK de entidades exigiría un DROP).
-- Sin DROP. Idempotente.

ALTER TABLE ciudadano_credencial ADD COLUMN IF NOT EXISTS numero_usuario INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_ciudadano_credencial_numero_usuario') THEN
        ALTER TABLE ciudadano_credencial ADD CONSTRAINT ck_ciudadano_credencial_numero_usuario
            CHECK (numero_usuario IS NULL OR numero_usuario BETWEEN 100001 AND 999999);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uqmun_ciudadano_credencial_numero_usuario
    ON ciudadano_credencial (id_municipio, numero_usuario) WHERE numero_usuario IS NOT NULL;

-- Las cuentas ya activadas, en el orden en que se activaron.
UPDATE ciudadano_credencial k
   SET numero_usuario = n.numero
  FROM (SELECT c.id_ciudadano_credencial,
               COALESCE((SELECT MAX(m.numero_usuario) FROM ciudadano_credencial m
                          WHERE m.id_municipio = c.id_municipio), 100000)
               + ROW_NUMBER() OVER (PARTITION BY c.id_municipio
                                    ORDER BY c.activado_en NULLS LAST, c.id_ciudadano_credencial) AS numero
          FROM ciudadano_credencial c
         WHERE c.activado = TRUE AND c.numero_usuario IS NULL) n
 WHERE n.id_ciudadano_credencial = k.id_ciudadano_credencial;
