-- Migración 146 — El subtipo «Objeto dudoso / peligroso» de Hallazgo pasa a prioridad P2 (César, 2026-11-24).
-- El tipo Hallazgo sigue en P3. Solo datos, por código, en los municipios vigentes y en el modelo. Re-aplicable.
-- Rige para los eventos nuevos (app del vecino y recepción del COM); los existentes no cambian.

UPDATE emergencia_subtipo s
   SET id_prioridad_override = p.id_emergencia_prioridad, fecha_modificacion = NOW()
  FROM emergencia_tipo t, emergencia_prioridad p, municipios m
 WHERE t.id_emergencia_tipo = s.id_tipo AND t.codigo = 'HALLAZGO'
   AND s.codigo = 'OBJETO_DUDOSO_PELIGROSO' AND s.id_prioridad_override IS NULL
   AND p.id_municipio = s.id_municipio AND p.codigo = 'P2' AND p.activo
   AND m.id_municipio = s.id_municipio AND m.estado <> 'baja';
