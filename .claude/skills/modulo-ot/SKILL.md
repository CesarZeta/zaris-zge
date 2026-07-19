---
name: modulo-ot
description: "Usar al trabajar en el módulo OT (Órdenes de Trabajo) de ZARIS (archivos: backend/app/api/routes/ordenes_trabajo.py, ot_adjuntos.py, web-app/src/modules/ot/ — SupervisorView, AgenteView, PlanificadorOT, OTDetalleDrawer, useOT.ts; tablas: ordenes_trabajo, ot_adjuntos). Cubre el flujo del supervisor (crear OT + agendar en una pasada), slots libres por recurso, auto-asignar al primero disponible, las 3 mesas (Supervisor/Agente/Auditoría), guard de nivel ≤2, bypass es_auditor de admin, y los adjuntos de evidencia de OT. Invocar ANTES de tocar cualquier endpoint, mesa, planificador o adjunto de OT."
---

# Módulo OT — frontend dedicado del Supervisor (crear OT + agendar en una pasada) — §34

Implementado 2026-05-14 jornada 5. El bullet "OT" del menú es el frontend donde el supervisor, desde la bandeja de reclamos de su subárea, crea la OT **y** la planifica en la agenda de agentes/equipos en un solo flujo. Antes eran dos pasos en dos módulos (crear OT en `modules/ot`, agendarla en `modules/agenda`).

### Vista Supervisor — layout 2 columnas (tab "Asignar")

`web-app/src/modules/ot/views/SupervisorView.tsx`: el tab Asignar usa grid `minmax(0,1fr) 340px` — bandeja de reclamos a la izquierda, `PlanificadorOT` a la derecha. Click en una fila (o en el botón "Planificar") selecciona el reclamo en el panel. El flujo de **lote** (checkboxes + `AsignarModal`) se mantiene intacto: agendar 10 OTs distintas en un panel no tiene sentido, el lote sigue siendo asignación simple sin agenda. El tab "Reasignar" no cambió.

### `PlanificadorOT.tsx` — panel de planificación

`web-app/src/modules/ot/components/PlanificadorOT.tsx`: muestra contexto del reclamo → selector agente/equipo → fecha → **slots libres como chips clickeables** → dos acciones:
- **"Crear OT y agendar"** → `POST /ot/con-agenda` (crea OT + ocupación espejo en una transacción).
- **"Crear OT sin agendar"** → `POST /ot` normal. La OT queda sin ocupación; igual registra al supervisor en `id_supervisor_asigna`.

Valida FK antes de enviar (ver memoria `feedback_validar_fk_antes_submit`).

### Backend nuevo en `ordenes_trabajo.py`

| Acción | Verbo | Path | Notas |
|---|---|---|---|
| Slots libres de un recurso | GET | `/api/v1/ot/slots-recurso?tipo_recurso=&id_recurso=&fecha=&duracion_min=` | **Segmento fijo: registrado ANTES de `GET /{id_ot}`** (§5). Agente: disponibilidad efectiva menos sus ocupaciones. Equipo: **delega en `disponibilidad_efectiva('equipo')`** (§27 — unión de agentes + override) menos las ocupaciones del equipo y de sus agentes. |
| Crear OT + agenda | POST | `/api/v1/ot/con-agenda` | Crea OT y ocupación tipo `'ot'` en una transacción. Body `dict` → convierte fecha/hora con `date.fromisoformat`/`time.fromisoformat` (asyncpg no castea strings, ver memoria `feedback_asyncpg_extract_cast_date`). Detecta conflictos de solapamiento y los devuelve, pero la OT igual se crea. `id_supervisor_asigna` = usuario logueado. |
| **Auto-asignar al primero disponible** | GET | `/api/v1/ot/auto-asignar-sugerencia?id_reclamo=&fecha=&duracion_min=` | **Segmento fijo ANTES de `/{id_ot}`** (§5). Nivel ≤ 2. Recorre cuadrillas + agentes de la **subárea del reclamo** (derivada del tipo) y devuelve el **primero con slot libre** (prioriza equipos sobre agentes). `{sugerencia: {tipo_recurso, id_recurso, nombre, slot} \| null, motivo?}`. El botón "Auto-asignar al primero disponible" del `PlanificadorOT` lo consume y preselecciona recurso+slot para confirmar. |

`GET /ot/mesa/supervisor` ahora expone **`ot_activa_agendada`** (boolean): el CTE `ot_activa` agrega un `EXISTS` sobre `ocupaciones` tipo `'ot'` activas ligadas a la OT. Permite distinguir en la bandeja las OTs creadas sin agendar. **El filtro `id_subarea` de la mesa usa `tr.id_subarea` derivado del tipo, NO `r.id_subarea`** (que está NULL en el 100% de los reclamos — filtrar por ahí vaciaba la bandeja, [[feedback_filtro_igual_null_vacia_listado]]). Mismo criterio en las dos mesas de auditoría.

