-- Migración 140 — solo datos. El tipo «inscripción Profesional» (cargado así en San Andrés)
-- pasa a «Inscripción profesional», como el resto de los nombres del catálogo. Lo ve el vecino
-- en el portal desde la fase 1 de trámites del vecino. Re-aplicable: solo toca el nombre exacto.
UPDATE tipo_tramite
   SET nombre = 'Inscripción profesional',
       fecha_modificacion = NOW()
 WHERE codigo = 'inscripcion-profesional'
   AND nombre = 'inscripción Profesional';
