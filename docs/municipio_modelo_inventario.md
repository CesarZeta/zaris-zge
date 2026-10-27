# Inventario para el municipio modelo

Generado por `backend/crear_municipio_modelo.py --inventario` sobre el municipio base (Municipio Demo).
Solo catálogos (grupos `maestros` y `configuracion`): no hay datos personales. Las filas inactivas
nunca se copian. Se proponen descartar los nombres que parecen de prueba (test, prueba, qa, demo, borrar, smoke).

| Tabla | Grupo | Activas | Inactivas (no se copian) | A copiar | A descartar | Nota |
|---|---|---|---|---|---|---|
| `agenda_clase` | maestros | 4 | 1 | 4 | — |  |
| `agenda_feriado` | maestros | 12 | 0 | 12 | — |  |
| `area` | maestros | 6 | 50 | 6 | — | las 6 áreas fijas se copian siempre |
| `cargos` | maestros | 132 | 1 | 132 | — |  |
| `emergencia_canal_ingreso` | maestros | 2 | 0 | 2 | — |  |
| `emergencia_organismo_derivacion` | maestros | 12 | 0 | 12 | — |  |
| `emergencia_prioridad` | maestros | 3 | 0 | 3 | — |  |
| `emergencia_subtipo` | maestros | 147 | 0 | 147 | — |  |
| `emergencia_tipo` | maestros | 50 | 1 | 50 | — |  |
| `encuesta_opcion` | maestros | 19 | 0 | 19 | — |  |
| `encuesta_plantilla` | maestros | 4 | 0 | 4 | — |  |
| `encuesta_pregunta` | maestros | 17 | 0 | 17 | — |  |
| `equipos` | maestros | 10 | 10 | 8 | «Equipo Demo Mantenimiento»; «Mesa prueba UI T17» |  |
| `espacios_agenda` | maestros | 7 | 1 | 7 | — |  |
| `lugares_atencion` | maestros | 5 | 0 | 5 | — |  |
| `servicios` | maestros | 5 | 1 | 5 | — |  |
| `subarea` | maestros | 64 | 19 | 62 | «SMOKE96 SubA»; «SMOKE96 SubB» |  |
| `tipo_prestacion` | maestros | 6 | 7 | 4 | «SMOKE95 prestacion»; «SMOKE96 prest B» |  |
| `tipo_reclamo` | maestros | 283 | 6 | 282 | «SMOKE96 tipo B» |  |
| `tipo_tramite` | maestros | 9 | 1 | 9 | — |  |
| `tipo_tramite_aprobacion_requerida` | maestros | 0 | 0 | 0 | — |  |
| `tipo_tramite_campo` | maestros | 53 | 0 | 53 | — |  |
| `tipo_tramite_documento_requerido` | maestros | 23 | 0 | 23 | — |  |
| `tipo_tramite_estado` | maestros | 66 | 1 | 66 | — |  |
| `tipo_tramite_transicion` | maestros | 61 | 0 | 61 | — |  |
| `tipo_tramite_version` | maestros | 11 | 3 | 11 | — |  |
| `configuracion_general` | configuracion | 27 | 1 | 27 | — | se copia siempre (todas las claves, pisadas por la identidad del alta) |
| `municipio_modulo` | configuracion | 16 | 0 | 16 | — |  |
