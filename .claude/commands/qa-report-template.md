# qa-report-template

Convención y template para reportes QA del proyecto. Usar este formato cuando un usuario o tester (humano o agente IA) entrega resultados de pruebas manuales, y guardar el reporte a disco.

## Cuándo usar

- El usuario pega en el chat un reporte de pruebas con casos PASS/FAIL/PARCIAL/OBS.
- Se diseña una tanda de pruebas a ejecutar (manual o por subagent QA).
- Hay que documentar resultados de validación visual de un módulo nuevo.

## Convención de naming

```
reporte_pruebas_<bloque>_YYYY-MM-DD.md
```

en la **raíz del repo** (no en subcarpetas). Ejemplos reales:
- `reporte_pruebas_bloque_A_2026-05-11.md` (Agenda React)
- `reporte_pruebas_bloques_D_y_C_2026-05-11.md` (OTs vanilla + Reclamos vanilla)

Si se ejecutan dos bloques en una misma corrida, juntarlos en un solo archivo (`bloques_X_y_Y`).

## Estructura del reporte

### Encabezado
```markdown
# Reporte de Pruebas — Bloque X · Módulo Y

**Fecha:** YYYY-MM-DD
**Tester:** quien probó (humano: nombre / agente: "Claude (QA agent)")
**Entorno:** URL local o prod, versión, seeds aplicados
**Login auto:** usuario con el que arrancó la sesión
**Duración aprox.:** N min
```

### Servicios verificados (tabla)
URL + resultado de smoke check antes de empezar (backend up, frontend serving, etc.).

### Resumen ejecutivo (tabla)
Por subsección: PASS / FAIL / PARCIAL / OBS / N/A / Total. Más una línea final con el total y el estado global (🟢 sin regresiones críticas, 🟡 con bugs medios, 🔴 bugs críticos).

### Detalle por caso (tabla por subsección)
Una fila por caso. Columnas: ID del caso (ej. `D-SUP-01`) · Resultado (✅ PASS / ❌ FAIL / 🟡 PARCIAL / 🔵 OBS / ⚪ N/A) · Observación (1-2 frases).

### Bugs y observaciones (tabla)
Solo los FAIL/PARCIAL/OBS con: ID · Prioridad (🔴 alta / 🟡 media / 🔵 baja) · Descripción · Acción sugerida.

Para cada bug detectado, ID con prefijo:
- `BUG-<bloque>-NNN` para regresiones reproducibles.
- `OBS-<bloque>-NNN` para observaciones (no bloqueantes, decisiones UX, mejoras).

### Notas operativas
Datos creados durante el testing que quedan en DB, restricciones cumplidas (no commits, no push, etc.).

## Tras recibir el reporte

1. **Guardarlo a disco** con el naming convention en la raíz del repo. El usuario suele pegarlo en el chat porque su entorno (agente QA) no puede escribir archivos.

2. **Triagear cada bug/observación**:
   - **Verificar antes de planear fix**: hacer 1 grep o 1 query SQL para confirmar que el bug existe y no es ya un comportamiento documentado/implementado (ver `feedback_aprendizajes_proyecto.md` G9).
   - **Convención del proyecto?**: si la observación es una "discrepancia" entre dos campos, chequear CLAUDE.md antes (G10).
   - **Probar el contrato antes de leer código**: si es un bug de form/persistencia, `curl` el endpoint + `SELECT` directo en DB antes de leer el frontend (G8).

3. **Actualizar memoria** `project_estado_sesion_y_pendientes.md` con:
   - Resultado global del bloque.
   - Bugs/OBS sin resolver categorizados por prioridad.
   - Acciones tomadas (fixes aplicados, OBS cerradas como no-bug, OBS diferidas).

4. **Decidir alcance del fix con el usuario** vía `AskUserQuestion`:
   - Fixear todos los bugs medios + cerrar OBS no-bugs.
   - Diferir bugs medios a sub-fase futura (con justificación).
   - Solo cerrar las OBS que son no-bug.

## Plantilla mínima copiable

```markdown
# Reporte de Pruebas — Bloque X · Módulo Y

**Fecha:** YYYY-MM-DD
**Tester:**
**Entorno:**
**Login auto:**
**Duración aprox.:** N min

## Servicios verificados

| Servicio | URL | Resultado |
|---|---|---|
| Backend | http://127.0.0.1:8000/health | ✅ |
| Web-app | http://localhost:5173 | ✅ |

## Resumen ejecutivo

| Subsección | PASS | FAIL | PARCIAL | OBS | N/A | Total |
|---|---|---|---|---|---|---|
| X.1 ... | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total** | **0** | **0** | **0** | **0** | **0** | **0** |

**Estado global:** 🟢 / 🟡 / 🔴.

## Detalle por caso

### X.1 ...

| Caso | Resultado | Observación |
|---|---|---|
| X.1.1 ... | ✅ PASS | ... |

## Bugs y observaciones

| ID | Prioridad | Descripción | Acción sugerida |
|---|---|---|---|
| BUG-X-001 | 🟡 | ... | ... |

## Notas operativas

-
```

## Reportes históricos

- `reporte_pruebas_bloque_A_2026-05-11.md` — Agenda React, 70 casos, 0 FAIL.
- `reporte_pruebas_bloques_D_y_C_2026-05-11.md` — OTs vanilla + Reclamos vanilla, 22 casos, 0 FAIL.
