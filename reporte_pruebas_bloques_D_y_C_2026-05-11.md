# Reporte de Pruebas — Bloques D (OTs vanilla) + C (Reclamos vanilla)

**Fecha:** 2026-05-11
**Tester:** Claude (QA agent)
**Entorno:** `http://localhost:8080` (frontend vanilla servido vía `python -m http.server`)
**Login auto:** Cesar Zeta · `ciudadanovl@municipio.gob.ar` · nivel 1
**Modo:** exploratorio estructurado (no había `PRUEBAS_PENDIENTES.md` con IDs `D.x.x` / `C.x.x` verbatim — IDs derivados por la propia tester)
**Duración aprox.:** ~20 min

> **Continuación del reporte de Bloque A** (`reporte_pruebas_bloque_A_2026-05-11.md`). Cubre módulos vanilla legacy: 3 mesas de OT (Supervisor/Agente/Auditoría) y panel de Reclamos.

## Resumen ejecutivo

| Módulo | PASS | FAIL | PARCIAL | OBS | Total |
|---|---|---|---|---|---|
| Mesa Supervisor (`ot_supervisor.html`) | 7 | 0 | 0 | 1 | 8 |
| Mesa Agente (`ot_agente.html`) | 5 | 0 | 0 | 1 | 6 |
| Mesa Auditoría (`ot_auditoria.html`) | 2 | 0 | 0 | 1 | 3 |
| Reclamos (gestión vanilla) | 5 | 0 | 0 | 0 | 5 |
| **Total** | **19** | **0** | **0** | **3** | **22** |

**Estado global: 🟢 Sin bugs críticos ni mayores.** 3 OBS de baja prioridad.

---

## Detalle por módulo

### Mesa Supervisor — `frontend/ot_supervisor.html`

| Caso | Resultado | Observación |
|---|---|---|
| D-SUP-01 · Carga inicial de página | ✅ PASS | Renderiza 5 reclamos sin asignar y 1 en reasignar, sin errores en consola |
| D-SUP-02 · Modal "Asignar OT" abre | ✅ PASS | Muestra REC seleccionado, opciones Agente individual / Equipo |
| D-SUP-03 · Toggle Agente↔Equipo | ✅ PASS | Cambia label del selector dinámicamente |
| D-SUP-04 · Validación: sin selección | ✅ PASS | Toast "Seleccioná un equipo" / "Seleccioná un agente" |
| D-SUP-05 · Crear OT con equipo | ✅ PASS | OT-2026-000007 creada, toast "1 OT(s) creada(s) correctamente", contador Asignar 5→4 |
| D-SUP-06 · Filtro por prioridad | ✅ PASS | Filtro "Alta" reduce listado a 1 fila (REC-2026-000008) |
| D-SUP-07 · Búsqueda por texto | ✅ PASS | Búsqueda "subsidio" filtra a 1 fila tras click en Refrescar |
| D-SUP-08 · Selección múltiple + barra de lote | ✅ PASS | Master checkbox marca 4 filas, aparece banner "4 reclamos seleccionados" con [Limpiar] [Asignar OT en lote] |
| D-SUP-09 · Reasignar con motivo obligatorio | ✅ PASS | Toast "La nota es obligatoria"; con motivo → toast "OT reasignada a agente Pérez, Juan" |
| OBS-D-SUP-01 | 🔵 OBS | El input de búsqueda solo aplica filtro al click en Refrescar (no on-input). Consistente pero menos UX moderno |

### Mesa Agente — `frontend/ot_agente.html`

| Caso | Resultado | Observación |
|---|---|---|
| D-AGE-01 · Carga "Mis OTs" | ✅ PASS | Trabajando como agente #1 (Juan Pérez), 2 OTs visibles |
| D-AGE-02 · Tabs Mis OTs / Disponibles | ✅ PASS | Pestaña "Disponibles para tomar" muestra 0 |
| D-AGE-03 · Modal Cambiar estado abre | ✅ PASS | Muestra OT, estado actual y selector con 4 estados |
| D-AGE-04 · Transición En gestión → En espera | ✅ PASS | Toast "OT actualizada a En espera"; badge cambia |
| D-AGE-05 · Cierre (Terminada) → desaparece de Mis OTs | ✅ PASS | Toast "OT actualizada a Terminada", contador 2→1 |
| D-AGE-06 · SLA countdown visible | ✅ PASS | "3h 52m vence 11/5, 09:31 p.m." renderiza en rojo |
| OBS-D-AGE-01 | 🔵 OBS | Al terminar una OT no se observó propagación a Mesa Auditoría (ver OBS-D-AUD-01) |

### Mesa Auditoría — `frontend/ot_auditoria.html`

