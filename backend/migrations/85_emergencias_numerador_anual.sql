-- Migracion 85: Modulo Emergencias - reset anual del numero operativo.
-- Cierra el pendiente de la mig 83 ("Reset anual de la secuencia: pendiente").
--
-- En lugar de un cron que resetee la secuencia global cada 1 de enero (mas
-- piezas moviles + ventana de fallo), se reemplaza la secuencia por un
-- NUMERADOR POR ANIO con UPSERT atomico — el mismo patron ya validado de
-- tipo_tramite_numerador (CLAUDE.md s35). El reset es implicito: anio nuevo
-- => fila nueva que arranca en 1. Concurrencia: el ON CONFLICT DO UPDATE
-- serializa por fila de anio (volumen de emergencias lo tolera de sobra).
--
-- Idempotente: IF NOT EXISTS + backfill con GREATEST + CREATE OR REPLACE.

BEGIN;

CREATE TABLE IF NOT EXISTS emergencia_numerador (
    anio                INTEGER PRIMARY KEY,
    ultimo_numero       INTEGER NOT NULL DEFAULT 0,
    fecha_alta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE emergencia_numerador ENABLE ROW LEVEL SECURITY;

-- Backfill: cada anio presente en eventos arranca desde su maximo actual,
-- asi la numeracion continua sin colisiones con lo ya emitido.
INSERT INTO emergencia_numerador (anio, ultimo_numero)
SELECT CAST(substring(numero_operativo FROM 4 FOR 4) AS integer) AS anio,
       MAX(CAST(substring(numero_operativo FROM 9) AS integer))  AS ultimo
FROM emergencia_evento
WHERE numero_operativo ~ '^EM-\d{4}-\d{6}$'
GROUP BY 1
ON CONFLICT (anio) DO UPDATE
SET ultimo_numero      = GREATEST(emergencia_numerador.ultimo_numero, EXCLUDED.ultimo_numero),
    fecha_modificacion = NOW();

-- Misma funcion que ya dispara trg_numero_emergencia (mig 83): solo cambia
-- el cuerpo — ahora numera contra emergencia_numerador en vez de la secuencia.
CREATE OR REPLACE FUNCTION fn_generar_numero_emergencia()
RETURNS trigger AS $$
DECLARE
    v_anio INTEGER := CAST(EXTRACT(YEAR FROM NOW()) AS integer);
    v_num  INTEGER;
BEGIN
    IF NEW.numero_operativo IS NULL OR NEW.numero_operativo = '' THEN
        INSERT INTO emergencia_numerador (anio, ultimo_numero)
        VALUES (v_anio, 1)
        ON CONFLICT (anio) DO UPDATE
            SET ultimo_numero      = emergencia_numerador.ultimo_numero + 1,
                fecha_modificacion = NOW()
        RETURNING ultimo_numero INTO v_num;
        NEW.numero_operativo := 'EM-' || v_anio::text || '-' || lpad(v_num::text, 6, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- La secuencia global de la mig 83 ya no se usa.
DROP SEQUENCE IF EXISTS emergencia_evento_numero_seq;

COMMIT;
