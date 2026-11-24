-- Migración 145b — Datos del catálogo de emergencias del vecino (PLAN_CATALOGO_EMERGENCIAS_VECINO.md).
--
-- En cada municipio que tiene el catálogo del COM completo (el modelo y los que ya lo copiaron):
--   1. Dos tipos nuevos del COM, P1 y con aviso al 911, en la gestión y con el organismo de «Robo»:
--      «Alerta de pánico» y «Violencia familiar o de género».
--   2. Los 10 grupos y sus opciones, más la opción del SOS «Seguridad» (sin grupo: solo desde su botón).
-- Todo por código, sin ids. Re-aplicable: no pisa lo que el municipio haya cambiado.

INSERT INTO emergencia_tipo (id_subarea, codigo, nombre, descripcion, id_prioridad_default,
                             id_organismo_derivacion_default, requiere_911, es_emergencia, activo, id_municipio)
SELECT r.id_subarea, n.codigo, n.nombre, n.descripcion, p.id_emergencia_prioridad,
       r.id_organismo_derivacion_default, TRUE, TRUE, TRUE, r.id_municipio
  FROM emergencia_tipo r
  JOIN municipios m ON m.id_municipio = r.id_municipio AND m.estado <> 'baja'
  JOIN emergencia_tipo i ON i.id_municipio = r.id_municipio AND i.codigo = 'INCENDIO' AND i.activo
  JOIN emergencia_tipo e ON e.id_municipio = r.id_municipio AND e.codigo = 'EMERGENCIA_SALUD' AND e.activo
  JOIN emergencia_prioridad p ON p.id_municipio = r.id_municipio AND p.codigo = 'P1' AND p.activo
 CROSS JOIN (VALUES
    ('ALERTA_PANICO', 'Alerta de pánico', 'Alerta del botón «Seguridad» de la app del vecino.'),
    ('VIOLENCIA_FAMILIAR_GENERO', 'Violencia familiar o de género', NULL)
 ) AS n(codigo, nombre, descripcion)
 WHERE r.codigo = 'ROBO' AND r.activo
ON CONFLICT (id_subarea, codigo) DO NOTHING;

INSERT INTO emergencia_grupo_vecino (codigo, nombre, icono, orden, activo, id_municipio)
SELECT g.codigo, g.nombre, g.icono, g.orden, TRUE, t.id_municipio
  FROM emergencia_tipo t
  JOIN municipios m ON m.id_municipio = t.id_municipio AND m.estado <> 'baja'
 CROSS JOIN (VALUES
    ('SALUD_ACCIDENTES',     'Salud y accidentes',    'salud',     10),
    ('FUEGO',                'Fuego',                 'fuego',     20),
    ('GAS_SUSTANCIAS',       'Gas y sustancias',      'gas',       30),
    ('ARBOLES_CABLES',       'Árboles y cables',      'arbol',     40),
    ('DERRUMBES',            'Derrumbes',             'derrumbe',  50),
    ('AGUA_TORMENTA',        'Agua y tormenta',       'agua',      60),
    ('PERSONAS_PROBLEMAS',   'Personas en problemas', 'personas',  70),
    ('ANIMALES',             'Animales',              'animales',  80),
    ('SEGURIDAD',            'Seguridad',             'seguridad', 90),
    ('OTRA',                 'Otra emergencia',       'otra',     100)
 ) AS g(codigo, nombre, icono, orden)
 WHERE t.codigo = 'ALERTA_PANICO' AND t.activo
ON CONFLICT (id_municipio, codigo) DO NOTHING;

INSERT INTO emergencia_opcion_vecino (codigo, nombre, id_grupo, id_tipo, id_subtipo, boton_sos,
                                      descripcion_obligatoria, orden, activo, id_municipio)