> **GAP verificado (2026-07-02, no asumir que scopea):** ese filtro `id_subarea` es un **query param opcional** — el backend NO lo impone según la subárea del supervisor logueado; hoy cualquier supervisor ve la bandeja de TODAS las subáreas. Ídem el selector manual de agentes del `PlanificadorOT` (`RecursoPicker` → `GET /agenda/catalogos/recursos`): lista todos los agentes sin filtro de subárea. Solo `auto-asignar-sugerencia` scopea (por la subárea del RECLAMO). El scoping por subárea del supervisor es pendiente de Fase 3 roles (ver `ESTADO.md`).

Helpers compartidos en `ordenes_trabajo.py`: `_slots_de_rango`, `_solapa`, `_merge_rangos`, `_slots_libres_recurso`. **El caso equipo de `_slots_libres_recurso` delega en `services/agenda.py::disponibilidad_efectiva('equipo')`** para no duplicar la lógica de unión/override (esa duplicación divergía de la grilla de Agenda — bug cerrado 2026-06-15).

### Hooks `useOT.ts`

`useSlotsRecurso(tipo, id, fecha, duracion)` — query de slots, `enabled` solo con recurso+fecha elegidos. `useCrearOTConAgenda()` — mutation que invalida mesas de OT **y** queries de agenda (`['agenda']`), porque la ocupación nueva debe aparecer en la grilla del módulo Agenda.

### Estado de los 3 módulos del menú (confirmado 2026-05-14)

- **OT** → frontend dedicado del supervisor (esta sección). Crea OT relacionada al reclamo + la agenda.
- **Turnos** → ligado a **agentes**, turnos de atención al ciudadano (§33). NO se tocó.
- **Entradas** → ligado a **espacios** + eventos con cupo (§33). NO se tocó.

`OcupacionOTModal` en el módulo Agenda (§ ver jornada anterior) se mantiene: sigue siendo válido planificar en la Agenda una OT ya creada. El flujo nuevo de OT no lo reemplaza, lo complementa.

### Mesa Auditoría — admin (nivel 1) bypassea `es_auditor`

Desde 2026-05-19: el check `agentes.es_auditor=TRUE` en `GET /api/v1/ot/auditor/me` se saltea cuando `current_user.nivel_acceso <= 1`. Admin por definición tiene acceso total al módulo y no necesita el flag explícito en DB. La regla "no auditar lo propio" se preserva via el filtro existente `(ot.id_agente IS NULL OR ot.id_agente = :id_agente)` del listado, que excluye las OTs operativas asignadas al mismo agente. Niveles 2-4 siguen requiriendo `es_auditor=TRUE` en su fila de `agentes`. El endpoint legacy `GET /mesa/auditoria?id_agente=` nunca chequeó `es_auditor` (recibía el id por query), así que no necesitó cambio.

### Guard de nivel — Mesa Supervisor y asignación de OT exigen nivel ≤ 2 (hallazgo QA #2, 2026-05-20)

Antes, los endpoints de asignación de OT solo usaban `get_current_user` sin chequear nivel — un Operador (nivel 3) podía crear/asignar OT desde la Mesa Supervisor. Fix:

- **Backend:** helper `_require_supervisor(current_user)` en `ordenes_trabajo.py` (403 si `nivel_acceso > 2`), aplicado como primera línea de `GET /ot/mesa/supervisor`, `POST /ot`, `POST /ot/con-agenda`. `PUT /ot/{id}/reasignar` ya lo tenía inline. Espeja `modulos.ot_supervisor.min_nivel_acceso = 2`.
- **Frontend (bundle React):** gate `WrapNivel` en `web-app/src/modules/ot/index.tsx` — `/ot/supervisor` y `/ot/auditoria` exigen nivel ≤ 2; el operador ve "Acceso restringido". El redirect de `/ot` (sin sub-ruta) es por rol: nivel ≤ 2 → `/ot/supervisor`, resto → `/ot/agente`.
- **Sidebar vanilla:** el link OT en `index.html` apunta a `#/ot` (no `#/ot/supervisor`) para que el redirect por rol decida la mesa. Conserva `data-modulo-fallback="ot_agente,ot_auditoria"` para que el item siga visible al operador (que aterriza en su Mesa de Agente).

Defensa en profundidad: aunque un operador deep-linkee a `/ot/supervisor`, el frontend muestra el mensaje y el backend rechaza con 403. Ver memoria [[guard_nivel_endpoint_no_solo_ui]].

