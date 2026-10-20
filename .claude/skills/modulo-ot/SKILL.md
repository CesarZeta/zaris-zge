---
name: modulo-ot
description: "Usar al trabajar en el módulo OT (Órdenes de Trabajo) de ZARIS (archivos: backend/app/api/routes/ordenes_trabajo.py, ot_adjuntos.py, services/autoasignacion.py, web-app/src/modules/ot/ — SupervisorView, AgenteView, PlanificadorOT, OTDetalleDrawer, useOT.ts; tablas: ordenes_trabajo, ot_adjuntos). Cubre el flujo del supervisor (crear y asignar la OT; los reclamos NO se agendan desde 2026-10-21), auto-asignar y autoasignación por menor carga y rotación, las 3 mesas (Supervisor/Agente/Auditoría), guard de nivel ≤2, bypass es_auditor de admin, y los adjuntos de evidencia de OT. Invocar ANTES de tocar cualquier endpoint, mesa, planificador o adjunto de OT."
---

# Módulo OT — frontend dedicado del Supervisor — §34

Implementado 2026-05-14 jornada 5. El bullet "OT" del menú es el frontend donde el supervisor, desde la bandeja de reclamos de su subárea, crea la OT y la asigna a un agente o cuadrilla.

### REGLA: los reclamos NO se agendan (César, 2026-10-21)

«La agenda solo es para turnos, no para reclamos. Solo que haya agentes y equipos para que se asignen los reclamos. Los horarios no entran en la ecuación.» Consecuencias vigentes:
- **El planificador no tiene fecha, huecos ni advertencias de horario**: agente/equipo + observaciones → «Crear OT» (`POST /ot`). Un agente sin horario cargado recibe OTs igual.
- **Auto-asignar (sugerencia) y la autoasignación por gestión eligen por menor carga y rotación** (`services/autoasignacion.py::candidatos_gestion`, compartido). Ninguna crea ocupación en la Agenda.
- **El módulo Agenda no crea ocupaciones de OT** (se quitaron «Planificar OT», `OcupacionOTModal`, el panel de OTs pendientes para arrastrar y `OTSearch`). Las ocupaciones `tipo='ot'` que ya existían (4 en prod) se siguen viendo y moviendo.
- `GET /ot/slots-recurso`, `POST /ot/con-agenda` y `services/ot_slots.py` quedan **sin uso** (compat con el bundle anterior); retirarlos en una sesión posterior verificando que ningún cliente los llame. `/auto-asignar-sugerencia` acepta `fecha`/`duracion_min` y los ignora.
- Si alguna vez vuelve la idea de «agendar» una OT, es una decisión de César: no reintroducirla por defecto.
- Las secciones de abajo que hablan de slots, `con-agenda` u ocupaciones de OT describen la historia hasta 2026-10-21.

### Vista Supervisor — tabla a todo el ancho + panel lateral (rediseño 2026-10-20)

`web-app/src/modules/ot/views/SupervisorView.tsx`: la tabla ocupa todo el ancho (antes había una columna fija de 340 px con el `PlanificadorOT`, que dejaba la tabla con scroll horizontal y 4 de 8 columnas visibles — queja de César). Click en una fila (o «Planificar») abre el `PlanificadorOT` en un **panel lateral fijo que se superpone** (z 2100, Escape/fondo/X lo cierran; se cierra solo al crear la OT). Filas compactas: «N° · Tipo» en una celda (con dos botones de orden), SLA con `SLACell compacto` («Vencido 15 d», detalle en el tooltip). **Barra «Asignar (N)» SIEMPRE visible** en Asignar tras buscar (apagada sin tildados, con la ayuda «Tildá…»): tildar + Asignar abre el `AsignarModal` de lote. Todas las columnas ordenables en pantalla (`ui/orden.tsx`; la mesa trae todo, sin tope); lo mismo en las mesas Agente y Auditoría.

### Autoasignación de reclamos por gestión (mig 114, 2026-10-20)

