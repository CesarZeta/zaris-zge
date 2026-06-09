-- Migración 79 — Alta pública de vecinos en DOS PASOS (Fase 4 del roadmap de
-- integridad de cuentas).
--
-- El autoregistro del vecino se separa en dos momentos:
--   Paso 1: crear CUENTA (email + password + DNI + nombre + apellido) → verificar email.
--   Paso 2: completar la FICHA real (sexo, fecha nac, nacionalidad, CUIL, domicilio…),
--           ya verificado y logueado.
--
-- Dos marcas nuevas:
--   - ciudadanos.ficha_completa: FALSE tras el paso 1 (cuenta creada, ficha mínima
--     con placeholders), TRUE cuando el vecino completa su ficha real en el paso 2.
--     El portal del vecino la consulta al loguear: si FALSE, lo lleva a completar.
--   - ciudadano_credencial.debe_cambiar_password: para el Camino B (alta por un agente
--     municipal): el agente crea la cuenta con una clave temporal y esta marca queda
--     TRUE; el vecino la cambia en su primer ingreso (espeja usuarios.debe_cambiar_password
--     de la mig 78). En el autoregistro (Camino A) queda FALSE: el vecino eligió su clave.
--
-- Idempotente. Aplicar en local Y prod.

ALTER TABLE ciudadanos
    ADD COLUMN IF NOT EXISTS ficha_completa BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE ciudadano_credencial
    ADD COLUMN IF NOT EXISTS debe_cambiar_password BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN ciudadanos.ficha_completa IS
    'TRUE = el vecino completó su ficha real (paso 2 del alta pública). FALSE = solo se cargó el mínimo del paso 1 (cuenta).';
COMMENT ON COLUMN ciudadano_credencial.debe_cambiar_password IS
    'TRUE = el vecino tiene una clave temporal (alta por agente, Camino B) y debe cambiarla en su primer ingreso. FALSE en autoregistro (el vecino eligió su clave).';

-- Backfill coherente para los registros existentes: los vecinos ya verificados que
-- tienen datos reales cargados (los que entraron por el alta-de-una vieja) se marcan
-- ficha_completa=TRUE para no forzarlos a recompletar. Heurística: tienen fecha_nac
-- distinta del placeholder y domicilio cargado.
UPDATE ciudadanos
   SET ficha_completa = TRUE
 WHERE ficha_completa = FALSE
   AND estado_validacion = 'verificado'
   AND fecha_nac IS NOT NULL
   AND fecha_nac <> DATE '1900-01-01'
   AND calle IS NOT NULL AND calle <> '';