### Adjuntos de OT — evidencia del trabajo (hallazgo QA Royman #4, 2026-05-20)

El #4 que quedó diferido en el commit `2110263`. Las OT ahora tienen adjuntos propios (fotos de la evidencia del trabajo: bache reparado, luminaria cambiada). **Independientes de los adjuntos del reclamo** (§26): el drawer muestra ambas secciones — "ADJUNTOS" (del reclamo) y "EVIDENCIA DE LA OT" (de la OT resaltada).

- **Tabla `ot_adjuntos`** (mig 54, ver §21): espejo de `reclamo_adjuntos` pero FK a `ordenes_trabajo(id_ot) ON DELETE CASCADE`. Reusa el bucket privado `reclamos-adjuntos` (paths bajo `ot/{id_ot}/{uuid}.{ext}`). Modelo `OrdenTrabajoAdjunto` en `backend/app/models/reclamos.py`.
- **Router `ot_adjuntos.py`** (prefix `/api/v1/ot/{id_ot}/adjuntos`): mismo flujo que reclamo_adjuntos — `POST /upload-url` → PUT directo al storage → `POST /{id_adj}/confirm`; `GET ""` (URLs firmadas TTL 1h); `DELETE /{id_adj}` (soft-delete + remove del bucket). Reusa `app/core/storage.py` (que ya aceptaba `bucket`/`path` arbitrarios).
- **Registrado en `main.py` ANTES de `ot_router`** (§5): `/ot/{id_ot}/adjuntos` no debe ser atrapado por el `/{id_ot}` greedy del router de OT.
- **Permiso SUBIR/BORRAR**: agente asignado a la OT (`ordenes_trabajo.id_agente` = `agentes.id_agente` del usuario, resuelto vía `agentes.id_usuario`) **o** nivel ≤ 2 (admin/supervisor). Helper `_require_puede_gestionar`. **VER (listar) lo puede cualquier autenticado** — todas las mesas ven la evidencia.
- **Frontend**: `web-app/src/modules/ot/` → `api/otAdjuntosApi.ts`, `hooks/useOTAdjuntos.ts`, `components/UploadAdjuntosOTPanel.tsx` (clon del de reclamos apuntando a la API de OT + queryKey `['ot','adjuntos',idOt]`). La sección vive en `OTDetalleDrawer.tsx` (`OTAdjuntosSection`), se muestra cuando `idOTResaltada != null`. El drawer recibe prop `puedeGestionarAdjuntos`: AgenteView lo pasa `true` si `scope ∈ {'mia','disponible_equipo'}`; Supervisor/Auditoría lo pasan `user.nivel_acceso <= 2`. El gate solo gobierna la UI — el backend igual hace cumplir el guard (un operador no-asignado recibe 403).
- **Verificado end-to-end (2026-05-20)**: smoke backend 5/5 (agente asignado sube OK, no-asignado 403, admin OK, listar, OT inexistente 404) + verificación visual en navegador (subir PNG real al storage Supabase → galería → borrar → vuelve a "Sin evidencia adjunta").

### Scope-subárea en mutaciones (2026-07-18, hallazgos [33][34] de la auditoría)

- **`_validar_scope_operar_ot(db, user, id_ot, id_agente_delegado=)`** aplica en `PUT /{id}/tomar` y `PUT /{id}/estado` sobre OTs OPERATIVAS: nivel 3/4 solo opera OTs propias (`ot.id_agente`), de sus cuadrillas (`ot.id_equipo ∈ ids_equipos` — la excepción por equipo es OBLIGATORIA porque la mesa del agente ofrece OTs por membresía sin condición de subárea) o de su subárea (`tr.id_subarea` derivada del tipo; NULL = no acotable, se permite). Nivel 2 pasa por `_validar_scope_supervisor_ot` (reclamo Y agente destino en la delegación de tomar). Nivel 1 sin restricción.
- **OTs `es_auditoria=TRUE` EXENTAS** del guard de misma-subárea (la auditoría es cross-subárea POR DISEÑO). Su guard es el INVERSO: **`_validar_scope_auditor`** en `/aprobar` y `/rechazar` re-valida en la mutación el mismo filtro de la mesa — (1) auditoría asignada a otro auditor → 403; (2) con `auditor_misma_subarea_permitido=false`, subárea propia (agente ∪ equipos) → 403; la asignación al propio auditor PREVALECE sobre el filtro de subárea. Admin (nivel 1) bypassea.
- Regla al agregar una mutación de OT: llamar a uno de los dos guards según `es_auditoria` — verificado con smoke multi-subárea (n4 cross 403 / propio 200 / delegación n2 cross 403).