SELECT o.codigo, o.nombre, g.id_emergencia_grupo_vecino, t.id_emergencia_tipo, st.id_emergencia_subtipo,
       o.boton, o.codigo = 'OTRA_EMERGENCIA', o.orden, TRUE, t.id_municipio
  FROM (VALUES
    -- código                    texto del vecino                        grupo                 tipo del COM                    subtipo                    botón SOS     orden
    ('EMERGENCIA_MEDICA',        'Emergencia médica',                    'SALUD_ACCIDENTES',   'EMERGENCIA_SALUD',             'EMERGENCIA',              'asistencia', 10),
    ('ACCIDENTE_TRANSITO',       'Accidente de tránsito',                'SALUD_ACCIDENTES',   'ACCIDENTE_VIA_PUBLICA',        NULL,                      'accidente',  20),
    ('RIESGO_VIDA',              'Riesgo de vida',                       'SALUD_ACCIDENTES',   'INTEGRIDAD_VIDA',              NULL,                      NULL,         30),
    ('INCENDIO',                 'Incendio',                             'FUEGO',              'INCENDIO',                     NULL,                      'incendio',   10),
    ('FUGA_GAS',                 'Olor o fuga de gas',                   'GAS_SUSTANCIAS',     'FUGA_GAS',                     NULL,                      NULL,         10),
    ('HUMO_OLOR_TOXICO',         'Humo u olor tóxico',                   'GAS_SUSTANCIAS',     'NUBE_TOXICA',                  NULL,                      NULL,         20),
    ('DERRAME',                  'Derrame de combustible o químicos',    'GAS_SUSTANCIAS',     'DERRAME_QUIMICO',              NULL,                      NULL,         30),
    ('ARBOL_CAIDO',              'Árbol caído',                          'ARBOLES_CABLES',     'CAIDA_ARBOL',                  NULL,                      NULL,         10),
    ('CABLES_POSTES',            'Cables o postes caídos',               'ARBOLES_CABLES',     'CAIDA_TENDIDO',                NULL,                      NULL,         20),
    ('DERRUMBE',                 'Derrumbe',                             'DERRUMBES',          'DERRUMBE',                     NULL,                      NULL,         10),
    ('INUNDACION',               'Inundación',                           'AGUA_TORMENTA',      'INUNDACION',                   NULL,                      NULL,         10),
    ('CALLE_ANEGADA',            'Calle anegada',                        'AGUA_TORMENTA',      'ANEGAMIENTO_PLUVIAL',          'CALLE',                   NULL,         20),
    ('DANIOS_TORMENTA',          'Daños por tormenta',                   'AGUA_TORMENTA',      'TORMENTA_SEVERA',              NULL,                      'tormenta',   30),
    ('ATRAPADO',                 'Persona o animal atrapado',            'PERSONAS_PROBLEMAS', 'RESCATE',                      NULL,                      NULL,         10),
    ('PERSONA_DESAPARECIDA',     'Persona perdida o desaparecida',       'PERSONAS_PROBLEMAS', 'DESAPARICION_PERSONA',         NULL,                      NULL,         20),
    ('PERSONA_ENCONTRADA',       'Encontré una persona perdida',         'PERSONAS_PROBLEMAS', 'HALLAZGO',                     'PERSONA_PERDIDA',         NULL,         30),
    ('ANIMAL_PELIGROSO',         'Animal peligroso suelto',              'ANIMALES',           'ANIMAL_PELIGROSO',             NULL,                      NULL,         10),
    ('MALTRATO_ANIMAL',          'Maltrato animal',                      'ANIMALES',           'MALTRATO_ANIMAL',              NULL,                      NULL,         20),
    ('ROBO',                     'Robo',                                 'SEGURIDAD',          'ROBO',                         NULL,                      NULL,         10),
    ('ROBO_VEHICULO',            'Robo de auto o moto',                  'SEGURIDAD',          'ROBO_AUTOMOTOR',               NULL,                      NULL,         20),
    ('VIOLENCIA_FAMILIAR_GENERO','Violencia familiar o de género',       'SEGURIDAD',          'VIOLENCIA_FAMILIAR_GENERO',    NULL,                      NULL,         30),
    ('AGRESION_SEXUAL',          'Agresión sexual',                      'SEGURIDAD',          'INTEGRIDAD_SEXUAL',            NULL,                      NULL,         40),
    ('AMENAZA',                  'Amenaza de muerte',                    'SEGURIDAD',          'INTEGRIDAD_VIDA',              'AMENAZA_MUERTE',          NULL,         50),
    ('EXTORSION',                'Amenaza o extorsión',                  'SEGURIDAD',          'EXTORSION',                    NULL,                      NULL,         60),
    ('DISPAROS',                 'Disparos',                             'SEGURIDAD',          'DISPAROS',                     NULL,                      NULL,         70),
    ('SECUESTRO',                'Secuestro o persona retenida',         'SEGURIDAD',          'PRIVACION_ILEGITIMA_LIBERTAD', 'EN_PROGRESO',             NULL,         80),
    ('INTRUSION',                'Alguien entró a una propiedad',        'SEGURIDAD',          'INTRUSION',                    NULL,                      NULL,         90),
    ('SOSPECHOSO',               'Persona o vehículo sospechoso',        'SEGURIDAD',          'SOSPECHOSO',                   NULL,                      NULL,        100),
    ('DISTURBIOS',               'Disturbios en la calle',               'SEGURIDAD',          'CONTRAVENTORES',               'DESORDEN_VIA_PUBLICA',    NULL,        110),
    ('AMENAZA_BOMBA',            'Amenaza de bomba',                     'SEGURIDAD',          'EXPLOSIVOS',                   'AMENAZA_BOMBA',           NULL,        120),
    ('OBJETO_SOSPECHOSO',        'Objeto sospechoso',                    'SEGURIDAD',          'HALLAZGO',                     'OBJETO_DUDOSO_PELIGROSO', NULL,        130),
    ('ALARMA',                   'Suena una alarma',                     'SEGURIDAD',          'ALARMAS',                      NULL,                      NULL,        140),
    ('DROGAS',                   'Venta o consumo de drogas',            'SEGURIDAD',          'DROGAS_ILICITAS',              NULL,                      NULL,        150),
    ('OTRA_EMERGENCIA',          'Otra emergencia',                      'OTRA',               'PEDIDO_GENERICO_AUXILIO',      NULL,                      NULL,         10),
    ('ALERTA_PANICO',            'Alerta de pánico',                     NULL,                 'ALERTA_PANICO',                NULL,                      'seguridad',  10)
  ) AS o(codigo, nombre, grupo, tipo, subtipo, boton, orden)
  JOIN emergencia_tipo t ON t.codigo = o.tipo AND t.activo
  JOIN municipios m ON m.id_municipio = t.id_municipio AND m.estado <> 'baja'
  JOIN emergencia_tipo pan ON pan.id_municipio = t.id_municipio AND pan.codigo = 'ALERTA_PANICO' AND pan.activo
  LEFT JOIN emergencia_grupo_vecino g ON g.id_municipio = t.id_municipio AND g.codigo = o.grupo
  LEFT JOIN emergencia_subtipo st ON st.id_tipo = t.id_emergencia_tipo AND st.codigo = o.subtipo AND st.activo
 WHERE o.grupo IS NULL OR g.id_emergencia_grupo_vecino IS NOT NULL
ON CONFLICT (id_municipio, codigo) DO NOTHING;