`services/autoasignacion.py::autoasignar_reclamo` corre como **BackgroundTask** después de responder en las 4 vías que crean reclamos (`POST /reclamos`, subreclamo, `POST /publico/reclamos`, retrabajo de `/observar`). Solo actúa si `subarea.asignacion_automatica` (tilde en Maestros → Subáreas, solo admin) y el reclamo sigue «Sin asignar» sin OT. Candidatos según `tipo_reclamo.asignacion_a` (agente nivel 4 no auditor | cuadrilla con integrantes operativos; hoy los 285 tipos de prod dicen `agente`); el de **menor carga** (OTs operativas abiertas) y desempate por **rotación** (la última asignación más vieja). **Sin horarios ni ocupación desde 2026-10-21** (hasta ahí buscaba un hueco día por día por 30 días y exigía horarios cargados). Crea OT `asignacion_automatica=TRUE` con `id_supervisor_asigna NULL` + reclamo En gestión + historial «OT … asignada automáticamente» («menor carga de la gestión: N OTs abiertas») y avisa (`notificar_ot_asignada`, `notificar_estado_reclamo`). Sin candidatos: historial «Asignación automática sin candidatos» + campana (código histórico `autoasignacion_sin_hueco`, sin mail) a supervisores de la gestión, fallback admins. `pg_advisory_xact_lock(114000000 + id_subarea)` serializa la gestión (el segundo reclamo ve la carga del primero). `tipo_reclamo.duracion_estimada_min` quedó sin uso. Reclamos ya existentes no se reasignan al prender el tilde. Smoke local 11/11 (2026-10-21, con agentes SIN horario cargado).

### Destinatario de una OT: siempre una persona (2026-10-20)

`_validar_destinatario_ot` (en `POST /ot`, `/con-agenda`, `/reasignar` y la delegación de `/tomar`; todos los niveles): **agente** activo con usuario de ZARIS activo y nivel ≤ 4 (`NIVEL_MAX_OPERA_OT`; el Consultor no opera); **equipo** activo con al menos un integrante así. Sino 422 accionable («El equipo X no tiene integrantes…»). `notificar_ot_asignada` (push.py) escribe la **campana** (`notificacion` tipo `ot_asignada`, `recurso_tipo='ot'`, sin mail) y manda push: al agente asignado o, si la OT es de un equipo sin agente, a **todos** sus integrantes activos (antes una OT de cuadrilla no avisaba a nadie); también avisa al agente cuando un supervisor le delega con `/tomar`. La sugerencia de auto-asignar descarta equipos sin integrantes operativos y solo propone agentes de nivel 4 no auditores. La app de agentes lee esa campana en `/avisos` (navega por `recurso_tipo/recurso_id`).

### `PlanificadorOT.tsx` — panel de planificación

`web-app/src/modules/ot/components/PlanificadorOT.tsx` (desde 2026-10-21): contexto del reclamo → «Auto-asignar al de menor carga» (preselecciona y avisa la carga) → agente/equipo (`RecursoPicker`, acotado a la subárea para nivel 2) → observaciones → **«Crear OT»** (`POST /ot`, registra al supervisor en `id_supervisor_asigna`). Se abre desde la fila, el botón «Planificar» o el botón **PLANIFICAR del detalle** («Ver», solo reclamos Sin asignar en la pestaña Asignar: `OTDetalleDrawer.onPlanificar`). La mesa muestra la **fecha de ingreso** (ordenable) en lugar del ciudadano (César 2026-10-21; el vecino está en «Ver»).

### Backend nuevo en `ordenes_trabajo.py`

| Acción | Verbo | Path | Notas |
|---|---|---|---|
| Slots libres de un recurso | GET | `/api/v1/ot/slots-recurso?tipo_recurso=&id_recurso=&fecha=&duracion_min=` | **Segmento fijo: registrado ANTES de `GET /{id_ot}`** (§5). Agente: disponibilidad efectiva menos sus ocupaciones. Equipo: **delega en `disponibilidad_efectiva('equipo')`** (§27 — unión de agentes + override) menos las ocupaciones del equipo y de sus agentes. |
| Crear OT + agenda | POST | `/api/v1/ot/con-agenda` | Crea OT y ocupación tipo `'ot'` en una transacción. Body `dict` → convierte fecha/hora con `date.fromisoformat`/`time.fromisoformat` (asyncpg no castea strings, ver memoria `feedback_asyncpg_extract_cast_date`). Detecta conflictos de solapamiento y los devuelve, pero la OT igual se crea. `id_supervisor_asigna` = usuario logueado. |
| **Auto-asignar al de menor carga** | GET | `/api/v1/ot/auto-asignar-sugerencia?id_reclamo=` | **Segmento fijo ANTES de `/{id_ot}`** (§5). Nivel ≤ 2 + scope de subárea. Desde 2026-10-21: `candidatos_gestion` del tipo preferido (`tipo_reclamo.asignacion_a`), si no hay, del otro; devuelve el primero (menor carga, rotación). `{sugerencia: {tipo_recurso, id_recurso, nombre, carga} \| null, motivo?}`. `fecha`/`duracion_min` se aceptan y se ignoran (bundle anterior). Hasta esa fecha devolvía el primer recurso con hueco en la fecha. |

