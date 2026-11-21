-- Migración 139b — Trámites del vecino: solo datos. Requiere la 139.
-- Ofrece al vecino los seis tipos de trámite que se habilitan en la fase 1, en todos los
-- municipios. No prende exige_identidad_validada en ninguno. Re-aplicable.
UPDATE tipo_tramite
   SET ofrecer_al_vecino = TRUE
 WHERE codigo IN ('aviso-obra', 'poda-arbol', 'inscripcion-profesional', 'exencion-tasas',
                  'permiso-espacio-publico', 'recurso-administrativo')
   AND ofrecer_al_vecino IS DISTINCT FROM TRUE;
