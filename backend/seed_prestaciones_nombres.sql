-- Acentos y mayúsculas de las prestaciones del municipio de demostración (César, 2026-11-23). Solo datos, idempotente.
UPDATE tipo_prestacion t SET nombre = v.nuevo, descripcion = v.descr, fecha_modificacion = NOW()
  FROM (VALUES
    ('Atencion medica - Odontologia',     'Atención médica - Odontología',     'Consulta odontológica con profesional asignado'),
    ('Atencion medica - Clinica general', 'Atención médica - Clínica general', 'Consulta de clínica general'),
    ('Atencion - Sala de Odontologia',    'Atención - Sala de Odontología',    'Atención odontológica en la sala municipal (varios profesionales)'),
    ('Reserva - Salon de Usos Multiples', 'Reserva - Salón de Usos Múltiples', 'Reserva del salón para actividades comunitarias'),
    ('INSCRIPCION PROFESIONAL',           'Inscripción profesional',           'Turno para firma')
  ) AS v(viejo, nuevo, descr), municipios m
 WHERE m.direccion_base AND t.id_municipio = m.id_municipio AND t.nombre = v.viejo;