`GET /ot/mesa/supervisor` ahora expone **`ot_activa_agendada`** (boolean): el CTE `ot_activa` agrega un `EXISTS` sobre `ocupaciones` tipo `'ot'` activas ligadas a la OT. Permite distinguir en la bandeja las OTs creadas sin agendar. **El filtro `id_subarea` de la mesa usa `tr.id_subarea` derivado del tipo, NO `r.id_subarea`** (que está NULL en el 100% de los reclamos — filtrar por ahí vaciaba la bandeja, [[feedback_filtro_igual_null_vacia_listado]]). Mismo criterio en las dos mesas de auditoría.

> **Scope por subárea del supervisor — CERRADO por la Fase 3 de roles (verificado en código 2026-10-20; la nota de GAP del 2026-07-02 quedó vieja):** `GET /ot/mesa/supervisor` llama `_subarea_forzada_supervisor` y, para nivel 2, la subárea de su agente pisa cualquier `id_subarea` del query (nivel 1 filtra libre). Las mutaciones (`POST /ot`, `/con-agenda`, `/reasignar`) validan reclamo y recurso con `_validar_scope_supervisor_ot`. En el front, `PlanificadorOT` le pasa `idSubarea` al `RecursoPicker` y `ReasignarModal` filtra agentes/equipos por subárea para nivel 2 (el backend igual da 403).

Helpers compartidos en `ordenes_trabajo.py`: `_slots_de_rango`, `_solapa`, `_merge_rangos`, `_slots_libres_recurso`. **El caso equipo de `_slots_libres_recurso` delega en `services/agenda.py::disponibilidad_efectiva('equipo')`** para no duplicar la lógica de unión/override (esa duplicación divergía de la grilla de Agenda — bug cerrado 2026-06-15).

> **Agente recién creado = sin slots (verificado en código 2026-10-20).** Un agente que nace del alta de usuario o de la ficha del funcionario (§39) no tiene `disponibilidad_recurso`, así que `slots-recurso` devuelve `[]` y el `PlanificadorOT` no puede agendarle una OT hasta que alguien le cargue horario en Agenda → Disponibilidad. `PUT /ot/{id}/reasignar` NO consulta disponibilidad (solo nivel ≤ 2 + `_validar_scope_supervisor_ot` para nivel 2), y es la vía más corta para probar el push de «OT asignada» (`notificar_ot_asignada`, que también disparan `POST /ot` y `POST /ot/con-agenda`). El modal de reasignar usa `useAgentesActivos` con `staleTime` de 1 h: si el agente se creó con la pestaña abierta, recargar para que aparezca.

### Hooks `useOT.ts`

`useSlotsRecurso(tipo, id, fecha, duracion)` — query de slots, `enabled` solo con recurso+fecha elegidos. `useCrearOTConAgenda()` — mutation que invalida mesas de OT **y** queries de agenda (`['agenda']`), porque la ocupación nueva debe aparecer en la grilla del módulo Agenda.

### Estado de los 3 módulos del menú (confirmado 2026-05-14)

- **OT** → frontend dedicado del supervisor (esta sección). Crea OT relacionada al reclamo + la agenda.
- **Turnos** → ligado a **agentes**, turnos de atención al ciudadano (§33). NO se tocó.
- **Entradas** → ligado a **espacios** + eventos con cupo (§33). NO se tocó.

`OcupacionOTModal` del módulo Agenda se **borró el 2026-10-21** (las OT no se agendan, ver la regla de arriba).

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

### Auditoría POSTERIOR al cierre (mig 112, 2026-10-20) — qué cambió en OT

La auditoría ya no nace al terminar la OT operativa (`tipo_reclamo.audit` no se consulta más: terminar SIEMPRE resuelve el reclamo). La OT `es_auditoria` la crea `POST /reclamos/{id}/auditoria` sobre un reclamo **Resuelto** (supervisor de la subárea o admin; `id_ot_origen` = la última OT operativa Terminada, para que la mesa muestre quién hizo el trabajo; `id_agente` opcional = auditor puntual). Semántica completa en la skill `modulo-reclamos`.