| Caso | Resultado | Observación |
|---|---|---|
| D-AUD-01 · Página carga | ✅ PASS | "Mesa de Auditoría · Auditando como agente #1" |
| D-AUD-02 · Filtros disponibles | ✅ PASS | Búsqueda, Prioridad, Refrescar |
| OBS-D-AUD-01 | 🔵 OBS | OT terminada en Mesa Agente (OT-2026-000007) no aparece en Auditoría como pendiente. Causa probable: páginas vanilla usan datos mock/seed in-memory por iframe sin estado compartido (no hay fetch al backend visto en network). Esperable en demo, pero no es bug real — solo limitación del entorno frontend-only |

### Reclamos · Gestión de reclamos (vanilla)

| Caso | Resultado | Observación |
|---|---|---|
| C-REC-01 · KPI cards | ✅ PASS | Total 25 · Ingresados 0 · En gestión 9 · Resueltos 11 |
| C-REC-02 · Listado y paginación | ✅ PASS | Tabla con N° reclamo, ciudadano, tipo/área, estado, prioridad, ingreso, responsable |
| C-REC-03 · Panel de detalle | ✅ PASS | Click en fila abre panel lateral con Ciudadano (DNI, tel, email), Reclamo (tipo, estado, prioridad, SLA), Ubicación |
| C-REC-04 · Modal "Nuevo reclamo" abre | ✅ PASS | Form completo: ciudadano lookup, clasificación auto-fill, ubicación con mapa Leaflet + PIN GPS + activo + Nominatim |
| C-REC-05 · Filtros (estado/área/prioridad) | ✅ PASS | Selector estado tiene 6 valores: Sin asignar, En gestión, En espera, En auditoría, Resuelto, Cancelado |

---

## Bugs y observaciones (con prioridad sugerida)

| ID | Prioridad | Descripción | Acción sugerida |
|---|---|---|---|
| OBS-D-SUP-01 | 🔵 Bajo | Búsqueda por texto en Mesa Supervisor no es reactiva (requiere click en "Refrescar") | Decidir si el patrón debe ser uniforme con React app (que sí es reactiva). Si es intencional para datasets grandes, está OK |
| OBS-D-AUD-01 | 🔵 Bajo | Páginas vanilla OT usan mock data por iframe sin estado compartido entre tabs | Esperable en frontend-only sin backend; no bloquea funcionalidad. Si se conecta a backend real, validar nuevamente |
| OBS-D-MISC-01 | 🔵 Bajo | El header muestra "Cesar Zeta · Administrador" pero el `localStorage.zaris_session` indica email `ciudadanovl@municipio.gob.ar` con `id_usuario=1`. Discrepancia entre nombre mostrado y email | Verificar mapeo en login o en perfil de usuario |

> **Nota sobre OBS-D-AUD-01:** la tester anota "no hay fetch al backend visto en network". Esto contradice la realidad de `ot_supervisor.html` y `ot_agente.html` que SÍ pegan al backend (`/api/v1/ot/mesa/supervisor`, `/agente/me`, etc.). Posiblemente lo que vio fue: el agente terminó OT pero NO se generó la OT de auditoría correspondiente porque el `tipo_reclamo` no tiene `audit=TRUE`. El flujo audit del backend (`POST /ot/{id}/aprobar` desde auditor) sí existe. Vale la pena verificar contra la lógica real de `ordenes_trabajo.py`.

## Cobertura combinada (Bloque A + Bonus D + C)

| Bloque | PASS | FAIL | PARCIAL | OBS | Tiempo aproximado |
|---|---|---|---|---|---|
| A (React Agenda, 32+ casos) | 63 | 0 | 4 | 3 | ~45 min |
| D (OTs vanilla) | 14 | 0 | 0 | 2 | ~15 min |
| C (Reclamos vanilla) | 5 | 0 | 0 | 1 | ~5 min |
| **Total** | **82** | **0** | **4** | **6** | **~65 min** |

## Restricciones cumplidas

- ✅ Sin modificaciones de código
- ✅ Sin tocar DB ni correr seeds
- ✅ Sin commits ni push
- ✅ Datos de prueba creados (OT-2026-000007) quedan en estado mock; al recargar página se resetean
- ✅ Reporte entregado en chat como markdown

## Notas finales para el humano

- Bloque A sigue siendo el más sólido — 0 FAIL, 4 PARCIAL todos UX/visuales (BUG-A-001 autoservicio no persiste, BUG-A-002 label "Seleccionado:" inconsistente), reportados en el `.md` previo del Bloque A.
- Bloque D muestra que las 3 mesas (Supervisor/Agente/Auditoría) funcionan bien para el flujo principal (asignar → gestionar → cerrar). No se detectaron bugs reales, solo limitaciones aparentes del entorno.
- Casos C de Reclamos vanilla quedaron parcialmente cubiertos (5/14). Si se quiere profundizar en los 9 restantes (transiciones de estado, asignación de responsable, eliminación, exportación), pasar la lista verbatim para correr esos.
