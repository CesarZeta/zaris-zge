-- Vacunación en el municipio de demostración (César, 2026-11-23). Solo datos, idempotente, por nombre.
-- Municipio = el de direccion_base. Gestión = «Clínica médica» del área indicada por id_area_salud.
INSERT INTO espacios_agenda (nombre, descripcion, direccion, capacidad_personas, atendido, activo, id_municipio, id_subarea, prefijo_colero)
SELECT 'Vacunatorio Municipal', 'Aplicación de vacunas con turno', 'Av. Mitre 100', 1, FALSE, TRUE, m.id_municipio, s.id_subarea, 'VAC'
  FROM municipios m JOIN subarea s ON s.id_municipio = m.id_municipio AND s.activo AND s.nombre = 'Clínica médica'
  JOIN area a ON a.id_area = s.id_area AND a.activo AND a.nombre = 'Secretaría de Salud'
 WHERE m.direccion_base AND NOT EXISTS (SELECT 1 FROM espacios_agenda e WHERE e.id_municipio = m.id_municipio AND e.nombre = 'Vacunatorio Municipal');
INSERT INTO disponibilidad_recurso (tipo_recurso, id_recurso, dias_semana, hora_inicio, hora_fin, etiqueta, activo, id_municipio, id_subarea)
SELECT 'espacio', e.id_espacio, 31, '08:00', '14:00', 'Horario de atención', TRUE, e.id_municipio, e.id_subarea
  FROM espacios_agenda e JOIN municipios m ON m.id_municipio = e.id_municipio AND m.direccion_base
 WHERE e.nombre = 'Vacunatorio Municipal' AND NOT EXISTS (SELECT 1 FROM disponibilidad_recurso d WHERE d.tipo_recurso = 'espacio' AND d.id_recurso = e.id_espacio);
INSERT INTO tipo_prestacion (nombre, descripcion, clase, duracion_min, tipo_recurso, id_espacio, id_espacio_ubicacion, registra_atencion, activo, id_municipio, id_subarea)
SELECT 'Vacunación', 'Aplicación de vacunas con turno', 'atencion', 15, 'espacio', e.id_espacio, e.id_espacio, TRUE, TRUE, e.id_municipio, e.id_subarea
  FROM espacios_agenda e JOIN municipios m ON m.id_municipio = e.id_municipio AND m.direccion_base
 WHERE e.nombre = 'Vacunatorio Municipal' AND NOT EXISTS (SELECT 1 FROM tipo_prestacion t WHERE t.id_municipio = e.id_municipio AND t.nombre = 'Vacunación');