- **Mesa del auditor (`/auditor/me`, `/mesa/auditoria`)**: mismo filtro de siempre (sin asignar o asignada a mí + regla de subárea cruzada), ahora con `reclamo_estado`, `reclamo_fecha_cierre` y `fecha_inicio_auditoria` en la fila. El frontend muestra «Resuelto el» y los botones **Aprobar / Observar**.
- **`PUT /{id}/aprobar`** → OT `Terminada`/`aprobada`; reclamo `Auditado` + `resultado_auditoria='aprobado'` + `fecha_fin_auditoria`. **Sin `_resolver_reclamo`, sin encuesta, sin push** (el vecino sigue viendo Resuelto). 422 si la OT ya está Terminada/Cancelada o el reclamo no está `En auditoría`.
- **`PUT /{id}/observar`** (alias deprecado `/rechazar`, mismo handler `observar_ot`; el bundle viejo lo sigue llamando hasta que publique el nuevo) → OT `Terminada`/`observada` (valor nuevo en `ck_ot_resultado`); reclamo `Auditado`/`observado`. **Body `generar_retrabajo` (F4, 2026-10-20; bool, default `true`, 422 si no es bool):** el frontend lo pregunta en un pop-up «¿Iniciar un nuevo incidente?» al confirmar «Observar» (`AuditarModal`: Volver / «No, solo registrar» / «Sí, iniciar nuevo incidente»; cierra al elegir y avisa por toast). Con `true`: **INSERT ... SELECT de un reclamo nuevo** copiando vecino/tipo/área/dirección/geo/activo/empresa/prioridad del auditado, `canal_origen='oficio'`, `id_reclamo_origen_auditoria`, descripción «Retrabajo por auditoría observada del reclamo REC-…: <observación>»; historial en los dos; post-commit `push.notificar_retrabajo_auditoria` (mail genérico + aviso + push al vecino). Con `false`: solo el historial del auditado («… — Sin retrabajo: el auditor no abrió un incidente nuevo»), `id_reclamo_retrabajo: null`, sin aviso. Ya NO crea una OT Pendiente ni devuelve el reclamo a En gestión. Marcador de deploy en OpenAPI: la descripción del 422 de `/observar` menciona `generar_retrabajo`.
- **La mesa del auditor no muestra SLA** (desde F4): el reclamo ya está resuelto, su vencimiento no aplica a la auditoría. El backend sigue devolviendo `sla_vencimiento`/`sla_dias` en la fila.
- **`PUT /{id}/estado` sobre una OT de auditoría**: `Terminada` → 422 (se cierra solo por aprobar/observar, si no el reclamo queda colgado en `En auditoría`); `Cancelada` → el reclamo vuelve a `Resuelto` (limpia `fecha_inicio_auditoria`/`resultado`, historial «Auditoría cancelada»); mover/cancelar una auditoría exige nivel ≤ 2 o ser el auditor asignado (`_validar_scope_operar_ot` exime a las auditorías, así que este guard es aparte).
- **Mesa supervisor y `POST /ot` / `/con-agenda`**: `En auditoría` y `Auditado` se tratan como `Resuelto` (no se listan, no se les asigna OT).

### Scope-subárea en mutaciones (2026-07-18, hallazgos [33][34] de la auditoría)

- **`_validar_scope_operar_ot(db, user, id_ot, id_agente_delegado=)`** aplica en `PUT /{id}/tomar` y `PUT /{id}/estado` sobre OTs OPERATIVAS: nivel 3/4 solo opera OTs propias (`ot.id_agente`), de sus cuadrillas (`ot.id_equipo ∈ ids_equipos` — la excepción por equipo es OBLIGATORIA porque la mesa del agente ofrece OTs por membresía sin condición de subárea) o de su subárea (`tr.id_subarea` derivada del tipo; NULL = no acotable, se permite). Nivel 2 pasa por `_validar_scope_supervisor_ot` (reclamo Y agente destino en la delegación de tomar). Nivel 1 sin restricción.
- **OTs `es_auditoria=TRUE` EXENTAS** del guard de misma-subárea (la auditoría es cross-subárea POR DISEÑO). Su guard es el INVERSO: **`_validar_scope_auditor`** en `/aprobar` y `/observar` (alias `/rechazar`) re-valida en la mutación el mismo filtro de la mesa — (1) auditoría asignada a otro auditor → 403; (2) con `auditor_misma_subarea_permitido=false`, subárea propia (agente ∪ equipos) → 403; la asignación al propio auditor PREVALECE sobre el filtro de subárea. Admin (nivel 1) bypassea.
- Regla al agregar una mutación de OT: llamar a uno de los dos guards según `es_auditoria` — verificado con smoke multi-subárea (n4 cross 403 / propio 200 / delegación n2 cross 403).
