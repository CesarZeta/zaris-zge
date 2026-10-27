# Inventario para el municipio modelo

IT-01 F4+F5, Tarea 12. Relevado el 2026-10-27 sobre San Andrés en prod (solo lectura). Solo
catálogos (grupos `maestros` y `configuracion`): no hay datos personales. Las filas inactivas nunca se
copian. El modelo no es lo que recibe cada municipio: en cada alta el super elige con casillas qué
catálogos copia del modelo.

## Decisión de César (2026-10-27): genéricos + trámites

| Catálogo | Filas activas en prod | Al modelo |
|---|---|---|
| Áreas fijas (`area`, `es_sistema`) y subáreas (`subarea`) | 6 + 62 | sí |
| Cargos (`cargos`) | 131 | sí |
| Tipos de reclamo (`tipo_reclamo`) | 282 | sí |
| Emergencias (`emergencia_tipo`, `_subtipo`, `_organismo_derivacion`, `_prioridad`, `_canal_ingreso`) | 50 · 147 · 12 · 3 · 2 | sí |
| Encuestas (`encuesta_plantilla`, `_pregunta`, `_opcion`) | 4 · 17 · 19 | sí |
| Clases de agenda (`agenda_clase`) | 4 | sí |
| Feriados (`agenda_feriado`) | 12 | sí |
| Configuración (`configuracion_general`) | 28 | sí (todas las claves; el alta las pisa con la identidad del municipio) |
| Tipos de trámite (`tipo_tramite` y sus versiones, campos, estados, transiciones, documentos y aprobaciones) | 15 | sí, menos «Permiso de Demostracion E2E» y «inscripción Profesional» (sus 4 aprobaciones son de un agente de San Andrés, que no pasa al modelo; César, corte B del 2026-10-27) |
| Espacios (`espacios_agenda`) | 8 | no: propios de San Andrés |
| Lugares de atención (`lugares_atencion`) | 5 | no: propios de San Andrés |
| Servicios (`servicios`) | 5 | no: propios de San Andrés |
| Prestaciones (`tipo_prestacion`) | 5 | no: dependen de los espacios |
| Equipos (`equipos`) | 7 | no: propios de San Andrés (incluye «Equipo Demo Mantenimiento») |

Sin el espacio «Guardia», el municipio nuevo arma el suyo al configurar la Guardia (la clave
`id_espacio_guardia` queda vacía y la Guardia no se ofrece hasta configurarla).

Las exclusiones que aplica `backend/crear_municipio_modelo.py --aplicar` están en
`backend/municipio_modelo_exclusiones.json`. `--inventario` imprime el relevamiento sin pisar este
documento (con `--salida <archivo>` lo escribe en otro lado).
