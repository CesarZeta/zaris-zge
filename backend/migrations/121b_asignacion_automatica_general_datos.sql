-- Migracion 121b — Datos de la 121 (2026-10-23).
--
-- Traduce el estado anterior SIN cambiar que gestion asigna sola: la general
-- queda prendida y toda gestion que no tenia el tilde viejo pasa a ser la
-- excepcion que asigna a mano (en prod solo Alumbrado Publico sigue asignando
-- sola; en local ninguna). Corre una sola vez: si la clave ya existe no toca nada
-- (re-aplicarla no pisa lo que el admin cambio despues).
--
-- configuracion_general: tipo y activo explicitos (prod los tiene NOT NULL sin
-- default, CLAUDE.md §21).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM configuracion_general WHERE clave = 'reclamos_asignacion_automatica') THEN
    UPDATE subarea SET asignacion_manual = NOT asignacion_automatica;
    INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo)
    VALUES ('reclamos_asignacion_automatica', 'true', 'boolean',
            'Asignación automática de reclamos para todo el municipio. Las gestiones marcadas «Asigna a mano» en Maestros → Subáreas quedan afuera.',
            TRUE);
  END IF;
END $$;
